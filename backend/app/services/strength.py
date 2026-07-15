"""Strength training: exercise catalogue seed, e1RM (Epley), PR detection,
weekly volume. PRs are computed on demand — trivial at single-user scale."""

from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..timeutil import iso_now

SEED_EXERCISES: list[tuple[str, str, str]] = [
    # (name, category, equipment)
    ("Barbell Back Squat", "legs", "barbell"),
    ("Front Squat", "legs", "barbell"),
    ("Leg Press", "legs", "machine"),
    ("Romanian Deadlift", "legs", "barbell"),
    ("Deadlift", "pull", "barbell"),
    ("Leg Extension", "legs", "machine"),
    ("Leg Curl", "legs", "machine"),
    ("Bulgarian Split Squat", "legs", "dumbbell"),
    ("Walking Lunge", "legs", "dumbbell"),
    ("Standing Calf Raise", "legs", "machine"),
    ("Hip Thrust", "legs", "barbell"),
    ("Bench Press", "push", "barbell"),
    ("Incline Bench Press", "push", "barbell"),
    ("Dumbbell Bench Press", "push", "dumbbell"),
    ("Incline Dumbbell Press", "push", "dumbbell"),
    ("Overhead Press", "push", "barbell"),
    ("Seated Dumbbell Shoulder Press", "push", "dumbbell"),
    ("Dip", "push", "bodyweight"),
    ("Push Up", "push", "bodyweight"),
    ("Cable Fly", "push", "cable"),
    ("Lateral Raise", "push", "dumbbell"),
    ("Triceps Pushdown", "push", "cable"),
    ("Overhead Triceps Extension", "push", "cable"),
    ("Close Grip Bench Press", "push", "barbell"),
    ("Pull Up", "pull", "bodyweight"),
    ("Chin Up", "pull", "bodyweight"),
    ("Lat Pulldown", "pull", "cable"),
    ("Barbell Row", "pull", "barbell"),
    ("Dumbbell Row", "pull", "dumbbell"),
    ("Seated Cable Row", "pull", "cable"),
    ("Face Pull", "pull", "cable"),
    ("Barbell Curl", "pull", "barbell"),
    ("Dumbbell Curl", "pull", "dumbbell"),
    ("Hammer Curl", "pull", "dumbbell"),
    ("Preacher Curl", "pull", "machine"),
    ("Shrug", "pull", "dumbbell"),
    ("Plank", "core", "bodyweight"),
    ("Hanging Leg Raise", "core", "bodyweight"),
    ("Cable Crunch", "core", "cable"),
    ("Ab Wheel Rollout", "core", "bodyweight"),
    ("Russian Twist", "core", "bodyweight"),
    ("Back Extension", "core", "bodyweight"),
]


def seed_exercises(db: Session) -> int:
    existing = set(db.scalars(select(models.Exercise.name)).all())
    added = 0
    for name, category, equipment in SEED_EXERCISES:
        if name not in existing:
            db.add(
                models.Exercise(
                    name=name,
                    category=category,
                    equipment=equipment,
                    is_custom=0,
                    created_at=iso_now(),
                )
            )
            added += 1
    if added:
        db.commit()
    return added


def epley_1rm(weight_kg: float, reps: int) -> float:
    if reps <= 1:
        return weight_kg
    return weight_kg * (1 + reps / 30)


def _sets_with_dates(
    db: Session, exercise_id: int | None = None, include_warmups: bool = False
):
    q = (
        select(models.WorkoutSet, models.Activity.date)
        .join(models.Activity, models.WorkoutSet.activity_id == models.Activity.id)
        .order_by(models.Activity.date, models.WorkoutSet.set_number)
    )
    if not include_warmups:
        q = q.where(models.WorkoutSet.is_warmup == 0)
    if exercise_id is not None:
        q = q.where(models.WorkoutSet.exercise_id == exercise_id)
    return db.execute(q).all()


def last_session_data(
    db: Session, exercise_ids: list[int], before_activity_id: int | None = None
) -> dict[int, dict]:
    """Most recent prior session's sets per exercise — for ghost prefill and
    progressive-overload deltas. Excludes warm-ups and the current session."""
    if not exercise_ids:
        return {}
    q = (
        select(models.WorkoutSet, models.Activity.date, models.Activity.id)
        .join(models.Activity, models.WorkoutSet.activity_id == models.Activity.id)
        .where(
            models.WorkoutSet.exercise_id.in_(exercise_ids),
            models.WorkoutSet.is_warmup == 0,
        )
        .order_by(models.Activity.date, models.Activity.id, models.WorkoutSet.id)
    )
    if before_activity_id is not None:
        q = q.where(models.Activity.id != before_activity_id)

    # Rows arrive date-ascending; the last activity seen per exercise wins.
    latest: dict[int, dict] = {}
    for ws, d, act_id in db.execute(q).all():
        cur = latest.get(ws.exercise_id)
        if cur is None or cur["activity_id"] != act_id:
            latest[ws.exercise_id] = cur = {
                "date": d,
                "activity_id": act_id,
                "sets": [],
                "best_e1rm": None,
            }
        cur["sets"].append(
            {"set_number": len(cur["sets"]) + 1, "weight_kg": ws.weight_kg, "reps": ws.reps}
        )
        if ws.weight_kg is not None:
            e1 = round(epley_1rm(ws.weight_kg, ws.reps), 1)
            if cur["best_e1rm"] is None or e1 > cur["best_e1rm"]:
                cur["best_e1rm"] = e1
    return {
        ex_id: {"date": v["date"], "sets": v["sets"], "best_e1rm": v["best_e1rm"]}
        for ex_id, v in latest.items()
    }


def exercise_history(db: Session, exercise_id: int) -> list[dict]:
    """Per-session best e1RM + volume for one exercise (progression series)."""
    by_date: dict[str, dict] = {}
    for ws, d in _sets_with_dates(db, exercise_id):
        entry = by_date.setdefault(
            d, {"date": d, "sets": 0, "volume_kg": 0.0, "best_e1rm": None, "best_weight": None, "top_set": None}
        )
        entry["sets"] += 1
        if ws.weight_kg is not None:
            entry["volume_kg"] += ws.weight_kg * ws.reps
            e1 = epley_1rm(ws.weight_kg, ws.reps)
            if entry["best_e1rm"] is None or e1 > entry["best_e1rm"]:
                entry["best_e1rm"] = round(e1, 1)
                entry["top_set"] = f"{ws.weight_kg:g}kg x {ws.reps}"
            if entry["best_weight"] is None or ws.weight_kg > entry["best_weight"]:
                entry["best_weight"] = ws.weight_kg
    out = list(by_date.values())
    for e in out:
        e["volume_kg"] = round(e["volume_kg"], 1)
    return out


def personal_records(db: Session, exercise_id: int) -> dict:
    """Best e1RM overall + best weight per rep count (1-10)."""
    best_e1rm = None
    rep_prs: dict[int, dict] = {}
    for ws, d in _sets_with_dates(db, exercise_id):
        if ws.weight_kg is None:
            continue
        e1 = epley_1rm(ws.weight_kg, ws.reps)
        if best_e1rm is None or e1 > best_e1rm["e1rm"]:
            best_e1rm = {"e1rm": round(e1, 1), "weight_kg": ws.weight_kg, "reps": ws.reps, "date": d}
        if 1 <= ws.reps <= 10:
            cur = rep_prs.get(ws.reps)
            if cur is None or ws.weight_kg > cur["weight_kg"]:
                rep_prs[ws.reps] = {"weight_kg": ws.weight_kg, "date": d}
    return {
        "best_e1rm": best_e1rm,
        "rep_prs": [{"reps": r, **v} for r, v in sorted(rep_prs.items())],
    }


def is_new_pr(db: Session, workout_set: models.WorkoutSet, activity_date: str) -> bool:
    """Did this set beat every earlier e1RM for its exercise?"""
    if workout_set.weight_kg is None:
        return False
    e1 = epley_1rm(workout_set.weight_kg, workout_set.reps)
    for ws, d in _sets_with_dates(db, workout_set.exercise_id):
        if ws.id == workout_set.id:
            continue
        if d > activity_date:
            continue
        if ws.weight_kg is not None and epley_1rm(ws.weight_kg, ws.reps) >= e1:
            return False
    return True


def weekly_volume(db: Session, weeks: int = 12) -> list[dict]:
    """Sets + tonnage per ISO week, split by category."""
    agg: dict[str, dict] = defaultdict(
        lambda: {"sets": 0, "tonnage_kg": 0.0, "by_category": defaultdict(lambda: {"sets": 0, "tonnage_kg": 0.0})}
    )
    exercises = {e.id: e for e in db.scalars(select(models.Exercise))}
    for ws, d in _sets_with_dates(db):
        iso = date.fromisoformat(d).isocalendar()
        week_key = f"{iso.year}-W{iso.week:02d}"
        entry = agg[week_key]
        tonnage = (ws.weight_kg or 0) * ws.reps
        entry["sets"] += 1
        entry["tonnage_kg"] += tonnage
        cat = exercises[ws.exercise_id].category if ws.exercise_id in exercises else "other"
        entry["by_category"][cat]["sets"] += 1
        entry["by_category"][cat]["tonnage_kg"] += tonnage

    weeks_sorted = sorted(agg.keys())[-weeks:]
    return [
        {
            "week": w,
            "sets": agg[w]["sets"],
            "tonnage_kg": round(agg[w]["tonnage_kg"], 0),
            "by_category": {
                k: {"sets": v["sets"], "tonnage_kg": round(v["tonnage_kg"], 0)}
                for k, v in agg[w]["by_category"].items()
            },
        }
        for w in weeks_sorted
    ]
