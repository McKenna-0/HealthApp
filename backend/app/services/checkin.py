"""Daily check-in: mood/alcohol/caffeine/illness/eating-window per date, plus
streak computation for habit gamification.

DailyCheckin is the source of truth. On every save we write through to
ContextLog rows tagged label='checkin' so correlations/AI summaries keep
working unchanged. Caffeine is captured as cups but written through as mg
(cups * 80) because correlations sum caffeine value as mg.
"""

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..timeutil import iso_now

CAFFEINE_MG_PER_CUP = 80.0
CHECKIN_MARKER = "checkin"


def upsert_checkin(db: Session, day: str, body: "schemas.CheckinIn") -> models.DailyCheckin:
    row = db.get(models.DailyCheckin, day)
    if row is None:
        row = models.DailyCheckin(date=day)
        db.add(row)
    row.ts = iso_now()
    row.mood = body.mood
    row.alcohol_units = body.alcohol_units
    row.caffeine_cups = body.caffeine_cups
    row.caffeine_last_time = body.caffeine_last_time
    row.illness = body.illness
    row.eating_start = body.eating_start
    row.eating_end = body.eating_end
    row.note = body.note
    _sync_context(db, row)
    if body.weight_kg is not None:
        _upsert_weight(db, day, body.weight_kg)
    db.commit()
    return row


def _sync_context(db: Session, row: models.DailyCheckin) -> None:
    """Upsert/delete label='checkin' ContextLog rows to mirror the check-in.
    Never touches rows without the marker."""
    desired: dict[str, tuple[float, str | None]] = {}
    if row.mood is not None:
        desired["mood"] = (float(row.mood), None)
    if row.alcohol_units > 0:
        desired["alcohol"] = (row.alcohol_units, None)
    if row.caffeine_cups > 0:
        desired["caffeine"] = (row.caffeine_cups * CAFFEINE_MG_PER_CUP, row.caffeine_last_time)
    if row.illness:
        desired["illness"] = (1.0, None)

    existing = {
        c.type: c
        for c in db.scalars(
            select(models.ContextLog).where(
                models.ContextLog.date == row.date,
                models.ContextLog.label == CHECKIN_MARKER,
            )
        )
    }
    for ctype, (value, note) in desired.items():
        cur = existing.pop(ctype, None)
        if cur is None:
            db.add(
                models.ContextLog(
                    date=row.date, ts=iso_now(), type=ctype,
                    value=value, label=CHECKIN_MARKER, note=note,
                )
            )
        else:
            cur.value = value
            cur.note = note
            cur.ts = iso_now()
    for leftover in existing.values():
        db.delete(leftover)


def _upsert_weight(db: Session, day: str, kg: float) -> None:
    """Same semantics as routers/weight.py::add_weight (manual upsert per date)."""
    existing = db.scalar(
        select(models.WeightLog).where(
            models.WeightLog.date == day, models.WeightLog.source == "manual"
        )
    )
    if existing:
        existing.weight_kg = kg
        existing.ts = iso_now()
    else:
        db.add(
            models.WeightLog(date=day, ts=iso_now(), weight_kg=kg, source="manual")
        )


def _time_part(ts: str) -> str | None:
    """'2026-07-20T13:05:00+01:00' or '2026-07-20 13:05' -> '13:05'."""
    try:
        return datetime.fromisoformat(ts).strftime("%H:%M")
    except ValueError:
        return None


def derive_eating_window(
    db: Session, day: str
) -> tuple[str | None, str | None, float | None]:
    """(first_meal_hhmm, last_meal_hhmm, fasting_hours) estimated from FoodLog
    logging timestamps. fasting_hours = previous day's last meal -> this day's
    first meal. NOTE: ts is logging time, not eating time — treat as estimate."""
    rows = db.scalars(
        select(models.FoodLog.ts).where(models.FoodLog.date == day)
    ).all()
    times = sorted(t for t in (_time_part(ts) for ts in rows) if t)
    start = times[0] if times else None
    end = times[-1] if times else None

    fasting = None
    if start:
        prev_day = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
        prev_rows = db.scalars(
            select(models.FoodLog.ts).where(models.FoodLog.date == prev_day)
        ).all()
        prev_times = sorted(t for t in (_time_part(ts) for ts in prev_rows) if t)
        if prev_times:
            prev_end = datetime.fromisoformat(f"{prev_day}T{prev_times[-1]}")
            first = datetime.fromisoformat(f"{day}T{start}")
            fasting = round((first - prev_end).total_seconds() / 3600, 1)
    return start, end, fasting


def compute_streaks(db: Session, today: date) -> dict:
    """Streak day = >=1 food entry AND check-in row. Grace rule: an unfinished
    today doesn't break the streak; it just doesn't count yet."""
    food_dates = set(db.scalars(select(models.FoodLog.date).distinct()))
    checkin_dates = set(db.scalars(select(models.DailyCheckin.date)))
    complete = food_dates & checkin_dates

    today_s = today.isoformat()
    today_complete = today_s in complete

    # current streak: walk backward
    current = 0
    d = today if today_complete else today - timedelta(days=1)
    while d.isoformat() in complete:
        current += 1
        d -= timedelta(days=1)

    # longest streak: single pass over sorted complete days
    longest = 0
    run = 0
    prev: date | None = None
    for ds in sorted(complete):
        cur = date.fromisoformat(ds)
        run = run + 1 if (prev is not None and cur - prev == timedelta(days=1)) else 1
        longest = max(longest, run)
        prev = cur

    week = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        ds = d.isoformat()
        week.append(
            {
                "date": ds,
                "weekday": d.strftime("%a"),
                "food_logged": ds in food_dates,
                "checkin_done": ds in checkin_dates,
                "complete": ds in complete,
            }
        )

    return {
        "current_streak": current,
        "longest_streak": longest,
        "today_complete": today_complete,
        "week": week,
    }
