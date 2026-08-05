from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.db import Base
from app.services.analytics import body_battery_factors, ewma_trend, ols_slope, readiness


def test_ols_slope_exact():
    pts = [(i, 2.0 * i + 5) for i in range(10)]
    assert abs(ols_slope(pts) - 2.0) < 1e-9


def test_ols_slope_degenerate():
    assert ols_slope([]) is None
    assert ols_slope([(1, 5.0)]) is None
    assert ols_slope([(1, 5.0), (1, 6.0)]) is None


def test_ewma_converges_to_linear_trend_slope():
    # weight falling 0.05 kg/day; after warmup the EWMA slope matches
    days = [(date(2026, 1, 1) + timedelta(days=i)).isoformat() for i in range(80)]
    weights = {d: 80.0 - 0.05 * i for i, d in enumerate(days)}
    trend = ewma_trend(weights, days)
    tail = [(i, trend[d]) for i, d in enumerate(days) if i >= 50]
    slope = ols_slope(tail)
    assert abs(slope - (-0.05)) < 0.005


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _seed_metrics(db, end: date, days: int, hrv=55.0, rhr=50, today_hrv=None, today_rhr=None, sleep_score=80, bb=85):
    for i in range(days, 0, -1):
        d = (end - timedelta(days=i)).isoformat()
        db.add(models.DailyMetrics(date=d, hrv_last_night_avg=hrv, resting_hr=rhr, source="mock", synced_at="x"))
    db.add(
        models.DailyMetrics(
            date=end.isoformat(),
            hrv_last_night_avg=today_hrv if today_hrv is not None else hrv,
            resting_hr=today_rhr if today_rhr is not None else rhr,
            body_battery_high=bb,
            source="mock",
            synced_at="x",
        )
    )
    db.add(models.Sleep(date=end.isoformat(), sleep_score=sleep_score, source="mock", synced_at="x"))
    db.commit()


def test_readiness_green_on_normal_day(db):
    end = date(2026, 7, 1)
    _seed_metrics(db, end, days=14)
    r = readiness(db, end.isoformat())
    assert r["status"] == "green"
    assert r["score_pct"] == 100
    assert len(r["components"]) == 4


def test_readiness_degrades_after_bad_night(db):
    end = date(2026, 7, 1)
    # HRV crashed 30%, RHR +7, poor sleep, low body battery
    _seed_metrics(db, end, days=14, today_hrv=38.0, today_rhr=57, sleep_score=55, bb=40)
    r = readiness(db, end.isoformat())
    assert r["status"] == "red"
    assert r["score_pct"] == 0


def test_readiness_building_baseline_with_few_days(db):
    end = date(2026, 7, 1)
    _seed_metrics(db, end, days=3)
    r = readiness(db, end.isoformat())
    assert r["status"] == "building_baseline"
    assert "day 3 of 7" in r["label"]


def test_ewma_carries_through_gaps():
    days = [(date(2026, 1, 1) + timedelta(days=i)).isoformat() for i in range(10)]
    weights = {days[0]: 80.0, days[5]: 79.0}
    trend = ewma_trend(weights, days)
    assert trend[days[0]] == 80.0
    assert trend[days[4]] == 80.0  # gap carries forward
    assert trend[days[5]] < 80.0
    assert len(trend) == 10


def test_body_battery_factors_sleep_and_activity(db):
    day = "2026-07-05"
    prev = "2026-07-04"
    db.add(models.Sleep(
        date=day,
        start_ts=f"{prev}T23:00:00",
        end_ts=f"{day}T07:00:00",
        source="mock",
        synced_at="x",
    ))
    db.add(models.Activity(
        external_id="test-run",
        date=day,
        start_ts=f"{day}T18:00:00",
        type="running",
        name="Evening Run",
        duration_min=30,
        source="mock",
        synced_at="x",
    ))
    db.add(models.IntradayBodyBattery(date=prev, timestamp="23:00", body_battery=20, source="mock"))
    db.add(models.IntradayBodyBattery(date=day, timestamp="07:00", body_battery=90, source="mock"))
    db.add(models.IntradayBodyBattery(date=day, timestamp="18:00", body_battery=60, source="mock"))
    db.add(models.IntradayBodyBattery(date=day, timestamp="18:30", body_battery=45, source="mock"))
    db.commit()

    factors = body_battery_factors(db, day)
    assert {f["type"] for f in factors} == {"sleep", "activity"}

    sleep_f = next(f for f in factors if f["type"] == "sleep")
    assert sleep_f["impact"] == 70

    act_f = next(f for f in factors if f["type"] == "activity")
    assert act_f["impact"] == -15
    assert act_f["label"] == "Evening Run"


def test_body_battery_factors_empty_without_intraday_data(db):
    assert body_battery_factors(db, "2026-07-05") == []
