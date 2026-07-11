from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..services import strength
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
    row = models.Exercise(**body.model_dump(), is_custom=1, created_at=iso_now())
    db.add(row)
    db.commit()
    return row


@router.get("/{exercise_id}/history")
def history(exercise_id: int, db: Session = Depends(get_db)):
    if not db.get(models.Exercise, exercise_id):
        raise HTTPException(404, "Exercise not found")
    return {
        "history": strength.exercise_history(db, exercise_id),
        "prs": strength.personal_records(db, exercise_id),
    }
