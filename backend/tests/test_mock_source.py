from datetime import date, timedelta

from app.datasources.mock_source import MockSource

START = date(2026, 4, 1)
DAYS = [START + timedelta(days=i) for i in range(90)]


def test_deterministic():
    a, b = MockSource(), MockSource()
    for d in DAYS[:14]:
        assert a.fetch_daily_metrics(d) == b.fetch_daily_metrics(d)
        assert a.fetch_sleep(d) == b.fetch_sleep(d)
    assert a.fetch_weight(START, DAYS[13]) == b.fetch_weight(START, DAYS[13])


def test_alcohol_depresses_hrv_and_sleep():
    src = MockSource()
    hrv_after_alcohol, hrv_normal = [], []
    score_after_alcohol, score_normal = [], []
    for d in DAYS:
        m = src.fetch_daily_metrics(d)
        s = src.fetch_sleep(d)
        drank = src.is_alcohol_night(d - timedelta(days=1))
        if src.is_ill(d):
            continue
        (hrv_after_alcohol if drank else hrv_normal).append(m.hrv_last_night_avg)
        (score_after_alcohol if drank else score_normal).append(s.sleep_score)
    assert hrv_after_alcohol, "expected some alcohol nights in 90 days"
    assert sum(hrv_after_alcohol) / len(hrv_after_alcohol) < sum(hrv_normal) / len(hrv_normal) - 5
    assert sum(score_after_alcohol) / len(score_after_alcohol) < sum(score_normal) / len(score_normal) - 10


def test_illness_raises_rhr():
    src = MockSource()
    ill = [src.fetch_daily_metrics(d).resting_hr for d in DAYS if src.is_ill(d)]
    ok = [src.fetch_daily_metrics(d).resting_hr for d in DAYS if not src.is_ill(d)]
    assert ill, "expected an illness stretch in 90 days"
    assert sum(ill) / len(ill) > sum(ok) / len(ok) + 5


def test_weight_trend_slope():
    src = MockSource()
    ws = src.fetch_weight(START, DAYS[-1])
    first_week = sum(w.weight_kg for w in ws[:7]) / 7
    last_week = sum(w.weight_kg for w in ws[-7:]) / 7
    expected_drop = 0.045 * 83
    assert abs((first_week - last_week) - expected_drop) < 1.0


def test_calories_are_consistent():
    src = MockSource()
    for d in DAYS[:30]:
        m = src.fetch_daily_metrics(d)
        assert m.calories_total_out == m.calories_bmr + m.calories_active
