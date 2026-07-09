from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..datasources.factory import get_data_source
from ..db import get_db
from ..services.ingest import sync_last_days

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("", response_model=schemas.SyncLogOut)
def trigger_sync(days: int = Query(default=7, ge=1, le=365), db: Session = Depends(get_db)):
    return sync_last_days(db, get_data_source(), days)


@router.get("/log", response_model=list[schemas.SyncLogOut])
def sync_log(limit: int = Query(default=20, ge=1, le=200), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(models.SyncLog).order_by(models.SyncLog.id.desc()).limit(limit)
    ).all()
    return rows
