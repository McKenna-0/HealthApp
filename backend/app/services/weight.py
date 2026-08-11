"""Manual weight entry.

Extracted from the weight router so the AI agent's confirmed write-proposals go
through exactly the same upsert the UI uses - one date+manual row, updated in
place rather than duplicated."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..timeutil import iso_now


def upsert_manual_weight(
    db: Session, date: str, weight_kg: float, note: str | None = None
) -> models.WeightLog:
    existing = db.scalar(
        select(models.WeightLog).where(
            models.WeightLog.date == date, models.WeightLog.source == "manual"
        )
    )
    if existing:
        existing.weight_kg = weight_kg
        existing.note = note
        existing.ts = iso_now()
        db.commit()
        return existing

    row = models.WeightLog(
        date=date,
        ts=iso_now(),
        weight_kg=weight_kg,
        source="manual",
        note=note,
    )
    db.add(row)
    db.commit()
    return row
