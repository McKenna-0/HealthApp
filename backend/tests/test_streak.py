from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.db import Base, get_db
from app.main import app
from app.services.checkin import compute_streaks

TODAY = date(2026, 7, 20)


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


def _food(db, day):
    db.add(models.FoodLog(date=day, ts=f"{day}T12:00:00", meal="lunch", calories=100))


def _checkin(db, day):
    db.add(models.DailyCheckin(date=day, ts="x", alcohol_units=0, caffeine_cups=0, illness=0))


def _complete(db, day):
    _food(db, day)
    _checkin(db, day)


def test_empty(db):
    s = compute_streaks(db, TODAY)
    assert s["current_streak"] == 0
    assert s["longest_streak"] == 0
    assert s["today_complete"] is False
    assert len(s["week"]) == 7
    assert all(not d["complete"] for d in s["week"])


def test_three_day_run_ending_today(db):
    for d in ["2026-07-18", "2026-07-19", "2026-07-20"]:
        _complete(db, d)
    db.commit()
    s = compute_streaks(db, TODAY)
    assert s["current_streak"] == 3
    assert s["longest_streak"] == 3
    assert s["today_complete"] is True


def test_food_only_or_checkin_only_not_complete(db):
    _food(db, "2026-07-20")
    _checkin(db, "2026-07-19")
    db.commit()
    s = compute_streaks(db, TODAY)
    assert s["current_streak"] == 0
    assert s["longest_streak"] == 0
    week = {d["date"]: d for d in s["week"]}
    assert week["2026-07-20"]["food_logged"] is True
    assert week["2026-07-20"]["checkin_done"] is False
    assert week["2026-07-19"]["checkin_done"] is True
    assert week["2026-07-19"]["food_logged"] is False


def test_gap_breaks_current_but_longest_counts_old_run(db):
    for d in ["2026-07-10", "2026-07-11", "2026-07-12", "2026-07-13"]:
        _complete(db, d)
    for d in ["2026-07-19", "2026-07-20"]:
        _complete(db, d)
    db.commit()
    s = compute_streaks(db, TODAY)
    assert s["current_streak"] == 2
    assert s["longest_streak"] == 4


def test_grace_today_incomplete(db):
    for d in ["2026-07-16", "2026-07-17", "2026-07-18", "2026-07-19"]:
        _complete(db, d)
    db.commit()
    s = compute_streaks(db, TODAY)
    assert s["current_streak"] == 4
    assert s["today_complete"] is False


def test_streak_endpoint_smoke(db):
    def override():
        yield db

    app.dependency_overrides[get_db] = override
    client = TestClient(app)
    r = client.get("/api/checkin/streak")
    assert r.status_code == 200
    body = r.json()
    assert {"current_streak", "longest_streak", "today_complete", "week"} <= set(body)
    app.dependency_overrides.clear()
