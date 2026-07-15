import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.db import Base, get_db
from app.main import app


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
        name="Bench Press", category="push", equipment="barbell",
        is_custom=0, created_at="x",
        primary_muscles='["chest"]', secondary_muscles='["front_delts","triceps"]',
    )
    db.add(ex)
    db.commit()
    return ex


def _start(client, body=None):
    r = client.post("/api/workouts/sessions", json=body or {"name": "Push"})
    assert r.status_code == 200, r.text
    return r.json()


def test_create_and_finish_session(client, db, bench):
    s = _start(client)
    act = s["activity"]
    assert act["source"] == "app"
    assert act["status"] == "active"
    assert act["type"] == "strength_training"

    r = client.post(
        f"/api/workouts/{act['id']}/sets",
        json={"exercise_id": bench.id, "reps": 8, "weight_kg": 80},
    )
    assert r.status_code == 200
    res = r.json()
    assert res["set"]["set_number"] == 1
    assert res["is_pr"] is True  # first ever set
    assert res["e1rm"] == round(80 * (1 + 8 / 30), 1)

    r = client.post(f"/api/workouts/sessions/{act['id']}/finish")
    assert r.status_code == 200
    summary = r.json()
    assert summary["total_sets"] == 1
    assert summary["tonnage_kg"] == 640.0
    assert summary["muscles"]["chest"] == 1.0
    assert len(summary["prs"]) == 1

    row = db.get(models.Activity, act["id"])
    assert row.status == "finished"
    assert row.ended_ts is not None
    assert row.total_sets == 1


def test_only_one_active_session(client, bench):
    _start(client)
    r = client.post("/api/workouts/sessions", json={"name": "Second"})
    assert r.status_code == 409


def test_active_endpoint_and_discard(client, db, bench):
    s = _start(client)
    act_id = s["activity"]["id"]
    client.post(
        f"/api/workouts/{act_id}/sets",
        json={"exercise_id": bench.id, "reps": 5, "weight_kg": 60},
    )

    r = client.get("/api/workouts/sessions/active")
    active = r.json()["active"]
    assert active["activity"]["id"] == act_id
    assert len(active["sets"]) == 1
    assert active["planned_exercises"][0]["exercise_id"] == bench.id

    r = client.delete(f"/api/workouts/sessions/{act_id}")
    assert r.status_code == 200
    assert client.get("/api/workouts/sessions/active").json()["active"] is None
    assert db.get(models.Activity, act_id) is None
    assert db.query(models.WorkoutSet).count() == 0


def test_per_exercise_set_numbering(client, db, bench):
    squat = models.Exercise(
        name="Squat", category="legs", equipment="barbell", is_custom=0, created_at="x"
    )
    db.add(squat)
    db.commit()
    s = _start(client)
    act_id = s["activity"]["id"]

    r1 = client.post(f"/api/workouts/{act_id}/sets", json={"exercise_id": bench.id, "reps": 8, "weight_kg": 80})
    r2 = client.post(f"/api/workouts/{act_id}/sets", json={"exercise_id": squat.id, "reps": 5, "weight_kg": 100})
    r3 = client.post(f"/api/workouts/{act_id}/sets", json={"exercise_id": bench.id, "reps": 8, "weight_kg": 80})
    assert r1.json()["set"]["set_number"] == 1
    assert r2.json()["set"]["set_number"] == 1  # per-exercise ordinal
    assert r3.json()["set"]["set_number"] == 2


def test_ghosts_and_deltas_from_last_session(client, db, bench):
    # session 1
    s1 = _start(client)
    id1 = s1["activity"]["id"]
    client.post(f"/api/workouts/{id1}/sets", json={"exercise_id": bench.id, "reps": 8, "weight_kg": 80})
    client.post(f"/api/workouts/{id1}/sets", json={"exercise_id": bench.id, "reps": 7, "weight_kg": 80})
    client.post(f"/api/workouts/sessions/{id1}/finish")

    # session 2 via repeat
    s2 = _start(client, {"repeat_workout_id": id1})
    assert s2["planned_exercises"][0]["exercise_id"] == bench.id
    assert s2["planned_exercises"][0]["target_sets"] == 2
    ghost = s2["ghosts"][str(bench.id)]
    assert [g["weight_kg"] for g in ghost["sets"]] == [80, 80]

    id2 = s2["activity"]["id"]
    r = client.post(f"/api/workouts/{id2}/sets", json={"exercise_id": bench.id, "reps": 9, "weight_kg": 82.5})
    res = r.json()
    assert res["delta_weight_kg"] == 2.5
    assert res["delta_reps"] == 1
    assert res["is_pr"] is True


def test_planned_exercises_survive_reload(client, db, bench):
    """Repeat/routine plans must persist: GET /sessions/active returns the
    planned exercises even before any set is logged (regression)."""
    s1 = _start(client)
    id1 = s1["activity"]["id"]
    client.post(f"/api/workouts/{id1}/sets", json={"exercise_id": bench.id, "reps": 8, "weight_kg": 80})
    client.post(f"/api/workouts/sessions/{id1}/finish")

    s2 = _start(client, {"repeat_workout_id": id1})
    assert s2["planned_exercises"][0]["exercise_id"] == bench.id

    active = client.get("/api/workouts/sessions/active").json()["active"]
    assert active["planned_exercises"][0]["exercise_id"] == bench.id
    assert str(bench.id) in active["ghosts"]


def test_warmup_sets_no_pr_no_delta(client, db, bench):
    s = _start(client)
    act_id = s["activity"]["id"]
    r = client.post(
        f"/api/workouts/{act_id}/sets",
        json={"exercise_id": bench.id, "reps": 10, "weight_kg": 40, "is_warmup": 1},
    )
    res = r.json()
    assert res["is_pr"] is False
    assert res["e1rm"] is None
    assert res["delta_weight_kg"] is None

    summary = client.post(f"/api/workouts/sessions/{act_id}/finish").json()
    assert summary["total_sets"] == 0
    assert summary["tonnage_kg"] == 0
