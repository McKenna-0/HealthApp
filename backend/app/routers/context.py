from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..services import context as context_service

router = APIRouter(prefix="/api/context", tags=["context"])


@router.get("", response_model=list[schemas.ContextOut])
def list_context(
    start: str | None = None,
    end: str | None = None,
    type: str | None = None,
    db: Session = Depends(get_db),
):
    return context_service.list_entries(
        db, start=start, end=end, types=[type] if type else None
    )


@router.post("", response_model=schemas.ContextOut)
def add_context(body: schemas.ContextIn, db: Session = Depends(get_db)):
    return context_service.add_entry(db, **body.model_dump())


@router.delete("/{ctx_id}")
def delete_context(ctx_id: int, db: Session = Depends(get_db)):
    row = db.get(models.ContextLog, ctx_id)
    if not row:
        raise HTTPException(404, "Not found")
    db.delete(row)
    db.commit()
    return {"deleted": ctx_id}
