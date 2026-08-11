"""Context log queries and writes.

Extracted from the context router so the AI agent's tools and confirmed
write-proposals share one implementation with the UI."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..timeutil import iso_now

CONTEXT_TYPES = ("alcohol", "caffeine", "mood", "illness", "supplement", "note")


def list_entries(
    db: Session,
    start: str | None = None,
    end: str | None = None,
    types: list[str] | None = None,
) -> list[models.ContextLog]:
    q = select(models.ContextLog)
    if start:
        q = q.where(models.ContextLog.date >= start)
    if end:
        q = q.where(models.ContextLog.date <= end)
    if types:
        q = q.where(models.ContextLog.type.in_(types))
    return list(
        db.scalars(q.order_by(models.ContextLog.date, models.ContextLog.ts)).all()
    )


def add_entry(
    db: Session,
    date: str,
    type: str,
    value: float | None = None,
    label: str | None = None,
    note: str | None = None,
) -> models.ContextLog:
    row = models.ContextLog(
        date=date, ts=iso_now(), type=type, value=value, label=label, note=note
    )
    db.add(row)
    db.commit()
    return row
