from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..timeutil import iso_now

router = APIRouter(prefix="/api/weight", tags=["weight"])


@router.get("", response_model=list[schemas.WeightOut])
def list_weights(
    start: str | None = None, end: str | None = None, db: Session = Depends(get_db)
):
    q = select(models.WeightLog)
    if start:
        q = q.where(models.WeightLog.date >= start)
    if end:
        q = q.where(models.WeightLog.date <= end)
    return db.scalars(q.order_by(models.WeightLog.date)).all()


@router.post("", response_model=schemas.WeightOut)
def add_weight(body: schemas.WeightIn, db: Session = Depends(get_db)):
    existing = db.scalar(
        select(models.WeightLog).where(
            models.WeightLog.date == body.date, models.WeightLog.source == "manual"
        )
    )
    if existing:
        existing.weight_kg = body.weight_kg
        existing.note = body.note
        existing.ts = iso_now()
        db.commit()
        return existing
    row = models.WeightLog(
        date=body.date,
        ts=iso_now(),
        weight_kg=body.weight_kg,
        source="manual",
        note=body.note,
    )
    db.add(row)
    db.commit()
    return row


@router.delete("/{weight_id}")
def delete_weight(weight_id: int, db: Session = Depends(get_db)):
    row = db.get(models.WeightLog, weight_id)
    if not row:
        raise HTTPException(404, "Not found")
    db.delete(row)
    db.commit()
    return {"deleted": weight_id}
