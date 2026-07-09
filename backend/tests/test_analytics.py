from datetime import date, timedelta

from app.services.analytics import ewma_trend, ols_slope


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


def test_ewma_carries_through_gaps():
    days = [(date(2026, 1, 1) + timedelta(days=i)).isoformat() for i in range(10)]
    weights = {days[0]: 80.0, days[5]: 79.0}
    trend = ewma_trend(weights, days)
    assert trend[days[0]] == 80.0
    assert trend[days[4]] == 80.0  # gap carries forward
    assert trend[days[5]] < 80.0
    assert len(trend) == 10
