from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..datasources.factory import get_data_source
from ..db import get_db
from ..services import cardio, strength

router = APIRouter(prefix="/api/workouts", tags=["workouts"])


@router.get("", response_model=list[schemas.ActivityOut])
def list_workouts(
    start: str | None = None,
    end: str | None = None,
    type: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = select(models.Activity)
    if start:
        q = q.where(models.Activity.date >= start)
    if end:
        q = q.where(models.Activity.date <= end)
    if type:
        q = q.where(models.Activity.type == type)
    return db.scalars(q.order_by(models.Activity.date.desc()).limit(limit)).all()


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
                "is_pr": strength.is_new_pr(db, ws, act.date),
            }
        )
    return {
        "activity": schemas.ActivityOut.model_validate(act).model_dump(),
        "sets": set_rows,
        "tonnage_kg": round(sum((s["weight_kg"] or 0) * s["reps"] for s in set_rows), 1),
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


@router.post("/{workout_id}/import-sets")
def import_sets(workout_id: int, db: Session = Depends(get_db)):
    """Prefill workout_sets from the watch's auto-detected exercise sets."""
    act = _get_activity(db, workout_id)
    existing_garmin = db.scalar(
        select(func.count())
        .select_from(models.WorkoutSet)
        .where(
            models.WorkoutSet.activity_id == workout_id,
            models.WorkoutSet.source == "garmin",
        )
    )
    if existing_garmin:
        raise HTTPException(409, "Garmin sets already imported for this workout")

    garmin_sets = get_data_source().fetch_exercise_sets(act.external_id)
    if not garmin_sets:
        raise HTTPException(404, "No auto-detected sets available for this activity")

    # map Garmin exercise-name guesses to catalogue entries (create custom if new)
    by_name = {e.name.lower(): e for e in db.scalars(select(models.Exercise)).all()}
    created = 0
    for gs in garmin_sets:
        name = gs.exercise_name or "Unknown Exercise"
        ex = by_name.get(name.lower())
        if ex is None:
            from ..timeutil import iso_now

            ex = models.Exercise(
                name=name, category="other", is_custom=1, created_at=iso_now()
            )
            db.add(ex)
            db.flush()
            by_name[name.lower()] = ex
        db.add(
            models.WorkoutSet(
                activity_id=workout_id,
                exercise_id=ex.id,
                set_number=gs.set_number,
                reps=gs.reps,
                weight_kg=gs.weight_kg,
                source="garmin",
            )
        )
        created += 1
    db.commit()
    return {"imported": created}


@router.post("/{workout_id}/sets", response_model=schemas.WorkoutSetOut)
def add_set(workout_id: int, body: schemas.WorkoutSetIn, db: Session = Depends(get_db)):
    _get_activity(db, workout_id)
    if not db.get(models.Exercise, body.exercise_id):
        raise HTTPException(404, "Exercise not found")
    next_num = (
        db.scalar(
            select(func.max(models.WorkoutSet.set_number)).where(
                models.WorkoutSet.activity_id == workout_id
            )
        )
        or 0
    ) + 1
    row = models.WorkoutSet(
        activity_id=workout_id, set_number=next_num, source="manual", **body.model_dump()
    )
    db.add(row)
    db.commit()
    return row


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
