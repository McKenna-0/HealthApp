from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db

router = APIRouter(prefix="/api/settings", tags=["settings"])

DEFAULTS = {
    "calorie_target": None,
    "protein_target_g": None,
    "carbs_target_g": None,
    "fat_target_g": None,
}


class SettingsIn(BaseModel):
    calorie_target: float | None = Field(default=None, ge=0)
    protein_target_g: float | None = Field(default=None, ge=0)
    carbs_target_g: float | None = Field(default=None, ge=0)
    fat_target_g: float | None = Field(default=None, ge=0)


@router.get("")
def get_settings(db: Session = Depends(get_db)):
    rows = db.scalars(select(models.UserSetting)).all()
    out = dict(DEFAULTS)
    for r in rows:
        if r.key in out:
            out[r.key] = float(r.value) if r.value else None
    return out


@router.put("")
def put_settings(body: SettingsIn, db: Session = Depends(get_db)):
    for key, value in body.model_dump().items():
        row = db.get(models.UserSetting, key)
        if row is None:
            db.add(models.UserSetting(key=key, value="" if value is None else str(value)))
        else:
            row.value = "" if value is None else str(value)
    db.commit()
    return get_settings(db)
