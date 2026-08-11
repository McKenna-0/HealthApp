from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..services.weight import upsert_manual_weight

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
    return upsert_manual_weight(db, body.date, body.weight_kg, body.note)


@router.delete("/{weight_id}")
def delete_weight(weight_id: int, db: Session = Depends(get_db)):
    row = db.get(models.WeightLog, weight_id)
    if not row:
        raise HTTPException(404, "Not found")
    db.delete(row)
    db.commit()
    return {"deleted": weight_id}
