"""Derived analytics: energy balance, EWMA weight trend, TDEE back-estimation,
rolling averages. Plain Python — series are tiny, no numpy needed."""

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models

KCAL_PER_KG = 7700.0
EWMA_ALPHA = 0.1
SOURCE_PRIORITY = {"manual": 0, "garmin": 1, "mock": 2}


def _date_range(start: str, end: str) -> list[str]:
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    return [(d0 + timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]


# ---- weight trend --------------------------------------------------------------


def daily_weights(db: Session, start: str, end: str) -> dict[str, float]:
    """One weight per day; manual entries take priority over device/mock."""
    rows = db.scalars(
        select(models.WeightLog)
        .where(models.WeightLog.date >= start, models.WeightLog.date <= end)
        .order_by(models.WeightLog.date)
    ).all()
    best: dict[str, models.WeightLog] = {}
    for r in rows:
        cur = best.get(r.date)
        if cur is None or SOURCE_PRIORITY.get(r.source, 9) < SOURCE_PRIORITY.get(cur.source, 9):
            best[r.date] = r
    return {d: r.weight_kg for d, r in best.items()}


def ewma_trend(weights: dict[str, float], days: list[str]) -> dict[str, float]:
    """EWMA over the daily series; gaps carry the trend forward unchanged."""
    trend: dict[str, float] = {}
    cur: float | None = None
    for d in days:
        w = weights.get(d)
        if w is not None:
            cur = w if cur is None else cur + EWMA_ALPHA * (w - cur)
        if cur is not None:
            trend[d] = round(cur, 3)
    return trend


def ols_slope(points: list[tuple[int, float]]) -> float | None:
    """Least-squares slope for (x, y) points; None if degenerate."""
    n = len(points)
    if n < 2:
        return None
    mean_x = sum(p[0] for p in points) / n
    mean_y = sum(p[1] for p in points) / n
    denom = sum((p[0] - mean_x) ** 2 for p in points)
    if denom == 0:
        return None
    return sum((p[0] - mean_x) * (p[1] - mean_y) for p in points) / denom


# ---- energy balance -------------------------------------------------------------


def energy_balance(db: Session, start: str, end: str) -> list[dict]:
    intake_rows = db.execute(
        select(
            models.FoodLog.date,
            func.sum(models.FoodLog.calories),
            func.min(models.FoodLog.logging_complete_day),
        )
        .where(models.FoodLog.date >= start, models.FoodLog.date <= end)
        .group_by(models.FoodLog.date)
    ).all()
    intake = {r[0]: (r[1], bool(r[2])) for r in intake_rows}

    out_rows = db.execute(
        select(models.DailyMetrics.date, models.DailyMetrics.calories_total_out).where(
            models.DailyMetrics.date >= start, models.DailyMetrics.date <= end
        )
    ).all()
    cal_out = {r[0]: r[1] for r in out_rows}

    days = _date_range(start, end)
    result = []
    balances: list[float | None] = []
    for d in days:
        cin, complete = intake.get(d, (None, False))
        cout = cal_out.get(d)
        balance = round(cin - cout, 0) if (cin is not None and cout is not None) else None
        valid = balance is not None and complete
        balances.append(balance if valid else None)
        window = [b for b in balances[-7:] if b is not None]
        result.append(
            {
                "date": d,
                "calories_in": round(cin, 0) if cin is not None else None,
                "calories_out": cout,
                "balance": balance,
                "valid": valid,
                "balance_7d_avg": round(sum(window) / len(window), 0) if window else None,
            }
        )
    return result


# ---- TDEE ------------------------------------------------------------------------


EWMA_WARMUP_DAYS = 30


def estimate_tdee(db: Session, end: str, window: int = 28) -> dict:
    start = (date.fromisoformat(end) - timedelta(days=window - 1)).isoformat()
    days = _date_range(start, end)

    # Warm up the EWMA on earlier history so its convergence transient
    # doesn't flatten the slope inside the analysis window.
    warm_start = (
        date.fromisoformat(start) - timedelta(days=EWMA_WARMUP_DAYS)
    ).isoformat()
    weights_all = daily_weights(db, warm_start, end)
    trend_all = ewma_trend(weights_all, _date_range(warm_start, end))
    trend = {d: v for d, v in trend_all.items() if d >= start}
    weights = {d: v for d, v in weights_all.items() if d >= start}
    balance = energy_balance(db, start, end)

    valid_intakes = [b["calories_in"] for b in balance if b["valid"]]
    trend_points = [(i, trend[d]) for i, d in enumerate(days) if d in trend]

    reasons = []
    if len(valid_intakes) < 10:
        reasons.append(f"need >=10 complete logged days, have {len(valid_intakes)}")
    if len(weights) < 5:
        reasons.append(f"need >=5 weight entries, have {len(weights)}")
    slope = ols_slope(trend_points)
    if slope is None:
        reasons.append("not enough weight data for a trend slope")

    if reasons:
        return {
            "tdee": None,
            "reason": "; ".join(reasons),
            "window_days": window,
            "valid_logged_days": len(valid_intakes),
            "weight_points": len(weights),
        }

    mean_intake = sum(valid_intakes) / len(valid_intakes)
    tdee = mean_intake - slope * KCAL_PER_KG

    garmin_out = [b["calories_out"] for b in balance if b["calories_out"] is not None]
    return {
        "tdee": round(tdee, 0),
        "reason": None,
        "window_days": window,
        "valid_logged_days": len(valid_intakes),
        "weight_points": len(weights),
        "mean_intake": round(mean_intake, 0),
        "weight_slope_kg_per_week": round(slope * 7, 3),
        "garmin_mean_calories_out": round(sum(garmin_out) / len(garmin_out), 0)
        if garmin_out
        else None,
    }


# ---- readiness ---------------------------------------------------------------------

MIN_BASELINE_DAYS = 7


def readiness(db: Session, end: str) -> dict:
    """Transparent traffic-light readiness from today's HRV/RHR vs a 28-day
    baseline (excluding today) plus absolute sleep score and body battery."""
    end_d = date.fromisoformat(end)
    base_start = (end_d - timedelta(days=28)).isoformat()
    base_end = (end_d - timedelta(days=1)).isoformat()

    rows = db.scalars(
        select(models.DailyMetrics).where(
            models.DailyMetrics.date >= base_start, models.DailyMetrics.date <= end
        )
    ).all()
    today = next((r for r in rows if r.date == end), None)
    baseline_rows = [r for r in rows if base_start <= r.date <= base_end]

    hrv_base_vals = [r.hrv_last_night_avg for r in baseline_rows if r.hrv_last_night_avg is not None]
    rhr_base_vals = [r.resting_hr for r in baseline_rows if r.resting_hr is not None]
    sleep_today = db.scalar(select(models.Sleep.sleep_score).where(models.Sleep.date == end))

    baseline_days = max(len(hrv_base_vals), len(rhr_base_vals))
    if len(hrv_base_vals) < MIN_BASELINE_DAYS and len(rhr_base_vals) < MIN_BASELINE_DAYS:
        return {
            "status": "building_baseline",
            "label": f"Building baseline — day {baseline_days} of {MIN_BASELINE_DAYS}",
            "score_pct": None,
            "baseline_days": baseline_days,
            "components": [],
        }

    components = []

    def add(key: str, label: str, value, baseline, points: int | None):
        if points is not None:
            components.append(
                {"key": key, "label": label, "value": value, "baseline": baseline, "points": points, "max_points": 2}
            )

    hrv_today = today.hrv_last_night_avg if today else None
    if hrv_today is not None and len(hrv_base_vals) >= MIN_BASELINE_DAYS:
        hrv_base = sum(hrv_base_vals) / len(hrv_base_vals)
        ratio = hrv_today / hrv_base if hrv_base else None
        pts = None if ratio is None else (2 if ratio >= 0.95 else 1 if ratio >= 0.85 else 0)
        add("hrv", "HRV vs baseline", round(hrv_today, 1), round(hrv_base, 1), pts)

    rhr_today = today.resting_hr if today else None
    if rhr_today is not None and len(rhr_base_vals) >= MIN_BASELINE_DAYS:
        rhr_base = sum(rhr_base_vals) / len(rhr_base_vals)
        delta = rhr_today - rhr_base
        pts = 2 if delta <= 2 else 1 if delta <= 5 else 0
        add("rhr", "Resting HR vs baseline", rhr_today, round(rhr_base, 1), pts)

    if sleep_today is not None:
        pts = 2 if sleep_today >= 75 else 1 if sleep_today >= 60 else 0
        add("sleep", "Sleep score", sleep_today, None, pts)

    bb_today = today.body_battery_high if today else None
    if bb_today is not None:
        pts = 2 if bb_today >= 75 else 1 if bb_today >= 50 else 0
        add("body_battery", "Body battery (high)", bb_today, None, pts)

    if not components:
        return {
            "status": "no_data",
            "label": "No data for today yet",
            "score_pct": None,
            "baseline_days": baseline_days,
            "components": [],
        }

    score = sum(c["points"] for c in components)
    possible = sum(c["max_points"] for c in components)
    pct = round(100 * score / possible)
    if pct >= 75:
        status, label = "green", "Ready"
    elif pct >= 45:
        status, label = "amber", "Take it steady"
    else:
        status, label = "red", "Recover"

    return {
        "status": status,
        "label": label,
        "score_pct": pct,
        "baseline_days": baseline_days,
        "components": components,
    }


# ---- rolling averages / dashboard -------------------------------------------------


def _rolling(values: list[float | None], window: int) -> list[float | None]:
    out: list[float | None] = []
    for i in range(len(values)):
        chunk = [v for v in values[max(0, i - window + 1) : i + 1] if v is not None]
        out.append(round(sum(chunk) / len(chunk), 1) if chunk else None)
    return out


def dashboard(db: Session, end: str, days: int = 30) -> dict:
    start = (date.fromisoformat(end) - timedelta(days=days - 1)).isoformat()
    day_list = _date_range(start, end)

    metrics = {
        m.date: m
        for m in db.scalars(
            select(models.DailyMetrics).where(
                models.DailyMetrics.date >= start, models.DailyMetrics.date <= end
            )
        )
    }
    sleeps = {
        s.date: s
        for s in db.scalars(
            select(models.Sleep).where(
                models.Sleep.date >= start, models.Sleep.date <= end
            )
        )
    }
    weights = daily_weights(db, start, end)
    trend = ewma_trend(weights, day_list)
    balance = {b["date"]: b for b in energy_balance(db, start, end)}

    steps = [metrics[d].steps if d in metrics else None for d in day_list]
    rhr = [metrics[d].resting_hr if d in metrics else None for d in day_list]
    hrv = [metrics[d].hrv_last_night_avg if d in metrics else None for d in day_list]
    scores = [sleeps[d].sleep_score if d in sleeps else None for d in day_list]

    series = []
    steps_7d = _rolling(steps, 7)
    for i, d in enumerate(day_list):
        m = metrics.get(d)
        s = sleeps.get(d)
        b = balance.get(d, {})
        series.append(
            {
                "date": d,
                "steps": steps[i],
                "steps_7d": steps_7d[i],
                "resting_hr": rhr[i],
                "hrv": hrv[i],
                "stress_avg": m.stress_avg if m else None,
                "body_battery_high": m.body_battery_high if m else None,
                "sleep_score": scores[i],
                "sleep_duration_min": s.duration_min if s else None,
                "weight": weights.get(d),
                "weight_trend": trend.get(d),
                "calories_in": b.get("calories_in"),
                "calories_out": b.get("calories_out"),
                "balance": b.get("balance"),
            }
        )

    def _avg(vals):
        xs = [v for v in vals if v is not None]
        return round(sum(xs) / len(xs), 1) if xs else None

    return {
        "start": start,
        "end": end,
        "series": series,
        "averages_7d": {
            "steps": _avg(steps[-7:]),
            "resting_hr": _avg(rhr[-7:]),
            "hrv": _avg(hrv[-7:]),
            "sleep_score": _avg(scores[-7:]),
        },
        "tdee": estimate_tdee(db, end),
        "readiness": readiness(db, end),
    }
