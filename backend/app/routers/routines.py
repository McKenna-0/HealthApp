from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..timeutil import iso_now

router = APIRouter(prefix="/api/routines", tags=["routines"])


def _routine_out(db: Session, routine: models.Routine) -> dict:
    rows = db.execute(
        select(models.RoutineExercise, models.Exercise.name)
        .join(models.Exercise, models.RoutineExercise.exercise_id == models.Exercise.id)
        .where(models.RoutineExercise.routine_id == routine.id)
        .order_by(models.RoutineExercise.position)
    ).all()
    return {
        "id": routine.id,
        "name": routine.name,
        "created_at": routine.created_at,
        "last_used_at": routine.last_used_at,
        "exercises": [
            {"exercise_id": re.exercise_id, "name": name, "target_sets": re.target_sets}
            for re, name in rows
        ],
    }


def _replace_exercises(
    db: Session, routine_id: int, exercises: list[schemas.RoutineExerciseIn]
) -> None:
    db.query(models.RoutineExercise).filter(
        models.RoutineExercise.routine_id == routine_id
    ).delete()
    for i, e in enumerate(exercises):
        if not db.get(models.Exercise, e.exercise_id):
            raise HTTPException(404, f"Exercise {e.exercise_id} not found")
        db.add(
            models.RoutineExercise(
                routine_id=routine_id,
                exercise_id=e.exercise_id,
                position=i,
                target_sets=e.target_sets,
            )
        )


@router.get("", response_model=list[schemas.RoutineOut])
def list_routines(db: Session = Depends(get_db)):
    routines = db.scalars(
        select(models.Routine).order_by(models.Routine.name)
    ).all()
    return [_routine_out(db, r) for r in routines]


@router.post("", response_model=schemas.RoutineOut)
def create_routine(body: schemas.RoutineIn, db: Session = Depends(get_db)):
    if db.scalar(select(models.Routine).where(models.Routine.name.ilike(body.name))):
        raise HTTPException(409, "Routine with this name already exists")
    routine = models.Routine(name=body.name, created_at=iso_now())
    db.add(routine)
    db.flush()
    _replace_exercises(db, routine.id, body.exercises)
    db.commit()
    return _routine_out(db, routine)


@router.put("/{routine_id}", response_model=schemas.RoutineOut)
def update_routine(routine_id: int, body: schemas.RoutineIn, db: Session = Depends(get_db)):
    routine = db.get(models.Routine, routine_id)
    if not routine:
        raise HTTPException(404, "Routine not found")
    clash = db.scalar(
        select(models.Routine).where(
            models.Routine.name.ilike(body.name), models.Routine.id != routine_id
        )
    )
    if clash:
        raise HTTPException(409, "Routine with this name already exists")
    routine.name = body.name
    _replace_exercises(db, routine_id, body.exercises)
    db.commit()
    return _routine_out(db, routine)


@router.delete("/{routine_id}")
def delete_routine(routine_id: int, db: Session = Depends(get_db)):
    routine = db.get(models.Routine, routine_id)
    if not routine:
        raise HTTPException(404, "Routine not found")
    db.query(models.RoutineExercise).filter(
        models.RoutineExercise.routine_id == routine_id
    ).delete()
    db.delete(routine)
    db.commit()
    return {"deleted": routine_id}


@router.post("/from-workout/{workout_id}", response_model=schemas.RoutineOut)
def routine_from_workout(workout_id: int, body: dict, db: Session = Depends(get_db)):
    name = (body.get("name") or "").strip()
    if len(name) < 2:
        raise HTTPException(422, "Name required")
    if db.scalar(select(models.Routine).where(models.Routine.name.ilike(name))):
        raise HTTPException(409, "Routine with this name already exists")
    act = db.get(models.Activity, workout_id)
    if not act:
        raise HTTPException(404, "Workout not found")
    sets = db.scalars(
        select(models.WorkoutSet)
        .where(models.WorkoutSet.activity_id == workout_id)
        .order_by(models.WorkoutSet.id)
    ).all()
    if not sets:
        raise HTTPException(409, "Workout has no sets")
    counts: dict[int, int] = {}
    order: list[int] = []
    for ws in sets:
        if ws.exercise_id not in counts:
            counts[ws.exercise_id] = 0
            order.append(ws.exercise_id)
        if not ws.is_warmup:
            counts[ws.exercise_id] += 1

    routine = models.Routine(name=name, created_at=iso_now())
    db.add(routine)
    db.flush()
    for i, ex_id in enumerate(order):
        db.add(
            models.RoutineExercise(
                routine_id=routine.id,
                exercise_id=ex_id,
                position=i,
                target_sets=max(counts[ex_id], 1),
            )
        )
    db.commit()
    return _routine_out(db, routine)
