from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..services import analytics, correlations
from ..timeutil import today_local

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _default_range(start: str | None, end: str | None, days: int = 30) -> tuple[str, str]:
    e = end or today_local().isoformat()
    s = start or (today_local() - timedelta(days=days - 1)).isoformat()
    return s, e


@router.get("/energy-balance")
def energy_balance(
    start: str | None = None, end: str | None = None, db: Session = Depends(get_db)
):
    s, e = _default_range(start, end)
    return analytics.energy_balance(db, s, e)


@router.get("/weight-trend")
def weight_trend(
    start: str | None = None, end: str | None = None, db: Session = Depends(get_db)
):
    s, e = _default_range(start, end, days=90)
    days = analytics._date_range(s, e)
    weights = analytics.daily_weights(db, s, e)
    trend = analytics.ewma_trend(weights, days)
    return [
        {"date": d, "weight": weights.get(d), "trend": trend.get(d)}
        for d in days
        if d in trend or d in weights
    ]


@router.get("/tdee")
def tdee(
    window: int = Query(default=28, ge=14, le=120),
    end: str | None = None,
    db: Session = Depends(get_db),
):
    return analytics.estimate_tdee(db, end or today_local().isoformat(), window)


@router.get("/correlations")
def correlation_insights(
    days: int = Query(default=90, ge=30, le=365), db: Session = Depends(get_db)
):
    return correlations.compute_insights(db, days)


@router.get("/dashboard")
def dashboard(
    days: int = Query(default=30, ge=7, le=365),
    end: str | None = None,
    db: Session = Depends(get_db),
):
    return analytics.dashboard(db, end or today_local().isoformat(), days)
