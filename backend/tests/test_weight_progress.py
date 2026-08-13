import random
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.db import Base, get_db
from app.main import app
from app.services.weight_progress import (
    classify_rate,
    eta_date,
    goal_line,
    rate_bands,
    smooth_weights,
    weight_progress,
)

END = date(2026, 7, 1)


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
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _days(n: int, end: date = END) -> list[str]:
    start = end - timedelta(days=n - 1)
    return [(start + timedelta(days=i)).isoformat() for i in range(n)]


def _seed_weights(db, series: dict[str, float], source: str = "manual"):
    for d, kg in series.items():
        db.add(models.WeightLog(date=d, ts=f"{d}T07:00:00", weight_kg=kg, source=source))
    db.commit()


def _settings(db, **kwargs):
    for key, value in kwargs.items():
        db.add(models.UserSetting(key=key, value=str(value)))
    db.commit()


# ---- smoother ---------------------------------------------------------------


def test_smoother_recovers_a_known_linear_rate():
    days = _days(90)
    truth = {d: 80.0 - 0.05 * i for i, d in enumerate(days)}
    random.seed(11)
    obs = {d: v + random.gauss(0, 0.4) for d, v in truth.items()}

    smoothed = smooth_weights(days, obs)

    mid = smoothed[45]
    assert abs(mid["slope"] * 7 - (-0.35)) < 0.06
    # Mid-series level should sit far closer to truth than any single reading.
    assert abs(mid["level"] - truth[mid["date"]]) < 0.2


def test_smoother_ignores_a_single_water_weight_spike():
    """A 2 kg one-day jump is a plausible salty meal, not a 2 kg gain."""
    days = _days(60)
    obs = {d: 75.0 for d in days}
    spike_day = days[30]
    obs[spike_day] = 77.0

    smoothed = smooth_weights(days, obs)
    by_date = {s["date"]: s for s in smoothed}

    assert abs(by_date[spike_day]["level"] - 75.0) < 0.35
    # And it must not be read as a rate of change.
    assert abs(by_date[spike_day]["slope"] * 7) < 0.1


def test_smoother_tracks_a_change_of_rate_within_a_fortnight():
    days = _days(80)
    truth: dict[str, float] = {}
    w = 75.0
    for i, d in enumerate(days):
        truth[d] = w
        w += 0.0 if i < 40 else 0.3 / 7
    random.seed(3)
    obs = {d: v + random.gauss(0, 0.4) for d, v in truth.items()}

    by_date = {s["date"]: s for s in smooth_weights(days, obs)}

    # The smoother is two-sided, so days either side of the turn read as part
    # of the transition. Well clear of it, both regimes come back cleanly.
    assert abs(by_date[days[25]]["slope"] * 7) < 0.1  # flat before the change
    assert by_date[days[54]]["slope"] * 7 > 0.2  # ~90% of 0.3 kg/wk after 14d


def test_smoother_handles_gaps_without_inventing_readings():
    """Weighing twice a week still yields the right rate, with a wider CI."""
    days = _days(60)
    truth = {d: 90.0 - (0.5 / 7) * i for i, d in enumerate(days)}
    random.seed(5)
    obs = {d: truth[d] + random.gauss(0, 0.5) for i, d in enumerate(days) if i % 3 == 0}

    smoothed = smooth_weights(days, obs)

    assert len(smoothed) == len(days) - days.index(min(obs))
    assert abs(smoothed[-1]["slope"] * 7 - (-0.5)) < 0.2
    assert smoothed[-1]["slope_sd"] > 0


def test_smoother_needs_a_few_readings():
    days = _days(10)
    assert smooth_weights(days, {}) == []
    assert smooth_weights(days, {days[0]: 80.0, days[1]: 80.2}) == []


def test_smoother_starts_at_the_first_reading():
    days = _days(30)
    obs = {d: 70.0 for d in days[10:]}
    smoothed = smooth_weights(days, obs)
    assert smoothed[0]["date"] == days[10]


def test_flat_series_reports_no_rate_and_a_tight_interval():
    days = _days(60)
    smoothed = smooth_weights(days, {d: 80.0 for d in days})
    assert abs(smoothed[-1]["slope"] * 7) < 0.01
    assert smoothed[-1]["level_sd"] < 0.3


# ---- rate classification ----------------------------------------------------


def test_bands_scale_with_body_weight():
    bands = rate_bands(80.0)
    assert bands["max_loss_kg_per_week"] == pytest.approx(0.8)
    assert bands["max_gain_kg_per_week"] == pytest.approx(0.4)


def test_gaining_at_the_planned_rate_is_on_track():
    assert classify_rate(0.25, 0.25, 80.0) == "on_track"


def test_gaining_faster_than_the_lean_gain_limit_is_too_fast():
    # 0.6 kg/wk on 80 kg is 0.75%/wk, past the 0.5%/wk ceiling.
    assert classify_rate(0.6, 0.25, 80.0) == "too_fast"


def test_beating_the_plan_but_staying_healthy_is_still_on_track():
    # 0.35 kg/wk on 80 kg is 0.44%/wk: ahead of a 0.2 kg/wk plan, still safe.
    assert classify_rate(0.35, 0.2, 80.0) == "on_track"


def test_losing_while_trying_to_gain_is_wrong_way():
    assert classify_rate(-0.1, 0.25, 80.0) == "wrong_way"


def test_barely_gaining_against_the_plan_is_too_slow():
    assert classify_rate(0.05, 0.4, 80.0) == "too_slow"


def test_cutting_faster_than_one_percent_a_week_is_too_fast():
    assert classify_rate(-1.0, -0.5, 80.0) == "too_fast"
    assert classify_rate(-0.7, -0.5, 80.0) == "on_track"


def test_gaining_while_trying_to_lose_is_wrong_way():
    assert classify_rate(0.2, -0.5, 80.0) == "wrong_way"


def test_maintenance_tolerates_small_drift_only():
    assert classify_rate(0.1, 0.0, 80.0) == "on_track"
    assert classify_rate(0.4, 0.0, 80.0) == "too_fast"


# ---- goal line --------------------------------------------------------------


def test_goal_line_starts_at_the_anchor_and_follows_the_rate():
    days = _days(15)
    line = goal_line(days, days[0], 70.0, 0.35, None)
    assert line[days[0]] == 70.0
    assert line[days[7]] == pytest.approx(70.35, abs=0.01)


def test_goal_line_is_undefined_before_the_goal_was_set():
    days = _days(15)
    line = goal_line(days, days[5], 70.0, 0.35, None)
    assert days[4] not in line
    assert line[days[5]] == 70.0


def test_goal_line_flattens_once_it_reaches_the_target():
    days = _days(60)
    line = goal_line(days, days[0], 70.0, 0.7, 72.0)
    assert line[days[-1]] == 72.0
    assert max(line.values()) == 72.0


def test_goal_line_clamps_downwards_for_a_cut():
    days = _days(60)
    line = goal_line(days, days[0], 80.0, -0.7, 78.0)
    assert min(line.values()) == 78.0


def test_eta_is_none_when_moving_away_from_the_target():
    assert eta_date("2026-07-01", 80.0, -0.05, 85.0) is None
    assert eta_date("2026-07-01", 80.0, 0.0, 85.0) is None
    assert eta_date("2026-07-01", 80.0, 0.05, 85.0) == "2026-10-09"


# ---- end to end -------------------------------------------------------------


def _seed_gaining_person(db, rate_per_week=0.3, base=70.0, days=60):
    day_list = _days(days)
    random.seed(21)
    _seed_weights(
        db,
        {
            d: base + (rate_per_week / 7) * i + random.gauss(0, 0.35)
            for i, d in enumerate(day_list)
        },
    )
    return day_list


def test_weight_progress_reports_trend_goal_and_status(db):
    day_list = _seed_gaining_person(db)
    _settings(
        db,
        weight_goal_kg=75.0,
        weight_goal_rate_kg_per_week=0.3,
        weight_goal_start_date=day_list[0],
        weight_goal_start_kg=70.0,
    )

    out = weight_progress(db, END.isoformat(), days=60)

    assert out["current"]["status"] == "on_track"
    assert out["current"]["rate_kg_per_week"] == pytest.approx(0.3, abs=0.15)
    assert (
        out["current"]["rate_lo_kg_per_week"]
        < out["current"]["rate_kg_per_week"]
        < out["current"]["rate_hi_kg_per_week"]
    )
    assert out["goal"]["target_kg"] == 75.0
    assert out["goal"]["remaining_kg"] > 0
    assert out["goal"]["eta_actual"] > END.isoformat()

    last = out["series"][-1]
    assert last["goal"] == pytest.approx(70.0 + 0.3 / 7 * 59, abs=0.01)
    assert last["trend_lo"] < last["trend"] < last["trend_hi"]
    assert last["status"] == "on_track"


def test_weight_progress_flags_a_gain_that_is_too_fast(db):
    # 1.2 kg/wk on ~70 kg is 1.7%/wk — well past the 0.5%/wk ceiling.
    day_list = _seed_gaining_person(db, rate_per_week=1.2)
    _settings(
        db,
        weight_goal_rate_kg_per_week=0.3,
        weight_goal_start_date=day_list[0],
        weight_goal_start_kg=70.0,
    )

    out = weight_progress(db, END.isoformat(), days=60)
    assert out["current"]["status"] == "too_fast"
    assert out["series"][-1]["status"] == "too_fast"


def test_weight_progress_flags_losing_while_bulking(db):
    day_list = _seed_gaining_person(db, rate_per_week=-0.4)
    _settings(
        db,
        weight_goal_rate_kg_per_week=0.3,
        weight_goal_start_date=day_list[0],
        weight_goal_start_kg=70.0,
    )

    out = weight_progress(db, END.isoformat(), days=60)
    assert out["current"]["status"] == "wrong_way"


def test_weight_progress_without_a_goal_still_returns_the_trend(db):
    _seed_gaining_person(db)
    out = weight_progress(db, END.isoformat(), days=60)

    assert out["goal"] is None
    assert out["current"]["status"] is None
    assert out["current"]["trend_kg"] > 0
    assert all(p["goal"] is None for p in out["series"])


def test_weight_progress_with_no_data_explains_itself(db):
    out = weight_progress(db, END.isoformat(), days=60)
    assert out["current"] is None
    assert "weigh-ins" in out["reason"]
    assert len(out["series"]) == 60


def test_weight_progress_forecast_widens_with_horizon(db):
    _seed_gaining_person(db)
    out = weight_progress(db, END.isoformat(), days=60, horizon=21)

    fc = out["forecast"]
    assert len(fc) == 21
    assert fc[0]["date"] == (END + timedelta(days=1)).isoformat()
    assert fc[-1]["hi"] - fc[-1]["lo"] > fc[0]["hi"] - fc[0]["lo"]
    assert fc[0]["lo"] < fc[0]["projected"] < fc[0]["hi"]


def test_forecast_carries_the_goal_line_so_the_two_stay_comparable(db):
    day_list = _seed_gaining_person(db)
    _settings(
        db,
        weight_goal_rate_kg_per_week=0.3,
        weight_goal_start_date=day_list[0],
        weight_goal_start_kg=70.0,
    )

    fc = weight_progress(db, END.isoformat(), days=60, horizon=14)["forecast"]
    assert fc[-1]["goal"] == pytest.approx(70.0 + 0.3 / 7 * 73, abs=0.01)


def test_weight_progress_anchors_the_goal_when_no_start_was_saved(db):
    _seed_gaining_person(db)
    _settings(db, weight_goal_rate_kg_per_week=0.3)

    out = weight_progress(db, END.isoformat(), days=60)
    assert out["goal"]["start_date"] == out["series"][0]["date"]
    assert out["series"][0]["goal"] is not None


def test_manual_weights_win_over_device_readings(db):
    day_list = _days(30)
    _seed_weights(db, {d: 80.0 for d in day_list}, source="garmin")
    _seed_weights(db, {day_list[-1]: 70.0}, source="manual")

    out = weight_progress(db, END.isoformat(), days=30)
    assert out["current"]["latest_scale_kg"] == 70.0


# ---- API --------------------------------------------------------------------


def test_weight_progress_endpoint(client, db):
    day_list = _seed_gaining_person(db)
    _settings(db, weight_goal_kg=75.0, weight_goal_rate_kg_per_week=0.3)

    r = client.get(f"/api/analytics/weight-progress?days=60&end={END.isoformat()}")
    assert r.status_code == 200
    body = r.json()
    assert body["series"][0]["date"] == day_list[0]
    assert body["current"]["trend_kg"] > 0
    assert body["method"].startswith("Local linear trend model")


def test_settings_put_is_partial(client):
    """Saving a weight goal must not blank the macro targets, or vice versa."""
    client.put("/api/settings", json={"calorie_target": 2600, "protein_target_g": 180})
    client.put(
        "/api/settings",
        json={"weight_goal_kg": 75, "weight_goal_rate_kg_per_week": 0.3},
    )

    out = client.get("/api/settings").json()
    assert out["calorie_target"] == 2600
    assert out["protein_target_g"] == 180
    assert out["weight_goal_kg"] == 75
    assert out["weight_goal_rate_kg_per_week"] == 0.3


def test_settings_accepts_a_negative_goal_rate(client):
    r = client.put("/api/settings", json={"weight_goal_rate_kg_per_week": -0.5})
    assert r.status_code == 200
    assert r.json()["weight_goal_rate_kg_per_week"] == -0.5


def test_settings_rejects_an_absurd_goal_rate(client):
    assert client.put("/api/settings", json={"weight_goal_rate_kg_per_week": 9}).status_code == 422
    assert client.put("/api/settings", json={"weight_goal_start_date": "July"}).status_code == 422
