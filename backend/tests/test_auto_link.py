import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.db import Base, get_db
from app.main import app
from app.services import sessions


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


def _app_session(db, start="2026-07-14T17:00:00", end="2026-07-14T18:00:00", status="finished"):
    act = models.Activity(
        external_id=f"app:{start}", date=start[:10], start_ts=start, ended_ts=end,
        type="strength_training", name="Push", source="app", status=status,
        synced_at="x",
    )
    db.add(act)
    db.commit()
    return act


def _garmin(db, start="2026-07-14T17:05:00", duration=50.0, ext="g1", type_="strength_training"):
    act = models.Activity(
        external_id=ext, date=start[:10], start_ts=start, type=type_,
        duration_min=duration, avg_hr=92, max_hr=140, calories=250,
        source="garmin", synced_at="x",
    )
    db.add(act)
    db.commit()
    return act


def test_auto_link_overlapping(db):
    s = _app_session(db)
    g = _garmin(db)
    linked = sessions.try_auto_link(db, s)
    assert linked is not None and linked.id == g.id
    assert s.linked_activity_id == g.id
    assert s.avg_hr == 92
    assert s.calories == 250
    assert s.duration_min == 50.0


def test_auto_link_respects_tolerance(db):
    s = _app_session(db)
    # starts 20 min after session end -> within ±30 min tolerance
    _garmin(db, start="2026-07-14T18:20:00", duration=30.0)
    assert sessions.try_auto_link(db, s) is not None


def test_no_link_when_too_far_apart(db):
    s = _app_session(db)
    _garmin(db, start="2026-07-14T21:00:00", duration=30.0)  # 3h later
    assert sessions.try_auto_link(db, s) is None
    assert s.linked_activity_id is None


def test_no_link_wrong_type_or_date(db):
    s = _app_session(db)
    _garmin(db, type_="running")
    _garmin(db, start="2026-07-15T17:05:00", ext="g2")
    assert sessions.try_auto_link(db, s) is None


def test_best_overlap_wins_and_no_double_link(db):
    s = _app_session(db)
    _garmin(db, start="2026-07-14T16:20:00", duration=45.0, ext="worse")  # overlaps 5min
    best = _garmin(db, start="2026-07-14T17:00:00", duration=55.0, ext="better")
    assert sessions.try_auto_link(db, s).id == best.id

    s2 = _app_session(db, start="2026-07-14T17:10:00", end="2026-07-14T17:50:00")
    # best is taken; the worse one still overlaps via tolerance
    linked2 = sessions.try_auto_link(db, s2)
    assert linked2 is None or linked2.id != best.id


def test_auto_link_new_activities_after_sync(db):
    s = _app_session(db)
    assert s.linked_activity_id is None
    g = _garmin(db)
    assert sessions.auto_link_new_activities(db) == 1
    db.refresh(s)
    assert s.linked_activity_id == g.id


def test_linked_activity_hidden_from_list(client, db):
    s = _app_session(db)
    g = _garmin(db)
    sessions.link(db, s, g)
    rows = client.get("/api/workouts").json()
    ids = [r["id"] for r in rows]
    assert s.id in ids
    assert g.id not in ids


def test_active_session_hidden_from_list(client, db):
    _app_session(db, status="active")
    rows = client.get("/api/workouts").json()
    assert rows == []


def test_manual_link_and_unlink(client, db):
    s = _app_session(db)
    g = _garmin(db, start="2026-07-14T21:00:00")  # too far for auto
    r = client.post(f"/api/workouts/{s.id}/link/{g.id}")
    assert r.status_code == 200
    db.refresh(s)
    assert s.linked_activity_id == g.id
    assert s.avg_hr == 92

    # cannot double-link
    s2 = _app_session(db, start="2026-07-14T19:00:00", end="2026-07-14T20:00:00")
    assert client.post(f"/api/workouts/{s2.id}/link/{g.id}").status_code == 409

    r = client.delete(f"/api/workouts/{s.id}/link")
    assert r.status_code == 200
    db.refresh(s)
    assert s.linked_activity_id is None
    assert s.avg_hr is None
    assert s.duration_min == 60.0  # restored from timestamps
