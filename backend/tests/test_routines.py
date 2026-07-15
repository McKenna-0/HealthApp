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
def exercises(db):
    bench = models.Exercise(name="Bench Press", category="push", is_custom=0, created_at="x")
    squat = models.Exercise(name="Squat", category="legs", is_custom=0, created_at="x")
    db.add_all([bench, squat])
    db.commit()
    return bench, squat


def test_routine_crud(client, exercises):
    bench, squat = exercises
    r = client.post(
        "/api/routines",
        json={
            "name": "Push Day",
            "exercises": [
                {"exercise_id": bench.id, "target_sets": 4},
                {"exercise_id": squat.id, "target_sets": 3},
            ],
        },
    )
    assert r.status_code == 200
    routine = r.json()
    assert [e["name"] for e in routine["exercises"]] == ["Bench Press", "Squat"]

    # duplicate name blocked
    assert client.post("/api/routines", json={"name": "push day", "exercises": []}).status_code == 409

    # update replaces children
    r = client.put(
        f"/api/routines/{routine['id']}",
        json={"name": "Push Day 2", "exercises": [{"exercise_id": squat.id, "target_sets": 5}]},
    )
    assert r.status_code == 200
    assert r.json()["exercises"][0]["target_sets"] == 5

    assert len(client.get("/api/routines").json()) == 1
    assert client.delete(f"/api/routines/{routine['id']}").status_code == 200
    assert client.get("/api/routines").json() == []


def test_routine_from_workout(client, db, exercises):
    bench, squat = exercises
    act = models.Activity(
        external_id="app:x", date="2026-07-14", source="app",
        type="strength_training", status="finished", synced_at="x",
    )
    db.add(act)
    db.commit()
    for i, (ex, warm) in enumerate([(bench, 1), (bench, 0), (bench, 0), (squat, 0)]):
        db.add(models.WorkoutSet(
            activity_id=act.id, exercise_id=ex.id, set_number=i + 1,
            reps=8, weight_kg=60, source="manual", is_warmup=warm,
        ))
    db.commit()

    r = client.post(f"/api/routines/from-workout/{act.id}", json={"name": "Snapshot"})
    assert r.status_code == 200
    ex_list = r.json()["exercises"]
    assert ex_list[0]["name"] == "Bench Press"
    assert ex_list[0]["target_sets"] == 2  # warm-up not counted
    assert ex_list[1]["target_sets"] == 1


def test_start_session_from_routine(client, db, exercises):
    bench, _ = exercises
    r = client.post(
        "/api/routines",
        json={"name": "Push", "exercises": [{"exercise_id": bench.id, "target_sets": 4}]},
    )
    routine_id = r.json()["id"]
    r = client.post("/api/workouts/sessions", json={"routine_id": routine_id})
    assert r.status_code == 200
    payload = r.json()
    assert payload["activity"]["name"] == "Push"
    assert payload["planned_exercises"] == [
        {"exercise_id": bench.id, "name": "Bench Press", "target_sets": 4}
    ]
    routine = db.get(models.Routine, routine_id)
    assert routine.last_used_at is not None
