"""Analytics windows must be anchorable to a past date, not just today.

The agent asks questions like "what did my training load look like before that
injury in March" - which only works if these functions accept an explicit end
date and exclude everything after it."""

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.db import Base
from app.services.cardio import pace_trend, training_load_series, weekly_summary
from app.services.correlations import _build_frame, compute_insights
from app.timeutil import today_local


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


_seq = iter(range(1, 100000))


def _add_activity(db, d: date, type_="running", load=50.0, speed=3.0):
    db.add(
        models.Activity(
            external_id=f"act-{next(_seq)}",
            date=d.isoformat(),
            type=type_,
            name=f"{type_} {d.isoformat()}",
            duration_min=45.0,
            distance_km=8.0,
            avg_hr=145,
            avg_speed_mps=speed,
            training_load=load,
            source="mock",
            synced_at="x",
        )
    )


# ---- cardio.training_load_series -------------------------------------------------


def test_training_load_series_defaults_to_today(db):
    today = today_local()
    for i in range(30):
        _add_activity(db, today - timedelta(days=i))
    db.commit()

    result = training_load_series(db, days=10)
    assert result["series"][-1]["date"] == today.isoformat()
    assert len(result["series"]) == 10


def test_training_load_series_anchors_to_past_end(db):
    today = today_local()
    for i in range(61):
        _add_activity(db, today - timedelta(days=i))
    db.commit()

    end = today - timedelta(days=30)
    result = training_load_series(db, days=10, end=end.isoformat())

    assert result["series"][-1]["date"] == end.isoformat()
    assert result["series"][0]["date"] == (end - timedelta(days=9)).isoformat()
    assert len(result["series"]) == 10
    # history measured up to `end`, not up to today
    assert result["history_days"] == 31


def test_training_load_series_excludes_activity_after_end(db):
    """A huge load logged after `end` must not inflate the as-of-then picture."""
    today = today_local()
    end = today - timedelta(days=20)
    for i in range(40):
        _add_activity(db, today - timedelta(days=i), load=10.0)
    db.commit()

    before = training_load_series(db, days=5, end=end.isoformat())

    # spike lands two days after `end` - inside the raw query's old unbounded reach
    _add_activity(db, end + timedelta(days=2), load=9999.0)
    db.commit()

    after = training_load_series(db, days=5, end=end.isoformat())
    assert before["series"] == after["series"]


# ---- cardio.pace_trend -----------------------------------------------------------


def test_pace_trend_anchors_to_past_end(db):
    today = today_local()
    _add_activity(db, today - timedelta(days=1))
    _add_activity(db, today - timedelta(days=40))
    db.commit()

    recent = pace_trend(db, "running", weeks=2)
    assert [r["date"] for r in recent] == [(today - timedelta(days=1)).isoformat()]

    historical = pace_trend(
        db, "running", weeks=2, end=(today - timedelta(days=35)).isoformat()
    )
    assert [r["date"] for r in historical] == [(today - timedelta(days=40)).isoformat()]


# ---- cardio.weekly_summary -------------------------------------------------------


def test_weekly_summary_excludes_weeks_after_end(db):
    today = today_local()
    for i in range(0, 60, 7):
        _add_activity(db, today - timedelta(days=i))
    db.commit()

    end = today - timedelta(days=21)
    bounded = weekly_summary(db, weeks=52, end=end.isoformat())
    unbounded = weekly_summary(db, weeks=52)

    assert len(bounded) < len(unbounded)
    last_iso = end.isocalendar()
    assert bounded[-1]["week"] <= f"{last_iso.year}-W{last_iso.week:02d}"


# ---- correlations ----------------------------------------------------------------


def _seed_metrics(db, start: date, days: int):
    for i in range(days):
        d = start + timedelta(days=i)
        db.add(
            models.DailyMetrics(
                date=d.isoformat(),
                steps=8000,
                resting_hr=55,
                hrv_last_night_avg=60.0,
                source="mock",
                synced_at="x",
            )
        )
    db.commit()


def test_build_frame_respects_upper_bound(db):
    today = today_local()
    _seed_metrics(db, today - timedelta(days=59), 60)

    end = today - timedelta(days=20)
    frame = _build_frame(db, days=10, end=end.isoformat())

    assert max(frame.keys()) == end.isoformat()
    assert min(frame.keys()) == (end - timedelta(days=9)).isoformat()
    assert len(frame) == 10


def test_compute_insights_reports_its_window(db):
    today = today_local()
    _seed_metrics(db, today - timedelta(days=59), 60)

    end = today - timedelta(days=20)
    result = compute_insights(db, days=30, end=end.isoformat())
    assert result["end"] == end.isoformat()
    assert result["days"] == 30


def test_compute_insights_default_end_is_today(db):
    today = today_local()
    _seed_metrics(db, today - timedelta(days=59), 60)

    implicit = compute_insights(db, days=30)
    explicit = compute_insights(db, days=30, end=today.isoformat())
    assert implicit == explicit
