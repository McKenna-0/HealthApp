"""Muscle group mapping for exercises: seed data backfill and heatmap
intensity aggregation (primary +1.0 / secondary +0.5 per working set)."""

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models

MUSCLE_GROUPS: list[str] = [
    "chest",
    "front_delts",
    "side_delts",
    "rear_delts",
    "biceps",
    "triceps",
    "forearms",
    "lats",
    "traps",
    "upper_back",
    "lower_back",
    "abs",
    "obliques",
    "glutes",
    "quads",
    "hamstrings",
    "calves",
]

# name -> (primary, secondary); keys match SEED_EXERCISES names exactly
EXERCISE_MUSCLES: dict[str, tuple[list[str], list[str]]] = {
    "Barbell Back Squat": (["quads", "glutes"], ["hamstrings", "lower_back", "abs"]),
    "Front Squat": (["quads"], ["glutes", "abs", "upper_back"]),
    "Leg Press": (["quads", "glutes"], ["hamstrings"]),
    "Romanian Deadlift": (["hamstrings", "glutes"], ["lower_back", "forearms"]),
    "Deadlift": (["hamstrings", "glutes", "lower_back"], ["traps", "forearms", "quads"]),
    "Leg Extension": (["quads"], []),
    "Leg Curl": (["hamstrings"], ["calves"]),
    "Bulgarian Split Squat": (["quads", "glutes"], ["hamstrings", "abs"]),
    "Walking Lunge": (["quads", "glutes"], ["hamstrings", "calves"]),
    "Standing Calf Raise": (["calves"], []),
    "Hip Thrust": (["glutes"], ["hamstrings", "quads"]),
    "Bench Press": (["chest"], ["front_delts", "triceps"]),
    "Incline Bench Press": (["chest", "front_delts"], ["triceps"]),
    "Dumbbell Bench Press": (["chest"], ["front_delts", "triceps"]),
    "Incline Dumbbell Press": (["chest", "front_delts"], ["triceps"]),
    "Overhead Press": (["front_delts", "side_delts"], ["triceps", "abs"]),
    "Seated Dumbbell Shoulder Press": (["front_delts", "side_delts"], ["triceps"]),
    "Dip": (["chest", "triceps"], ["front_delts"]),
    "Push Up": (["chest"], ["front_delts", "triceps", "abs"]),
    "Cable Fly": (["chest"], ["front_delts"]),
    "Lateral Raise": (["side_delts"], ["traps"]),
    "Triceps Pushdown": (["triceps"], []),
    "Overhead Triceps Extension": (["triceps"], []),
    "Close Grip Bench Press": (["triceps", "chest"], ["front_delts"]),
    "Pull Up": (["lats", "upper_back"], ["biceps", "forearms"]),
    "Chin Up": (["lats", "biceps"], ["upper_back", "forearms"]),
    "Lat Pulldown": (["lats"], ["biceps", "upper_back"]),
    "Barbell Row": (["upper_back", "lats"], ["biceps", "rear_delts", "lower_back"]),
    "Dumbbell Row": (["upper_back", "lats"], ["biceps", "rear_delts"]),
    "Seated Cable Row": (["upper_back", "lats"], ["biceps", "rear_delts"]),
    "Face Pull": (["rear_delts", "traps"], ["upper_back"]),
    "Barbell Curl": (["biceps"], ["forearms"]),
    "Dumbbell Curl": (["biceps"], ["forearms"]),
    "Hammer Curl": (["biceps", "forearms"], []),
    "Preacher Curl": (["biceps"], ["forearms"]),
    "Shrug": (["traps"], ["forearms"]),
    "Plank": (["abs"], ["obliques", "lower_back"]),
    "Hanging Leg Raise": (["abs"], ["obliques", "forearms"]),
    "Cable Crunch": (["abs"], ["obliques"]),
    "Ab Wheel Rollout": (["abs"], ["obliques", "lats"]),
    "Russian Twist": (["obliques"], ["abs"]),
    "Back Extension": (["lower_back"], ["glutes", "hamstrings"]),
}


def backfill_exercise_muscles(db: Session) -> int:
    """Set muscle columns for known exercises that don't have them yet.
    Idempotent; called on startup after seed_exercises."""
    updated = 0
    rows = db.scalars(
        select(models.Exercise).where(models.Exercise.primary_muscles.is_(None))
    ).all()
    for ex in rows:
        mapping = EXERCISE_MUSCLES.get(ex.name)
        if mapping is None:
            continue
        primary, secondary = mapping
        ex.primary_muscles = json.dumps(primary)
        ex.secondary_muscles = json.dumps(secondary)
        updated += 1
    if updated:
        db.commit()
    return updated


def _exercise_muscle_lookup(db: Session) -> dict[int, tuple[list[str], list[str]]]:
    out: dict[int, tuple[list[str], list[str]]] = {}
    for ex in db.scalars(select(models.Exercise)):
        primary = json.loads(ex.primary_muscles) if ex.primary_muscles else []
        secondary = json.loads(ex.secondary_muscles) if ex.secondary_muscles else []
        out[ex.id] = (primary, secondary)
    return out


def muscle_intensity(
    db: Session,
    activity_ids: list[int] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, float]:
    """Aggregate muscle work over non-warm-up sets, normalized to 0-1.
    +1.0 per set for each primary muscle, +0.5 for each secondary."""
    q = (
        select(models.WorkoutSet, models.Activity.date)
        .join(models.Activity, models.WorkoutSet.activity_id == models.Activity.id)
        .where(models.WorkoutSet.is_warmup == 0)
    )
    if activity_ids is not None:
        q = q.where(models.WorkoutSet.activity_id.in_(activity_ids))
    if start_date is not None:
        q = q.where(models.Activity.date >= start_date)
    if end_date is not None:
        q = q.where(models.Activity.date <= end_date)

    lookup = _exercise_muscle_lookup(db)
    raw: dict[str, float] = {}
    for ws, _d in db.execute(q).all():
        primary, secondary = lookup.get(ws.exercise_id, ([], []))
        for m in primary:
            raw[m] = raw.get(m, 0.0) + 1.0
        for m in secondary:
            raw[m] = raw.get(m, 0.0) + 0.5
    if not raw:
        return {}
    peak = max(raw.values())
    return {m: round(v / peak, 3) for m, v in raw.items()}


def muscle_set_counts(
    db: Session, start_date: str, end_date: str
) -> dict[str, dict[str, float]]:
    """Per-muscle set counts + normalized intensity for a date range
    (weekly coverage view)."""
    q = (
        select(models.WorkoutSet)
        .join(models.Activity, models.WorkoutSet.activity_id == models.Activity.id)
        .where(
            models.WorkoutSet.is_warmup == 0,
            models.Activity.date >= start_date,
            models.Activity.date <= end_date,
        )
    )
    lookup = _exercise_muscle_lookup(db)
    raw: dict[str, float] = {}
    sets: dict[str, int] = {}
    for ws in db.scalars(q).all():
        primary, secondary = lookup.get(ws.exercise_id, ([], []))
        for m in primary:
            raw[m] = raw.get(m, 0.0) + 1.0
            sets[m] = sets.get(m, 0) + 1
        for m in secondary:
            raw[m] = raw.get(m, 0.0) + 0.5
    if not raw:
        return {}
    peak = max(raw.values())
    return {
        m: {"sets": sets.get(m, 0), "intensity": round(v / peak, 3)}
        for m, v in raw.items()
    }
