from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..services import checkin as checkin_svc
from ..timeutil import today_local

router = APIRouter(prefix="/api/checkin", tags=["checkin"])


def _response(db: Session, day: str) -> schemas.CheckinResponse:
    row = db.get(models.DailyCheckin, day)
    start, end, fasting = checkin_svc.derive_eating_window(db, day)
    manual_weight = db.scalar(
        select(models.WeightLog.weight_kg).where(
            models.WeightLog.date == day, models.WeightLog.source == "manual"
        )
    )
    return schemas.CheckinResponse(
        exists=row is not None,
        checkin=schemas.CheckinOut.model_validate(row) if row else None,
        derived_eating_start=start,
        derived_eating_end=end,
        fasting_hours=fasting,
        weight_kg=manual_weight,
    )


@router.get("", response_model=schemas.CheckinResponse)
def get_checkin(date: str | None = None, db: Session = Depends(get_db)):
    return _response(db, date or today_local().isoformat())


@router.get("/streak", response_model=schemas.StreakOut)
def get_streak(db: Session = Depends(get_db)):
    return checkin_svc.compute_streaks(db, today_local())


@router.put("/{date}", response_model=schemas.CheckinResponse)
def put_checkin(date: str, body: schemas.CheckinIn, db: Session = Depends(get_db)):
    checkin_svc.upsert_checkin(db, date, body)
    return _response(db, date)
