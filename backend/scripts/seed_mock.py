"""Seed the DB with 90 days of mock data: Garmin-style metrics via the normal
ingest path, plus food and context logs (which are 'manual' tables and don't
come through a DataSource).

Food intake is seeded at ~(calories_out - 350) so the TDEE estimator has a
known deficit to recover against the -0.045 kg/day weight trend.

Usage:  uv run python scripts/seed_mock.py [--days 90]
"""

import argparse
import random
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete  # noqa: E402

from app import models  # noqa: E402
from app.datasources.mock_source import MockSource  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.services.ingest import sync_range  # noqa: E402
from app.timeutil import today_local  # noqa: E402

MEALS = [("breakfast", 0.25), ("lunch", 0.30), ("dinner", 0.35), ("snack", 0.10)]
TARGET_DEFICIT = 350


def main(days: int) -> None:
    init_db()
    db = SessionLocal()
    source = MockSource()
    end = today_local()
    start = end - timedelta(days=days - 1)

    print(f"Wiping mock data and seeding {start} .. {end}")
    for table in (models.DailyMetrics, models.Sleep, models.Activity, models.SyncLog):
        db.execute(delete(table))
    db.execute(delete(models.WeightLog).where(models.WeightLog.source == "mock"))
    db.execute(delete(models.FoodLog))
    db.execute(delete(models.ContextLog))
    db.commit()

    log = sync_range(db, source, start, end)
    print(f"Ingest: {log.status}")

    rng = random.Random(1234)
    d = start
    while d <= end:
        metrics = source.fetch_daily_metrics(d)
        target = (metrics.calories_total_out or 2400) - TARGET_DEFICIT + rng.gauss(0, 120)
        for meal, frac in MEALS:
            db.add(
                models.FoodLog(
                    date=d.isoformat(),
                    ts=f"{d.isoformat()}T12:00:00",
                    meal=meal,
                    description=f"Mock {meal}",
                    calories=round(target * frac, 0),
                    logging_complete_day=1,
                )
            )
        if source.is_alcohol_night(d):
            db.add(
                models.ContextLog(
                    date=d.isoformat(),
                    ts=f"{d.isoformat()}T21:00:00",
                    type="alcohol",
                    value=float(rng.randint(2, 6)),
                    note="mock drinks",
                )
            )
        db.add(
            models.ContextLog(
                date=d.isoformat(),
                ts=f"{d.isoformat()}T08:00:00",
                type="caffeine",
                value=float(rng.choice([80, 160, 240])),
            )
        )
        if source.is_ill(d):
            db.add(
                models.ContextLog(
                    date=d.isoformat(),
                    ts=f"{d.isoformat()}T09:00:00",
                    type="illness",
                    value=1.0,
                    note="mock cold",
                )
            )
        d += timedelta(days=1)
    db.commit()
    db.close()
    print("Seed complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=90)
    main(parser.parse_args().days)
