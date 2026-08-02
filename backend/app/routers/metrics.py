from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db

router = APIRouter(prefix="/api", tags=["metrics"])


def _range_query(db: Session, model, start: str | None, end: str | None):
    q = select(model)
    if start:
        q = q.where(model.date >= start)
    if end:
        q = q.where(model.date <= end)
    return db.scalars(q.order_by(model.date)).all()


@router.get("/metrics/daily", response_model=list[schemas.DailyMetricsOut])
def daily_metrics(
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return _range_query(db, models.DailyMetrics, start, end)


@router.get("/sleep", response_model=list[schemas.SleepOut])
def sleep(
    start: str | None = None, end: str | None = None, db: Session = Depends(get_db)
):
    return _range_query(db, models.Sleep, start, end)


@router.get("/activities", response_model=list[schemas.ActivityOut])
def activities(
    start: str | None = None, end: str | None = None, db: Session = Depends(get_db)
):
    return _range_query(db, models.Activity, start, end)


@router.get("/metrics/body-battery/intraday", response_model=list[schemas.IntradayBodyBatteryOut])
def intraday_body_battery(date: str = Query(...), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(models.IntradayBodyBattery)
        .where(models.IntradayBodyBattery.date == date)
        .order_by(models.IntradayBodyBattery.timestamp)
    ).all()
    return rows


@router.get("/metrics/stress/intraday", response_model=list[schemas.IntradayStressOut])
def intraday_stress(date: str = Query(...), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(models.IntradayStress)
        .where(models.IntradayStress.date == date)
        .order_by(models.IntradayStress.timestamp)
    ).all()
    return rows
