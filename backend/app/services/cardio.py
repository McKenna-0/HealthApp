"""Cardio analytics: weekly aggregates, pace trends, training load + ACR."""

from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..timeutil import today_local

STRENGTH_TYPES = {"strength_training", "indoor_cardio", "yoga", "pilates"}


def _resolve_end(end: str | None) -> date:
    """Anchor date for a window. Defaults to today so callers that omit it
    keep the previous 'always relative to now' behaviour."""
    return date.fromisoformat(end) if end else today_local()


def _activities(
    db: Session,
    start: str | None = None,
    type_: str | None = None,
    end: str | None = None,
):
    q = select(models.Activity).order_by(models.Activity.date)
    if start:
        q = q.where(models.Activity.date >= start)
    if end:
        q = q.where(models.Activity.date <= end)
    if type_:
        q = q.where(models.Activity.type == type_)
    return db.scalars(q).all()


# Public alias - the AI tool layer needs raw activity rows for a bounded range.
list_activities = _activities


def _fallback_load(a: models.Activity) -> float | None:
    """duration x HR-intensity when Garmin didn't provide activityTrainingLoad."""
    if a.duration_min is None or a.avg_hr is None:
        return None
    hr_max_est = 190.0
    intensity = max(0.0, min(1.2, a.avg_hr / hr_max_est))
    return round(a.duration_min * intensity, 1)


def weekly_summary(
    db: Session,
    weeks: int = 12,
    type_: str | None = None,
    end: str | None = None,
) -> list[dict]:
    agg: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "distance_km": 0.0, "duration_min": 0.0, "load": 0.0, "elevation_m": 0.0}
    )
    for a in _activities(db, type_=type_, end=end):
        iso = date.fromisoformat(a.date).isocalendar()
        key = f"{iso.year}-W{iso.week:02d}"
        e = agg[key]
        e["count"] += 1
        e["distance_km"] += a.distance_km or 0
        e["duration_min"] += a.duration_min or 0
        e["load"] += a.training_load or _fallback_load(a) or 0
        e["elevation_m"] += a.elevation_gain_m or 0
    keys = sorted(agg.keys())[-weeks:]
    return [
        {
            "week": k,
            "count": agg[k]["count"],
            "distance_km": round(agg[k]["distance_km"], 1),
            "duration_min": round(agg[k]["duration_min"], 0),
            "load": round(agg[k]["load"], 0),
            "elevation_m": round(agg[k]["elevation_m"], 0),
        }
        for k in keys
    ]


def pace_trend(
    db: Session, type_: str, weeks: int = 12, end: str | None = None
) -> list[dict]:
    """Per-activity pace/speed series for one activity type.

    `end` anchors the window so historical periods can be inspected, not just
    the run-up to today."""
    end_d = _resolve_end(end)
    start = (end_d - timedelta(weeks=weeks)).isoformat()
    out = []
    for a in _activities(db, start=start, type_=type_, end=end_d.isoformat()):
        if not a.avg_speed_mps or not a.distance_km:
            continue
        pace_min_per_km = (1000 / a.avg_speed_mps) / 60
        out.append(
            {
                "date": a.date,
                "id": a.id,
                "name": a.name,
                "distance_km": a.distance_km,
                "pace_min_per_km": round(pace_min_per_km, 2),
                "speed_kmh": round(a.avg_speed_mps * 3.6, 1),
                "avg_hr": a.avg_hr,
            }
        )
    return out


MIN_CHRONIC_DAYS = 21


def training_load_series(db: Session, days: int = 60, end: str | None = None) -> dict:
    """Daily load + 7d acute / 28d chronic averages + ACR (gated on history).

    `end` anchors the window; activities after it are excluded so an ACR can be
    computed as-of a past date without hindsight leaking in."""
    end_d = _resolve_end(end)
    start = end_d - timedelta(days=days + 28)
    daily: dict[str, float] = defaultdict(float)
    for a in _activities(db, start=start.isoformat(), end=end_d.isoformat()):
        daily[a.date] += a.training_load or _fallback_load(a) or 0

    first_load_date = min(daily.keys()) if daily else None
    series = []
    d = end_d - timedelta(days=days - 1)
    while d <= end_d:
        acute_days = [(d - timedelta(days=i)).isoformat() for i in range(7)]
        chronic_days = [(d - timedelta(days=i)).isoformat() for i in range(28)]
        acute = sum(daily.get(x, 0) for x in acute_days) / 7
        chronic = sum(daily.get(x, 0) for x in chronic_days) / 28
        history_days = (
            (d - date.fromisoformat(first_load_date)).days + 1 if first_load_date else 0
        )
        acr = (
            round(acute / chronic, 2)
            if chronic > 0 and history_days >= MIN_CHRONIC_DAYS
            else None
        )
        series.append(
            {
                "date": d.isoformat(),
                "load": round(daily.get(d.isoformat(), 0), 0),
                "acute_7d": round(acute, 1),
                "chronic_28d": round(chronic, 1),
                "acr": acr,
            }
        )
        d += timedelta(days=1)

    history_days = (
        (end_d - date.fromisoformat(first_load_date)).days + 1 if first_load_date else 0
    )
    return {
        "series": series,
        "sufficient_history": history_days >= MIN_CHRONIC_DAYS,
        "history_days": history_days,
    }
