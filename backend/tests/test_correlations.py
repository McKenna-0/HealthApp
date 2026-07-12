from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.datasources.mock_source import MockSource
from app.db import Base
from app.services.correlations import cohens_d, compute_insights, pearson_r


def test_pearson_r_exact():
    # perfectly linear -> r = 1
    assert abs(pearson_r([(i, 2 * i + 1) for i in range(10)]) - 1.0) < 1e-9
    # perfectly inverse -> r = -1
    assert abs(pearson_r([(i, -3 * i) for i in range(10)]) + 1.0) < 1e-9
    # hand-computed: x=[1,2,3], y=[2,4,5] -> r = 3/sqrt(2*4.6667) ~= 0.9820
    r = pearson_r([(1, 2), (2, 4), (3, 5)])
    assert abs(r - 0.98198) < 1e-4


def test_pearson_r_degenerate():
    assert pearson_r([]) is None
    assert pearson_r([(1, 2)]) is None
    assert pearson_r([(1, 2), (1, 3)]) is None  # zero x variance


def test_cohens_d_hand_computed():
    # A=[10,12], B=[6,8]: means 11 vs 7, pooled sd = sqrt((2+2)/2)=sqrt(2)
    d, diff = cohens_d([10, 12], [6, 8])
    assert diff == 4
    assert abs(d - 4 / (2**0.5)) < 1e-9


def test_cohens_d_degenerate():
    d, diff = cohens_d([5, 5], [5, 5])
    assert d is None  # zero pooled sd
    d, _ = cohens_d([5], [4, 6])
    assert d is None  # group too small for variance


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _seed_from_mock(db, days=60):
    """Seed daily metrics/sleep + alcohol/illness context from MockSource,
    which has documented ground-truth correlations."""
    src = MockSource()
    end = date.today()
    for i in range(days, 0, -1):
        d = end - timedelta(days=i)
        m = src.fetch_daily_metrics(d)
        s = src.fetch_sleep(d)
        db.add(
            models.DailyMetrics(
                date=d.isoformat(),
                steps=m.steps,
                resting_hr=m.resting_hr,
                hrv_last_night_avg=m.hrv_last_night_avg,
                source="mock",
                synced_at="x",
            )
        )
        db.add(
            models.Sleep(
                date=d.isoformat(),
                sleep_score=s.sleep_score,
                duration_min=s.duration_min,
                source="mock",
                synced_at="x",
            )
        )
        if src.is_alcohol_night(d):
            db.add(models.ContextLog(date=d.isoformat(), ts="x", type="alcohol", value=3.0))
        if src.is_ill(d):
            db.add(models.ContextLog(date=d.isoformat(), ts="x", type="illness", value=1.0))
    db.commit()


def test_insights_recover_mock_ground_truth(db):
    _seed_from_mock(db, days=90)
    result = compute_insights(db, days=90)
    by_id = {i["id"]: i for i in result["insights"]}

    alcohol_hrv = by_id["alcohol_hrv"]
    assert alcohol_hrv["status"] == "ok"
    assert alcohol_hrv["mean_diff"] < 0  # HRV lower after drinking
    assert alcohol_hrv["direction"] == "lower"
    assert alcohol_hrv["strength"] in ("moderate", "strong")

    alcohol_sleep = by_id["alcohol_sleep"]
    assert alcohol_sleep["status"] == "ok"
    assert alcohol_sleep["mean_diff"] < 0  # sleep score lower

    illness_rhr = by_id["illness_rhr"]
    assert illness_rhr["status"] == "ok"
    assert illness_rhr["mean_diff"] > 0  # RHR higher when ill
    assert illness_rhr["direction"] == "higher"


def test_insights_gate_on_small_n(db):
    # only 5 days of data -> everything insufficient, no effects computed
    _seed_from_mock(db, days=5)
    result = compute_insights(db, days=90)
    for i in result["insights"]:
        if i["status"] == "insufficient_data":
            assert i["effect"] is None
    # at least the binary ones must be gated with so few days
    by_id = {i["id"]: i for i in result["insights"]}
    assert by_id["alcohol_hrv"]["status"] == "insufficient_data"
    assert by_id["illness_rhr"]["status"] == "insufficient_data"
