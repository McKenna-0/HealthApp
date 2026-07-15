from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..datasources.factory import get_data_source
from ..db import get_db
from ..services import cardio, muscles, sessions, strength
from ..timeutil import today_local

router = APIRouter(prefix="/api/workouts", tags=["workouts"])


@router.get("", response_model=list[schemas.ActivityOut])
def list_workouts(
    start: str | None = None,
    end: str | None = None,
    type: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    # hide Garmin activities that are linked to an in-app session (their
    # metrics show on the session) and hide in-progress sessions
    linked_ids = select(models.Activity.linked_activity_id).where(
        models.Activity.linked_activity_id.is_not(None)
    )
    q = select(models.Activity).where(
        models.Activity.id.not_in(linked_ids),
        (models.Activity.status.is_(None)) | (models.Activity.status != "active"),
    )
    if start:
        q = q.where(models.Activity.date >= start)
    if end:
        q = q.where(models.Activity.date <= end)
    if type:
        q = q.where(models.Activity.type == type)
    return db.scalars(
        q.order_by(models.Activity.date.desc(), models.Activity.id.desc()).limit(limit)
    ).all()


# ---- sessions (declared before /{workout_id} so paths don't collide) ---------


def _session_payload(db: Session, act: models.Activity, planned: list[dict]) -> dict:
    exercise_ids = [p["exercise_id"] for p in planned]
    ghosts = strength.last_session_data(db, exercise_ids, before_activity_id=act.id)
    return {
        "activity": schemas.ActivityOut.model_validate(act).model_dump(),
        "planned_exercises": planned,
        "ghosts": ghosts,
    }


@router.post("/sessions")
def create_session(body: schemas.SessionCreateIn, db: Session = Depends(get_db)):
    if sessions.get_active_session(db) is not None:
        raise HTTPException(409, "A workout is already in progress")
    try:
        act, planned = sessions.create_session(
            db,
            name=body.name,
            routine_id=body.routine_id,
            repeat_workout_id=body.repeat_workout_id,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
    return _session_payload(db, act, planned)


@router.get("/sessions/active")
def active_session(db: Session = Depends(get_db)):
    act = sessions.get_active_session(db)
    if act is None:
        return {"active": None}
    planned = sessions.planned_exercises(db, act)
    sets = db.scalars(
        select(models.WorkoutSet)
        .where(models.WorkoutSet.activity_id == act.id)
        .order_by(models.WorkoutSet.id)
    ).all()
    payload = _session_payload(db, act, planned)
    payload["sets"] = [
        schemas.WorkoutSetOut.model_validate(ws).model_dump() for ws in sets
    ]
    return {"active": payload}


@router.post("/sessions/{session_id}/finish")
def finish_session(session_id: int, db: Session = Depends(get_db)):
    act = _get_activity(db, session_id)
    if act.status != "active":
        raise HTTPException(409, "Workout is not active")
    sessions.finish_session(db, act)
    return sessions.session_summary(db, act)


@router.delete("/sessions/{session_id}")
def discard_session(session_id: int, db: Session = Depends(get_db)):
    act = _get_activity(db, session_id)
    if act.source != "app":
        raise HTTPException(409, "Only in-app workouts can be discarded")
    sessions.discard_session(db, act)
    return {"deleted": session_id}


# ---- analytics (declared before /{workout_id} so paths don't collide) --------


@router.get("/analytics/strength")
def strength_analytics(
    exercise_id: int | None = None,
    weeks: int = Query(default=12, ge=1, le=104),
    db: Session = Depends(get_db),
):
    out: dict = {"weekly_volume": strength.weekly_volume(db, weeks)}
    if exercise_id is not None:
        out["history"] = strength.exercise_history(db, exercise_id)
        out["prs"] = strength.personal_records(db, exercise_id)
    return out


@router.get("/analytics/cardio")
def cardio_analytics(
    type: str | None = None,
    weeks: int = Query(default=12, ge=1, le=104),
    db: Session = Depends(get_db),
):
    out: dict = {
        "weekly": cardio.weekly_summary(db, weeks, type),
        "load": cardio.training_load_series(db),
    }
    if type:
        out["pace_trend"] = cardio.pace_trend(db, type, weeks)
    return out


@router.get("/analytics/muscles")
def muscle_analytics(
    days: int = Query(default=7, ge=1, le=90), db: Session = Depends(get_db)
):
    from datetime import timedelta

    end = today_local()
    start = end - timedelta(days=days - 1)
    return {
        "days": days,
        "muscles": muscles.muscle_set_counts(db, start.isoformat(), end.isoformat()),
    }


@router.get("/types")
def activity_types(db: Session = Depends(get_db)):
    rows = db.execute(
        select(models.Activity.type, func.count())
        .group_by(models.Activity.type)
        .order_by(func.count().desc())
    ).all()
    return [{"type": r[0], "count": r[1]} for r in rows if r[0]]


# ---- single workout ------------------------------------------------------------


def _get_activity(db: Session, workout_id: int) -> models.Activity:
    row = db.get(models.Activity, workout_id)
    if not row:
        raise HTTPException(404, "Workout not found")
    return row


@router.get("/{workout_id}")
def workout_detail(workout_id: int, db: Session = Depends(get_db)):
    act = _get_activity(db, workout_id)
    sets = db.scalars(
        select(models.WorkoutSet)
        .where(models.WorkoutSet.activity_id == workout_id)
        .order_by(models.WorkoutSet.id)
    ).all()
    exercises = {
        e.id: e for e in db.scalars(select(models.Exercise)).all()
    }
    set_rows = []
    for ws in sets:
        ex = exercises.get(ws.exercise_id)
        set_rows.append(
            {
                **schemas.WorkoutSetOut.model_validate(ws).model_dump(),
                "exercise_name": ex.name if ex else "?",
                "e1rm": round(strength.epley_1rm(ws.weight_kg, ws.reps), 1)
                if ws.weight_kg is not None
                else None,
                "is_pr": (not ws.is_warmup) and strength.is_new_pr(db, ws, act.date),
            }
        )
    return {
        "activity": schemas.ActivityOut.model_validate(act).model_dump(),
        "sets": set_rows,
        "tonnage_kg": round(
            sum(
                (s["weight_kg"] or 0) * s["reps"]
                for s in set_rows
                if not s["is_warmup"]
            ),
            1,
        ),
    }


@router.get("/{workout_id}/laps", response_model=list[schemas.LapOut])
def workout_laps(workout_id: int, db: Session = Depends(get_db)):
    act = _get_activity(db, workout_id)
    cached = db.scalars(
        select(models.ActivityLap)
        .where(models.ActivityLap.activity_id == workout_id)
        .order_by(models.ActivityLap.lap_index)
    ).all()
    if cached:
        return cached
    laps = get_data_source().fetch_activity_laps(act.external_id)
    rows = [
        models.ActivityLap(
            activity_id=workout_id,
            lap_index=lap.lap_index,
            duration_s=lap.duration_s,
            distance_km=lap.distance_km,
            avg_hr=lap.avg_hr,
            avg_speed_mps=lap.avg_speed_mps,
            elevation_gain_m=lap.elevation_gain_m,
        )
        for lap in laps
    ]
    db.add_all(rows)
    db.commit()
    return rows


@router.get("/{workout_id}/hr-zones", response_model=list[schemas.HrZoneOut])
def workout_hr_zones(workout_id: int, db: Session = Depends(get_db)):
    act = _get_activity(db, workout_id)
    cached = db.scalars(
        select(models.ActivityHrZone)
        .where(models.ActivityHrZone.activity_id == workout_id)
        .order_by(models.ActivityHrZone.zone_number)
    ).all()
    if cached:
        return cached
    zones = get_data_source().fetch_activity_hr_zones(act.external_id)
    rows = [
        models.ActivityHrZone(
            activity_id=workout_id,
            zone_number=z.zone_number,
            secs_in_zone=z.secs_in_zone,
            zone_low_boundary=z.zone_low_boundary,
        )
        for z in zones
    ]
    db.add_all(rows)
    db.commit()
    return rows


@router.get("/{workout_id}/summary", response_model=schemas.WorkoutSummaryOut)
def workout_summary(workout_id: int, db: Session = Depends(get_db)):
    act = _get_activity(db, workout_id)
    return sessions.session_summary(db, act)


@router.post("/{workout_id}/link/{activity_id}")
def link_workout(workout_id: int, activity_id: int, db: Session = Depends(get_db)):
    act = _get_activity(db, workout_id)
    if act.source != "app":
        raise HTTPException(409, "Only in-app workouts can be linked")
    target = _get_activity(db, activity_id)
    if target.source == "app":
        raise HTTPException(409, "Cannot link to another in-app workout")
    already = db.scalar(
        select(models.Activity).where(
            models.Activity.linked_activity_id == activity_id,
            models.Activity.id != workout_id,
        )
    )
    if already:
        raise HTTPException(409, "Activity already linked to another workout")
    sessions.link(db, act, target)
    return {"linked": activity_id}


@router.delete("/{workout_id}/link")
def unlink_workout(workout_id: int, db: Session = Depends(get_db)):
    act = _get_activity(db, workout_id)
    if act.linked_activity_id is None:
        raise HTTPException(404, "Workout has no linked activity")
    sessions.unlink(db, act)
    return {"unlinked": workout_id}


@router.post("/{workout_id}/sets", response_model=schemas.SetLogResult)
def add_set(workout_id: int, body: schemas.WorkoutSetIn, db: Session = Depends(get_db)):
    act = _get_activity(db, workout_id)
    if not db.get(models.Exercise, body.exercise_id):
        raise HTTPException(404, "Exercise not found")
    # per-exercise ordinal so ghost matching by set index works
    next_num = (
        db.scalar(
            select(func.max(models.WorkoutSet.set_number)).where(
                models.WorkoutSet.activity_id == workout_id,
                models.WorkoutSet.exercise_id == body.exercise_id,
            )
        )
        or 0
    ) + 1
    row = models.WorkoutSet(
        activity_id=workout_id, set_number=next_num, source="manual", **body.model_dump()
    )
    db.add(row)
    db.commit()

    e1rm = None
    is_pr = False
    delta_weight = None
    delta_reps = None
    if not row.is_warmup:
        if row.weight_kg is not None:
            e1rm = round(strength.epley_1rm(row.weight_kg, row.reps), 1)
            is_pr = strength.is_new_pr(db, row, act.date)
        # compare against the same working-set ordinal from last session
        last = strength.last_session_data(
            db, [body.exercise_id], before_activity_id=workout_id
        ).get(body.exercise_id)
        if last:
            working_ordinal = db.scalar(
                select(func.count())
                .select_from(models.WorkoutSet)
                .where(
                    models.WorkoutSet.activity_id == workout_id,
                    models.WorkoutSet.exercise_id == body.exercise_id,
                    models.WorkoutSet.is_warmup == 0,
                    models.WorkoutSet.id <= row.id,
                )
            )
            prev = next(
                (s for s in last["sets"] if s["set_number"] == working_ordinal), None
            )
            if prev:
                if row.weight_kg is not None and prev["weight_kg"] is not None:
                    delta_weight = round(row.weight_kg - prev["weight_kg"], 2)
                delta_reps = row.reps - prev["reps"]
    return {
        "set": schemas.WorkoutSetOut.model_validate(row).model_dump(),
        "e1rm": e1rm,
        "is_pr": is_pr,
        "delta_weight_kg": delta_weight,
        "delta_reps": delta_reps,
    }


@router.put("/sets/{set_id}", response_model=schemas.WorkoutSetOut)
def update_set(set_id: int, body: schemas.WorkoutSetUpdate, db: Session = Depends(get_db)):
    row = db.get(models.WorkoutSet, set_id)
    if not row:
        raise HTTPException(404, "Set not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    row.source = "manual"  # edited by hand
    db.commit()
    return row


@router.delete("/sets/{set_id}")
def delete_set(set_id: int, db: Session = Depends(get_db)):
    row = db.get(models.WorkoutSet, set_id)
    if not row:
        raise HTTPException(404, "Set not found")
    db.delete(row)
    db.commit()
    return {"deleted": set_id}
