from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from ..services.bloodwork import catalogue, out_of_range
from ..timeutil import iso_now

router = APIRouter(prefix="/api/bloodwork", tags=["bloodwork"])


class ResultIn(BaseModel):
    marker: str = Field(min_length=1, max_length=80)
    value: float
    unit: str = Field(min_length=1, max_length=30)
    ref_low: float | None = None
    ref_high: float | None = None


class PanelIn(BaseModel):
    date: str
    lab_name: str | None = None
    note: str | None = None
    results: list[ResultIn] = Field(min_length=1)


def _result_out(r: models.BloodResult) -> dict:
    return {
        "id": r.id,
        "marker": r.marker,
        "value": r.value,
        "unit": r.unit,
        "ref_low": r.ref_low,
        "ref_high": r.ref_high,
        "flag": out_of_range(r.value, r.ref_low, r.ref_high),
    }


def _panel_out(db: Session, p: models.BloodPanel) -> dict:
    results = db.scalars(
        select(models.BloodResult).where(models.BloodResult.panel_id == p.id)
    ).all()
    return {
        "id": p.id,
        "date": p.date,
        "lab_name": p.lab_name,
        "note": p.note,
        "results": [_result_out(r) for r in results],
    }


@router.get("/markers")
def markers():
    return catalogue()


@router.get("/panels")
def list_panels(db: Session = Depends(get_db)):
    panels = db.scalars(
        select(models.BloodPanel).order_by(models.BloodPanel.date.desc())
    ).all()
    return [_panel_out(db, p) for p in panels]


@router.post("/panels")
def add_panel(body: PanelIn, db: Session = Depends(get_db)):
    panel = models.BloodPanel(
        date=body.date, lab_name=body.lab_name, note=body.note, created_at=iso_now()
    )
    db.add(panel)
    db.flush()
    for r in body.results:
        db.add(models.BloodResult(panel_id=panel.id, **r.model_dump()))
    db.commit()
    return _panel_out(db, panel)


@router.delete("/panels/{panel_id}")
def delete_panel(panel_id: int, db: Session = Depends(get_db)):
    panel = db.get(models.BloodPanel, panel_id)
    if not panel:
        raise HTTPException(404, "Panel not found")
    for r in db.scalars(
        select(models.BloodResult).where(models.BloodResult.panel_id == panel_id)
    ):
        db.delete(r)
    db.delete(panel)
    db.commit()
    return {"deleted": panel_id}


@router.get("/history")
def marker_history(marker: str, db: Session = Depends(get_db)):
    rows = db.execute(
        select(models.BloodResult, models.BloodPanel.date)
        .join(models.BloodPanel, models.BloodResult.panel_id == models.BloodPanel.id)
        .where(models.BloodResult.marker == marker)
        .order_by(models.BloodPanel.date)
    ).all()
    return [{"date": d, **_result_out(r)} for r, d in rows]
