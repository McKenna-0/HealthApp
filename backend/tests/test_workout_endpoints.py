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
