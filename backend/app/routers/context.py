from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..timeutil import iso_now

router = APIRouter(prefix="/api/context", tags=["context"])


@router.get("", response_model=list[schemas.ContextOut])
def list_context(
    start: str | None = None,
    end: str | None = None,
    type: str | None = None,
    db: Session = Depends(get_db),
):
    q = select(models.ContextLog)
    if start:
        q = q.where(models.ContextLog.date >= start)
    if end:
        q = q.where(models.ContextLog.date <= end)
    if type:
        q = q.where(models.ContextLog.type == type)
    return db.scalars(q.order_by(models.ContextLog.date, models.ContextLog.ts)).all()


@router.post("", response_model=schemas.ContextOut)
def add_context(body: schemas.ContextIn, db: Session = Depends(get_db)):
    row = models.ContextLog(ts=iso_now(), **body.model_dump())
    db.add(row)
    db.commit()
    return row


@router.delete("/{ctx_id}")
def delete_context(ctx_id: int, db: Session = Depends(get_db)):
    row = db.get(models.ContextLog, ctx_id)
    if not row:
        raise HTTPException(404, "Not found")
    db.delete(row)
    db.commit()
    return {"deleted": ctx_id}
