from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from ..services import targets
from ..timeutil import today_local

router = APIRouter(prefix="/api/settings", tags=["settings"])

DEFAULTS = {
    "calorie_target": None,
    "protein_target_g": None,
    "carbs_target_g": None,
    "fat_target_g": None,
    "weight_goal_kg": None,
    "weight_goal_rate_kg_per_week": None,
    "weight_goal_start_date": None,
    "weight_goal_start_kg": None,
    "macro_mode": "grams",
    "protein_target_pct": None,
    "carbs_target_pct": None,
    "fat_target_pct": None,
    "daily_balance_target": None,
}


class SettingsIn(BaseModel):
    calorie_target: float | None = Field(default=None, ge=0)
    protein_target_g: float | None = Field(default=None, ge=0)
    carbs_target_g: float | None = Field(default=None, ge=0)
    fat_target_g: float | None = Field(default=None, ge=0)
    weight_goal_kg: float | None = Field(default=None, gt=20, lt=400)
    # Signed: positive to gain, negative to lose, 0 to hold. Bounded well past
    # any sane rate so the UI, not the API, is where guidance happens.
    weight_goal_rate_kg_per_week: float | None = Field(default=None, ge=-3, le=3)
    weight_goal_start_date: str | None = Field(
        default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    weight_goal_start_kg: float | None = Field(default=None, gt=20, lt=400)
    macro_mode: str | None = Field(default=None, pattern="^(grams|percent)$")
    protein_target_pct: float | None = Field(default=None, ge=0, le=100)
    carbs_target_pct: float | None = Field(default=None, ge=0, le=100)
    fat_target_pct: float | None = Field(default=None, ge=0, le=100)
    daily_balance_target: float | None = Field(default=None)


_STRING_KEYS = {"macro_mode", "weight_goal_start_date"}


@router.get("")
def get_settings(db: Session = Depends(get_db)):
    rows = db.scalars(select(models.UserSetting)).all()
    out = dict(DEFAULTS)
    for r in rows:
        if r.key in out:
            if r.key in _STRING_KEYS:
                out[r.key] = r.value if r.value else DEFAULTS[r.key]
            else:
                out[r.key] = float(r.value) if r.value else None
    return out


@router.get("/targets")
def daily_targets(
    date: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Effective targets for a day, with active calories folded into the goal."""
    return targets.resolve(db, date or today_local().isoformat())


@router.put("")
def put_settings(body: SettingsIn, db: Session = Depends(get_db)):
    # Partial update: only keys the caller actually sent are written. The
    # weight-goal editor and the macro-targets form are separate screens
    # writing the same document, and a full-object PUT from either would blank
    # whatever the other one owns.
    for key, value in body.model_dump(exclude_unset=True).items():
        row = db.get(models.UserSetting, key)
        if row is None:
            db.add(models.UserSetting(key=key, value="" if value is None else str(value)))
        else:
            row.value = "" if value is None else str(value)
    db.commit()
    return get_settings(db)
