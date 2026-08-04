"""Compose a compact JSON summary of all health data for the AI analyst.

The model only ever sees what this module emits — it can never claim access
to data it wasn't given. Reuses existing analytics/strength/cardio services."""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..services import analytics, cardio, strength
from ..services.bloodwork import out_of_range
from ..timeutil import today_local


def _round(v, nd=1):
    return round(v, nd) if isinstance(v, (int, float)) else v


def compose_summary(db: Session, days: int = 30) -> dict:
    end = today_local()
    start = end - timedelta(days=days - 1)
    start_s, end_s = start.isoformat(), end.isoformat()

    dash = analytics.dashboard(db, end_s, days)
    series = [d for d in dash["series"] if any(v is not None for k, v in d.items() if k != "date")]

    # workouts
    acts = db.scalars(
        select(models.Activity)
        .where(models.Activity.date >= start_s)
        .order_by(models.Activity.date)
    ).all()
    workouts = [
        {
            "date": a.date,
            "type": a.type,
            "name": a.name,
            "duration_min": a.duration_min,
            "distance_km": a.distance_km,
            "avg_hr": a.avg_hr,
            "calories": a.calories,
            "elevation_gain_m": a.elevation_gain_m,
            "training_load": _round(a.training_load),
            "aerobic_te": a.aerobic_te,
        }
        for a in acts
    ]

    # strength volume + top PRs for exercises trained in window
    weekly_vol = strength.weekly_volume(db, weeks=max(4, days // 7))
    trained_ex_ids = {
        ws.exercise_id
        for ws in db.scalars(
            select(models.WorkoutSet)
            .join(models.Activity, models.WorkoutSet.activity_id == models.Activity.id)
            .where(models.Activity.date >= start_s)
        )
    }
    exercises = {e.id: e.name for e in db.scalars(select(models.Exercise))}
    prs = {}
    for ex_id in trained_ex_ids:
        pr = strength.personal_records(db, ex_id)
        if pr["best_e1rm"]:
            prs[exercises.get(ex_id, str(ex_id))] = pr["best_e1rm"]

    load = cardio.training_load_series(db, days=days)

    # context logs
    ctx = db.scalars(
        select(models.ContextLog).where(models.ContextLog.date >= start_s)
    ).all()
    context = [
        {"date": c.date, "type": c.type, "value": c.value, "label": c.label, "note": c.note}
        for c in ctx
    ]

    # latest blood panels (up to 2)
    panels = db.scalars(
        select(models.BloodPanel).order_by(models.BloodPanel.date.desc()).limit(2)
    ).all()
    bloodwork = []
    for p in panels:
        results = db.scalars(
            select(models.BloodResult).where(models.BloodResult.panel_id == p.id)
        ).all()
        bloodwork.append(
            {
                "date": p.date,
                "lab": p.lab_name,
                "results": [
                    {
                        "marker": r.marker,
                        "value": r.value,
                        "unit": r.unit,
                        "ref_low": r.ref_low,
                        "ref_high": r.ref_high,
                        "flag": out_of_range(r.value, r.ref_low, r.ref_high),
                    }
                    for r in results
                ],
            }
        )

    # established correlation insights (only ok-status, keeps prompt compact)
    from .correlations import compute_insights

    corr = [
        {k: i[k] for k in ("id", "title", "n", "effect", "effect_type", "mean_diff", "unit", "strength", "summary_line")}
        for i in compute_insights(db, days=90)["insights"]
        if i["status"] == "ok"
    ]

    # macro targets (only numeric settings, not cookies/status strings)
    _TARGET_KEYS = {
        "calorie_target", "protein_target_g", "carbs_target_g", "fat_target_g",
        "protein_target_pct", "carbs_target_pct", "fat_target_pct",
    }
    targets = {
        r.key: (float(r.value) if r.value else None)
        for r in db.scalars(select(models.UserSetting))
        if r.key in _TARGET_KEYS
    }

    return {
        "period": {"start": start_s, "end": end_s, "days": days},
        "daily_series": series,
        "averages_7d": dash["averages_7d"],
        "tdee_estimate": dash["tdee"],
        "workouts": workouts,
        "strength_weekly_volume": weekly_vol,
        "strength_prs": prs,
        "training_load": {
            "sufficient_history_for_acr": load["sufficient_history"],
            "history_days": load["history_days"],
            "last_14_days": load["series"][-14:],
        },
        "context_logs": context,
        "bloodwork": bloodwork,
        "macro_targets": targets,
        "correlation_insights": corr,
    }
