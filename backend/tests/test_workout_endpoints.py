from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.db import Base, get_db
from app.main import app
from app.timeutil import today_local


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


@pytest.fixture
def client(db):
    def override():
        yield db

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def bench(db):
    ex = models.Exercise(
        name="Bench Press", category="push", is_custom=0, created_at="x",
        primary_muscles='["chest"]', secondary_muscles='["front_delts","triceps"]',
    )
    db.add(ex)
    db.commit()
    return ex


def _workout(db, date, ext=None):
    act = models.Activity(
        external_id=ext or f"app:{date}", date=date, source="app",
        type="strength_training", status="finished", synced_at="x",
    )
    db.add(act)
    db.commit()
    return act


def _set(db, act, ex, weight=60.0, reps=8, n=1, warm=0):
    ws = models.WorkoutSet(
        activity_id=act.id, exercise_id=ex.id, set_number=n,
        reps=reps, weight_kg=weight, source="manual", is_warmup=warm,
    )
    db.add(ws)
    db.commit()
    return ws


def test_muscle_analytics_window(client, db, bench):
    today = today_local()
    recent = _workout(db, today.isoformat())
    old = _workout(db, (today - timedelta(days=30)).isoformat())
    _set(db, recent, bench)
    _set(db, old, bench)

    r = client.get("/api/workouts/analytics/muscles?days=7")
    assert r.status_code == 200
    data = r.json()
    assert data["days"] == 7
    assert data["muscles"]["chest"]["sets"] == 1


def test_workout_summary_endpoint(client, db, bench):
    act = _workout(db, "2026-07-14")
    _set(db, act, bench, weight=40, reps=10, warm=1)
    _set(db, act, bench, weight=80, reps=8, n=2)

    r = client.get(f"/api/workouts/{act.id}/summary")
    assert r.status_code == 200
    s = r.json()
    assert s["total_sets"] == 1
    assert s["tonnage_kg"] == 640.0
    assert s["exercise_count"] == 1
    assert s["muscles"]["chest"] == 1.0
    assert len(s["prs"]) == 1


def test_rename_workout(client, db):
    act = _workout(db, "2026-07-14")

    r = client.put(f"/api/workouts/{act.id}/name", json={"name": "  Push Day A  "})
    assert r.status_code == 200
    assert r.json()["name"] == "Push Day A"
    assert client.get(f"/api/workouts/{act.id}").json()["activity"]["name"] == "Push Day A"

    # blank names are rejected, as are names for garmin-sourced activities
    assert client.put(f"/api/workouts/{act.id}/name", json={"name": "   "}).status_code == 422
    assert client.put("/api/workouts/9999/name", json={"name": "x"}).status_code == 404

    act.source = "garmin"
    db.commit()
    r = client.put(f"/api/workouts/{act.id}/name", json={"name": "Renamed"})
    assert r.status_code == 409


def test_exercises_last_session_endpoint(client, db, bench):
    act = _workout(db, "2026-07-10")
    _set(db, act, bench, weight=80, reps=8)
    current = _workout(db, "2026-07-14", ext="app:current")

    r = client.get(f"/api/exercises/last-session?ids={bench.id}&exclude={current.id}")
    assert r.status_code == 200
    data = r.json()
    assert data[str(bench.id)]["sets"][0]["weight_kg"] == 80

    assert client.get("/api/exercises/last-session?ids=abc").status_code == 422


def test_custom_exercise_with_muscles(client):
    r = client.post(
        "/api/exercises",
        json={
            "name": "Cable Lateral Raise",
            "category": "push",
            "equipment": "cable",
            "primary_muscles": ["side_delts"],
            "secondary_muscles": ["traps"],
        },
    )
    assert r.status_code == 200
    out = r.json()
    assert out["primary_muscles"] == ["side_delts"]
    assert out["is_custom"] == 1

    r = client.post(
        "/api/exercises",
        json={"name": "Bad", "category": "other", "primary_muscles": ["wings"]},
    )
    assert r.status_code == 422


def _active(db, date, ext="app:active"):
    act = models.Activity(
        external_id=ext, date=date, source="app",
        type="strength_training", status="active", synced_at="x",
    )
    db.add(act)
    db.commit()
    return act


def test_update_set_returns_recomputed_comparison(client, db, bench):
    """Editing a set must re-run the last-session comparison, not echo the row."""
    prev = _workout(db, "2026-07-10", ext="app:prev")
    _set(db, prev, bench, weight=80, reps=8)
    cur = _active(db, "2026-07-14")

    logged = client.post(
        f"/api/workouts/{cur.id}/sets",
        json={"exercise_id": bench.id, "reps": 8, "weight_kg": 85.0, "is_warmup": 0},
    ).json()
    assert logged["delta_weight_kg"] == 5.0
    set_id = logged["set"]["id"]

    r = client.put(f"/api/workouts/sets/{set_id}", json={"weight_kg": 90.0, "reps": 10})
    assert r.status_code == 200
    out = r.json()
    assert out["set"]["weight_kg"] == 90.0
    assert out["set"]["reps"] == 10
    assert out["delta_weight_kg"] == 10.0
    assert out["delta_reps"] == 2
    assert out["e1rm"] == 120.0
    assert out["is_pr"] is True


def test_update_set_can_erase_a_pr(client, db, bench):
    """Editing down past a previous best clears the PR flag."""
    prev = _workout(db, "2026-07-10", ext="app:prev")
    _set(db, prev, bench, weight=100, reps=5)
    cur = _active(db, "2026-07-14")

    logged = client.post(
        f"/api/workouts/{cur.id}/sets",
        json={"exercise_id": bench.id, "reps": 5, "weight_kg": 110.0, "is_warmup": 0},
    ).json()
    assert logged["is_pr"] is True

    out = client.put(
        f"/api/workouts/sets/{logged['set']['id']}", json={"weight_kg": 90.0, "reps": 5}
    ).json()
    assert out["is_pr"] is False
    assert out["delta_weight_kg"] == -10.0


def test_active_session_carries_set_results(client, db, bench):
    """The session payload is the source of truth for the comparison chips, so
    a refetch after an edit shows the edited numbers."""
    prev = _workout(db, "2026-07-10", ext="app:prev")
    _set(db, prev, bench, weight=80, reps=8)
    _set(db, prev, bench, weight=80, reps=6, n=2)
    cur = _active(db, "2026-07-14")

    client.post(
        f"/api/workouts/{cur.id}/sets",
        json={"exercise_id": bench.id, "reps": 5, "weight_kg": 40.0, "is_warmup": 1},
    )
    first = client.post(
        f"/api/workouts/{cur.id}/sets",
        json={"exercise_id": bench.id, "reps": 8, "weight_kg": 85.0, "is_warmup": 0},
    ).json()
    client.post(
        f"/api/workouts/{cur.id}/sets",
        json={"exercise_id": bench.id, "reps": 6, "weight_kg": 85.0, "is_warmup": 0},
    )

    client.put(f"/api/workouts/sets/{first['set']['id']}", json={"weight_kg": 95.0, "reps": 8})

    payload = client.get("/api/workouts/sessions/active").json()["active"]
    results = payload["set_results"]
    edited = results[str(first["set"]["id"])]
    assert edited["set"]["weight_kg"] == 95.0
    assert edited["delta_weight_kg"] == 15.0
    assert edited["delta_reps"] == 0
    # warm-ups have no comparison, and the second working set keeps its own
    # ordinal against last session
    assert len([k for k in results]) == 2
    others = [v for k, v in results.items() if k != str(first["set"]["id"])]
    assert others[0]["delta_weight_kg"] == 5.0
