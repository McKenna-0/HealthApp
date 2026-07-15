import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..services import strength
from ..services.muscles import MUSCLE_GROUPS
from ..timeutil import iso_now

router = APIRouter(prefix="/api/exercises", tags=["exercises"])


@router.get("", response_model=list[schemas.ExerciseOut])
def list_exercises(q: str | None = None, db: Session = Depends(get_db)):
    stmt = select(models.Exercise).order_by(models.Exercise.name)
    if q:
        stmt = stmt.where(models.Exercise.name.ilike(f"%{q}%"))
    return db.scalars(stmt).all()


@router.post("", response_model=schemas.ExerciseOut)
def add_exercise(body: schemas.ExerciseIn, db: Session = Depends(get_db)):
    existing = db.scalar(
        select(models.Exercise).where(models.Exercise.name.ilike(body.name))
    )
    if existing:
        raise HTTPException(409, f"Exercise '{existing.name}' already exists")
    invalid = (set(body.primary_muscles) | set(body.secondary_muscles)) - set(MUSCLE_GROUPS)
    if invalid:
        raise HTTPException(422, f"Unknown muscle groups: {sorted(invalid)}")
    row = models.Exercise(
        name=body.name,
        category=body.category,
        equipment=body.equipment,
        primary_muscles=json.dumps(body.primary_muscles) if body.primary_muscles else None,
        secondary_muscles=json.dumps(body.secondary_muscles) if body.secondary_muscles else None,
        is_custom=1,
        created_at=iso_now(),
    )
    db.add(row)
    db.commit()
    return row


@router.get("/last-session")
def last_session(ids: str, exclude: int | None = None, db: Session = Depends(get_db)):
    """Ghost data for one or more exercises (ids=1,2,3), used when adding an
    exercise mid-workout. Pass exclude=<workout_id> to skip the current session."""
    try:
        exercise_ids = [int(x) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(422, "ids must be comma-separated integers")
    return strength.last_session_data(db, exercise_ids, before_activity_id=exclude)


@router.get("/{exercise_id}/history")
def history(exercise_id: int, db: Session = Depends(get_db)):
    if not db.get(models.Exercise, exercise_id):
        raise HTTPException(404, "Exercise not found")
    return {
        "history": strength.exercise_history(db, exercise_id),
        "prs": strength.personal_records(db, exercise_id),
    }
