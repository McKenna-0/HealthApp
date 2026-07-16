"""In-app workout sessions: create/finish/discard, watch auto-linking, and
completion summaries. A session is an Activity row with source='app'."""

import json
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..timeutil import iso_now
from . import muscles, strength

LINK_TOLERANCE_MIN = 30.0


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def create_session(
    db: Session,
    name: str | None = None,
    routine_id: int | None = None,
    repeat_workout_id: int | None = None,
) -> tuple[models.Activity, list[dict]]:
    """Create an active in-app workout. Returns (activity, planned_exercises)."""
    planned: list[dict] = []

    if routine_id is not None:
        routine = db.get(models.Routine, routine_id)
        if routine is None:
            raise ValueError("Routine not found")
        name = name or routine.name
        rows = db.scalars(
            select(models.RoutineExercise)
            .where(models.RoutineExercise.routine_id == routine_id)
            .order_by(models.RoutineExercise.position)
        ).all()
        for r in rows:
            ex = db.get(models.Exercise, r.exercise_id)
            if ex:
                planned.append(
                    {"exercise_id": ex.id, "name": ex.name, "target_sets": r.target_sets}
                )
        routine.last_used_at = iso_now()
    elif repeat_workout_id is not None:
        src = db.get(models.Activity, repeat_workout_id)
        if src is None:
            raise ValueError("Workout not found")
        name = name or src.name
        sets = db.scalars(
            select(models.WorkoutSet)
            .where(models.WorkoutSet.activity_id == repeat_workout_id)
            .order_by(models.WorkoutSet.id)
        ).all()
        seen: dict[int, int] = {}  # exercise_id -> working set count
        order: list[int] = []
        for ws in sets:
            if ws.exercise_id not in seen:
                seen[ws.exercise_id] = 0
                order.append(ws.exercise_id)
            if not ws.is_warmup:
                seen[ws.exercise_id] += 1
        for ex_id in order:
            ex = db.get(models.Exercise, ex_id)
            if ex:
                planned.append(
                    {
                        "exercise_id": ex.id,
                        "name": ex.name,
                        "target_sets": max(seen[ex_id], 1),
                    }
                )

    now = iso_now()
    act = models.Activity(
        external_id=f"app:{uuid4()}",
        date=now[:10],
        start_ts=now,
        type="strength_training",
        name=name or "Workout",
        source="app",
        status="active",
        synced_at=now,
        planned_json=json.dumps(
            [{"exercise_id": p["exercise_id"], "target_sets": p["target_sets"]} for p in planned]
        )
        if planned
        else None,
    )
    db.add(act)
    db.commit()
    return act, planned


def planned_exercises(db: Session, act: models.Activity) -> list[dict]:
    """Planned exercises for a session (from stored plan + any exercises that
    already have logged sets, in order of first appearance)."""
    planned: list[dict] = []
    seen: set[int] = set()
    exercises = {e.id: e for e in db.scalars(select(models.Exercise)).all()}
    for item in json.loads(act.planned_json) if act.planned_json else []:
        ex = exercises.get(item["exercise_id"])
        if ex and ex.id not in seen:
            seen.add(ex.id)
            planned.append(
                {"exercise_id": ex.id, "name": ex.name, "target_sets": item.get("target_sets", 3)}
            )
    sets = db.scalars(
        select(models.WorkoutSet)
        .where(models.WorkoutSet.activity_id == act.id)
        .order_by(models.WorkoutSet.id)
    ).all()
    for ws in sets:
        if ws.exercise_id not in seen:
            seen.add(ws.exercise_id)
            ex = exercises.get(ws.exercise_id)
            planned.append(
                {"exercise_id": ws.exercise_id, "name": ex.name if ex else "?", "target_sets": 3}
            )
    return planned


def get_active_session(db: Session) -> models.Activity | None:
    return db.scalar(
        select(models.Activity)
        .where(models.Activity.status == "active")
        .order_by(models.Activity.id.desc())
    )


def finish_session(db: Session, session: models.Activity) -> models.Activity:
    session.status = "finished"
    session.ended_ts = iso_now()

    sets = db.scalars(
        select(models.WorkoutSet).where(
            models.WorkoutSet.activity_id == session.id,
            models.WorkoutSet.is_warmup == 0,
        )
    ).all()
    session.total_sets = len(sets)
    session.total_reps = sum(s.reps for s in sets)
    session.total_volume_kg = round(sum((s.weight_kg or 0) * s.reps for s in sets), 1)

    if session.linked_activity_id is None:
        start = _parse_ts(session.start_ts)
        end = _parse_ts(session.ended_ts)
        if start and end:
            session.duration_min = round((end - start).total_seconds() / 60, 1)
        try_auto_link(db, session)
    db.commit()
    return session


def _overlap_min(
    a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime
) -> float:
    """Overlap in minutes between two intervals, with tolerance applied by caller."""
    start = max(a_start, b_start)
    end = min(a_end, b_end)
    return (end - start).total_seconds() / 60


def _link_candidates(db: Session, session: models.Activity) -> list[models.Activity]:
    linked_ids = select(models.Activity.linked_activity_id).where(
        models.Activity.linked_activity_id.is_not(None)
    )
    return db.scalars(
        select(models.Activity).where(
            models.Activity.date == session.date,
            models.Activity.type == "strength_training",
            models.Activity.source.not_in(["app", "repcount"]),
            models.Activity.id != session.id,
            models.Activity.id.not_in(linked_ids),
        )
    ).all()


def try_auto_link(db: Session, session: models.Activity) -> models.Activity | None:
    """Find the Garmin strength activity best overlapping this session's time
    window (±30 min tolerance) and link it. Returns the linked activity or None."""
    if session.linked_activity_id is not None or not session.start_ts:
        return None
    s_start = _parse_ts(session.start_ts)
    s_end = _parse_ts(session.ended_ts) or s_start
    if s_start is None:
        return None

    from datetime import timedelta

    tol = timedelta(minutes=LINK_TOLERANCE_MIN)
    best: tuple[float, models.Activity] | None = None
    for cand in _link_candidates(db, session):
        c_start = _parse_ts(cand.start_ts)
        if c_start is None:
            continue
        # normalize tz-awareness mismatches
        if (c_start.tzinfo is None) != (s_start.tzinfo is None):
            c_start = c_start.replace(tzinfo=s_start.tzinfo)
        c_end = c_start + timedelta(minutes=cand.duration_min or 0)
        overlap = _overlap_min(s_start - tol, s_end + tol, c_start, c_end)
        if overlap > 0 and (best is None or overlap > best[0]):
            best = (overlap, cand)
    if best is None:
        return None
    link(db, session, best[1])
    return best[1]


def auto_link_new_activities(db: Session) -> int:
    """Called after a sync: link any unlinked finished sessions to newly
    arrived Garmin strength activities."""
    sessions = db.scalars(
        select(models.Activity).where(
            models.Activity.source == "app",
            models.Activity.status == "finished",
            models.Activity.linked_activity_id.is_(None),
        )
    ).all()
    linked = 0
    for s in sessions:
        if try_auto_link(db, s) is not None:
            linked += 1
    if linked:
        db.commit()
    return linked


def link(db: Session, session: models.Activity, activity: models.Activity) -> None:
    """Attach watch metrics (duration/HR/calories) from a Garmin activity."""
    session.linked_activity_id = activity.id
    if activity.duration_min is not None:
        session.duration_min = activity.duration_min
    session.avg_hr = activity.avg_hr
    session.max_hr = activity.max_hr
    session.calories = activity.calories
    db.commit()


def unlink(db: Session, session: models.Activity) -> None:
    session.linked_activity_id = None
    session.avg_hr = None
    session.max_hr = None
    session.calories = None
    start = _parse_ts(session.start_ts)
    end = _parse_ts(session.ended_ts)
    session.duration_min = (
        round((end - start).total_seconds() / 60, 1) if start and end else None
    )
    db.commit()


def discard_session(db: Session, session: models.Activity) -> None:
    db.query(models.WorkoutSet).filter(
        models.WorkoutSet.activity_id == session.id
    ).delete()
    db.delete(session)
    db.commit()


def session_summary(db: Session, act: models.Activity) -> dict:
    sets = db.scalars(
        select(models.WorkoutSet)
        .where(models.WorkoutSet.activity_id == act.id)
        .order_by(models.WorkoutSet.id)
    ).all()
    working = [s for s in sets if not s.is_warmup]
    exercises = {e.id: e for e in db.scalars(select(models.Exercise)).all()}

    prs = []
    for ws in working:
        if ws.weight_kg is None:
            continue
        if strength.is_new_pr(db, ws, act.date):
            ex = exercises.get(ws.exercise_id)
            prs.append(
                {
                    "exercise_id": ws.exercise_id,
                    "exercise_name": ex.name if ex else "?",
                    "weight_kg": ws.weight_kg,
                    "reps": ws.reps,
                    "e1rm": round(strength.epley_1rm(ws.weight_kg, ws.reps), 1),
                }
            )
    # keep only the best PR per exercise
    best_by_ex: dict[int, dict] = {}
    for p in prs:
        cur = best_by_ex.get(p["exercise_id"])
        if cur is None or (p["e1rm"] or 0) > (cur["e1rm"] or 0):
            best_by_ex[p["exercise_id"]] = p

    return {
        "workout_id": act.id,
        "name": act.name,
        "date": act.date,
        "start_ts": act.start_ts,
        "ended_ts": act.ended_ts,
        "duration_min": act.duration_min,
        "avg_hr": act.avg_hr,
        "max_hr": act.max_hr,
        "calories": act.calories,
        "tonnage_kg": round(sum((s.weight_kg or 0) * s.reps for s in working), 1),
        "total_sets": len(working),
        "total_reps": sum(s.reps for s in working),
        "exercise_count": len({s.exercise_id for s in sets}),
        "prs": list(best_by_ex.values()),
        "muscles": muscles.muscle_intensity(db, activity_ids=[act.id]),
        "linked_activity_id": act.linked_activity_id,
    }
