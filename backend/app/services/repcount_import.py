"""One-off RepCount CSV import.

Maps RepCount export rows (one row per set) into activities + workout_sets.
Grouping key is the exact "Workout Start" string; idempotency via
external_id = "repcount:<start with T>". Exercise names are matched
case/space-insensitively against the existing catalogue; misses create
custom exercises with a coarse category/muscle mapping.
"""

import csv
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..timeutil import iso_now

logger = logging.getLogger(__name__)

CATEGORY_MAP = {
    "back": "pull",
    "biceps": "pull",
    "chest": "push",
    "triceps": "push",
    "shoulders": "push",
    "legs": "legs",
    "core": "core",
    "abs": "core",
}

MUSCLES_MAP = {
    "back": ["lats", "upper_back"],
    "biceps": ["biceps"],
    "chest": ["chest"],
    "triceps": ["triceps"],
    "shoulders": ["side_delts", "front_delts"],
    "legs": ["quads", "glutes", "hamstrings"],
    "core": ["abs"],
    "abs": ["abs"],
}


@dataclass
class ImportStats:
    workouts_created: int = 0
    workouts_skipped_existing: int = 0
    sets_created: int = 0
    exercises_created: list[str] = field(default_factory=list)
    bodyweight_entries: int = 0
    skipped_rows: dict[str, int] = field(default_factory=dict)

    def skip(self, reason: str) -> None:
        self.skipped_rows[reason] = self.skipped_rows.get(reason, 0) + 1

    def summary(self) -> str:
        lines = [
            f"Workouts created:  {self.workouts_created}",
            f"Workouts skipped (already imported): {self.workouts_skipped_existing}",
            f"Sets created:      {self.sets_created}",
            f"Bodyweight logs:   {self.bodyweight_entries}",
            f"Exercises created ({len(self.exercises_created)}):",
        ]
        lines += [f"  - {n}" for n in sorted(self.exercises_created)]
        if self.skipped_rows:
            lines.append("Skipped rows:")
            lines += [f"  {k}: {v}" for k, v in sorted(self.skipped_rows.items())]
        return "\n".join(lines)


def _parse_ts(raw: str | None) -> str | None:
    """'2026-07-15 16:55' -> '2026-07-15T16:55' (fromisoformat-parseable)."""
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        datetime.fromisoformat(raw.replace(" ", "T"))
    except ValueError:
        return None
    return raw.replace(" ", "T")


def _parse_float(raw: str | None) -> float | None:
    raw = (raw or "").strip().replace(",", ".")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


class _ExerciseResolver:
    def __init__(self, db: Session, stats: ImportStats):
        self.db = db
        self.stats = stats
        self.by_key: dict[str, models.Exercise] = {
            e.name.strip().lower(): e for e in db.scalars(select(models.Exercise))
        }

    def resolve(self, raw_name: str, raw_category: str) -> models.Exercise:
        name = raw_name.strip()
        key = name.lower()
        ex = self.by_key.get(key)
        if ex is not None:
            return ex
        cat_key = (raw_category or "").strip().lower()
        muscles = MUSCLES_MAP.get(cat_key)
        ex = models.Exercise(
            name=name,
            category=CATEGORY_MAP.get(cat_key, "other"),
            equipment=None,
            is_custom=1,
            created_at=iso_now(),
            primary_muscles=json.dumps(muscles) if muscles else None,
        )
        self.db.add(ex)
        self.db.flush()  # assign id
        self.by_key[key] = ex
        self.stats.exercises_created.append(name)
        return ex


def import_csv(
    db: Session,
    rows: Iterable[dict],
    dry_run: bool = False,
    import_bodyweight: bool = True,
) -> ImportStats:
    stats = ImportStats()
    resolver = _ExerciseResolver(db, stats)

    # group rows by exact Workout Start string, preserving file order
    groups: dict[str, list[dict]] = {}
    for row in rows:
        start = (row.get("Workout Start") or "").strip()
        if not start or _parse_ts(start) is None:
            stats.skip("missing/invalid Workout Start")
            continue
        groups.setdefault(start, []).append(row)

    existing_ids = set(
        db.scalars(
            select(models.Activity.external_id).where(
                models.Activity.external_id.like("repcount:%")
            )
        )
    )

    for start, group in groups.items():
        start_ts = _parse_ts(start)
        assert start_ts is not None
        external_id = f"repcount:{start_ts}"
        if external_id in existing_ids:
            stats.workouts_skipped_existing += 1
            continue

        end_ts = _parse_ts(group[0].get("Workout End"))
        duration_min = None
        if end_ts:
            mins = (
                datetime.fromisoformat(end_ts) - datetime.fromisoformat(start_ts)
            ).total_seconds() / 60
            duration_min = round(mins, 1) if mins > 0 else None

        act = models.Activity(
            external_id=external_id,
            date=start_ts[:10],
            start_ts=start_ts,
            ended_ts=end_ts,
            duration_min=duration_min,
            type="strength_training",
            name=(group[0].get("Name") or "").strip() or "RepCount workout",
            source="repcount",
            status="finished",
            synced_at=iso_now(),
        )
        db.add(act)
        db.flush()

        set_counts: dict[int, int] = {}
        total_reps = 0
        total_volume = 0.0
        bodyweight_done = False
        for row in group:
            ex_name = (row.get("Exercise") or "").strip()
            if not ex_name:
                if any((row.get(k) or "").strip() for k in ("Kcal", "Distance", "Duration")):
                    stats.skip("cardio row")
                else:
                    stats.skip("missing exercise")
                continue
            reps_f = _parse_float(row.get("Reps"))
            weight = _parse_float(row.get("Weight"))
            if reps_f is None or reps_f <= 0:
                stats.skip("missing/invalid reps")
                continue
            if weight is None:
                stats.skip("missing weight")
                continue
            reps = int(reps_f)
            ex = resolver.resolve(ex_name, row.get("Category") or "")
            set_counts[ex.id] = set_counts.get(ex.id, 0) + 1
            note = (row.get("Notes") or "").strip() or None
            db.add(
                models.WorkoutSet(
                    activity_id=act.id,
                    exercise_id=ex.id,
                    set_number=set_counts[ex.id],
                    reps=reps,
                    weight_kg=weight,
                    note=note,
                    source="repcount",
                    is_warmup=0,
                )
            )
            stats.sets_created += 1
            total_reps += reps
            total_volume += weight * reps

            bw = _parse_float(row.get("Bodyweight"))
            if import_bodyweight and bw is not None and bw > 30 and not bodyweight_done:
                bodyweight_done = True
                existing_bw = db.scalar(
                    select(models.WeightLog).where(
                        models.WeightLog.date == start_ts[:10],
                        models.WeightLog.source == "repcount",
                    )
                )
                if existing_bw is None:
                    db.add(
                        models.WeightLog(
                            date=start_ts[:10],
                            ts=start_ts,
                            weight_kg=bw,
                            source="repcount",
                        )
                    )
                    stats.bodyweight_entries += 1

        act.total_sets = sum(set_counts.values())
        act.total_reps = total_reps
        act.total_volume_kg = round(total_volume, 1)
        stats.workouts_created += 1

    if dry_run:
        db.rollback()
    else:
        db.commit()
    return stats


def import_csv_file(
    db: Session,
    path: str | Path,
    dry_run: bool = False,
    import_bodyweight: bool = True,
) -> ImportStats:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return import_csv(
            db, csv.DictReader(f), dry_run=dry_run, import_bodyweight=import_bodyweight
        )
