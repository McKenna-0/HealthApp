from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import settings
from ..datasources.factory import get_data_source
from ..db import get_db
from ..services.ingest import sync_last_days
from ..timeutil import now_local

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("", response_model=schemas.SyncLogOut)
def trigger_sync(days: int = Query(default=7, ge=1, le=365), db: Session = Depends(get_db)):
    return sync_last_days(db, get_data_source(), days)


@router.get("/status", response_model=schemas.SyncStatusOut)
def sync_status(db: Session = Depends(get_db)):
    last = db.scalar(select(models.SyncLog).order_by(models.SyncLog.id.desc()).limit(1))
    last_ok = db.scalar(
        select(models.SyncLog)
        .where(models.SyncLog.status == "ok")
        .order_by(models.SyncLog.id.desc())
        .limit(1)
    )
    # same staleness rule as scheduler._catchup_if_stale
    stale = True
    if last_ok and last_ok.finished_at:
        age = now_local() - datetime.fromisoformat(last_ok.finished_at)
        stale = age.total_seconds() > settings.catchup_after_hours * 3600
    return schemas.SyncStatusOut(
        last_success_at=last_ok.finished_at if last_ok else None,
        last_attempt_at=(last.finished_at or last.started_at) if last else None,
        last_status=last.status if last else None,
        last_error=last.error if last else None,
        stale=stale,
    )


@router.get("/log", response_model=list[schemas.SyncLogOut])
def sync_log(limit: int = Query(default=20, ge=1, le=200), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(models.SyncLog).order_by(models.SyncLog.id.desc()).limit(limit)
    ).all()
    return rows
