from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.db import Base, get_db
from app.main import app
from app.services import strength
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
    ex = models.Exercise(name="Bench Press", category="push", is_custom=0, created_at="x")
    db.add(ex)
    db.commit()
    return ex


def _workout(db, date, ext):
    act = models.Activity(
        external_id=ext, date=date, source="app",
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


def test_same_day_sessions_stay_separate(db, bench):
    a1 = _workout(db, "2026-07-10", "a1")
    a2 = _workout(db, "2026-07-10", "a2")
    _set(db, a1, bench, weight=60, reps=10)
    _set(db, a2, bench, weight=80, reps=5)

    series = strength.exercise_session_series(db, bench.id)
    assert len(series) == 2
    assert {s["activity_id"] for s in series} == {a1.id, a2.id}


def test_session_series_aggregates_and_top_set(db, bench):
    a = _workout(db, "2026-07-10", "a1")
    _set(db, a, bench, weight=60, reps=10, n=1)
    _set(db, a, bench, weight=80, reps=10, n=2)  # higher e1RM -> top set
    _set(db, a, bench, weight=70, reps=3, n=3, warm=1)  # warmup excluded

    [s] = strength.exercise_session_series(db, bench.id)
    assert s["num_sets"] == 2
    assert s["total_reps"] == 20
    assert s["max_reps"] == 10
    assert s["volume_kg"] == pytest.approx(60 * 10 + 80 * 10)
    assert s["best_e1rm"] == pytest.approx(80 * (1 + 10 / 30), abs=0.1)
    assert [x["is_top"] for x in s["sets"]] == [False, True]


def test_start_date_filter_and_endpoint_range(client, db, bench):
    today = today_local()
    recent = _workout(db, today.isoformat(), "recent")
    old = _workout(db, (today - timedelta(days=200)).isoformat(), "old")
    _set(db, recent, bench)
    _set(db, old, bench)

    r = client.get(f"/api/workouts/analytics/exercises/{bench.id}?range=3m")
    assert r.status_code == 200
    assert len(r.json()["sessions"]) == 1

    r = client.get(f"/api/workouts/analytics/exercises/{bench.id}?range=all")
    assert len(r.json()["sessions"]) == 2
    assert r.json()["exercise"]["name"] == "Bench Press"
    assert r.json()["prs"]["best_e1rm"] is not None


def test_overview_counts_distinct_workouts(client, db, bench):
    a1 = _workout(db, "2026-07-10", "a1")
    a2 = _workout(db, "2026-07-12", "a2")
    _set(db, a1, bench, n=1)
    _set(db, a1, bench, n=2)
    _set(db, a2, bench, weight=70)

    r = client.get("/api/workouts/analytics/exercises")
    assert r.status_code == 200
    [row] = r.json()["exercises"]
    assert row["total_workouts"] == 2
    assert row["last_date"] == "2026-07-12"
    assert row["name"] == "Bench Press"


def test_detail_404_for_unknown_exercise(client):
    assert client.get("/api/workouts/analytics/exercises/999").status_code == 404
