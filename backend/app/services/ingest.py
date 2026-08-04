"""Source-agnostic ingestion: DataSource DTOs -> SQLite upserts + sync_log."""

import logging
from dataclasses import asdict
from datetime import date, timedelta

from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from .. import models
from ..datasources.base import DataSource
from ..timeutil import iso_now, today_local

logger = logging.getLogger(__name__)


def _upsert(db: Session, table, values: dict, index_elements: list[str]):
    stmt = insert(table).values(**values)
    update_cols = {
        k: stmt.excluded[k] for k in values if k not in index_elements
    }
    db.execute(
        stmt.on_conflict_do_update(index_elements=index_elements, set_=update_cols)
    )


def sync_range(db: Session, source: DataSource, start: date, end: date) -> models.SyncLog:
    log = models.SyncLog(
        started_at=iso_now(),
        source=source.name,
        days_requested=(end - start).days + 1,
        status="ok",
    )
    n_metrics = n_sleeps = n_activities = n_weights = 0
    try:
        day = start
        while day <= end:
            if metrics := source.fetch_daily_metrics(day):
                vals = asdict(metrics)
                vals["date"] = metrics.date.isoformat()
                vals.update(source=source.name, synced_at=iso_now())
                _upsert(db, models.DailyMetrics, vals, ["date"])
                n_metrics += 1
            if sleep := source.fetch_sleep(day):
                vals = asdict(sleep)
                vals["date"] = sleep.date.isoformat()
                vals.update(source=source.name, synced_at=iso_now())
                _upsert(db, models.Sleep, vals, ["date"])
                n_sleeps += 1
            for bb in source.fetch_intraday_body_battery(day):
                _upsert(db, models.IntradayBodyBattery, {
                    "date": bb.date.isoformat(),
                    "timestamp": bb.timestamp,
                    "body_battery": bb.body_battery,
                    "source": source.name,
                }, ["date", "timestamp"])
            for st in source.fetch_intraday_stress(day):
                _upsert(db, models.IntradayStress, {
                    "date": st.date.isoformat(),
                    "timestamp": st.timestamp,
                    "stress_level": st.stress_level,
                    "source": source.name,
                }, ["date", "timestamp"])
            day += timedelta(days=1)

        activities = source.fetch_activities(start, end)
        for act in activities:
            vals = asdict(act)
            vals["date"] = act.date.isoformat()
            vals.update(source=source.name, synced_at=iso_now())
            _upsert(db, models.Activity, vals, ["external_id"])
        n_activities = len(activities)

        from . import sessions

        sessions.auto_link_new_activities(db)

        weights = source.fetch_weight(start, end)
        for w in weights:
            _upsert(
                db,
                models.WeightLog,
                {
                    "date": w.date.isoformat(),
                    "ts": w.ts,
                    "weight_kg": w.weight_kg,
                    "source": source.name,
                    "note": None,
                },
                ["date", "source"],
            )
        n_weights = len(weights)
    except Exception as exc:  # noqa: BLE001 - sync must never crash the app
        logger.exception("Sync failed")
        db.rollback()
        log.status = "error"
        log.error = f"{type(exc).__name__}: {exc}"

    log.finished_at = iso_now()
    log.metrics_synced = n_metrics
    log.sleeps_synced = n_sleeps
    log.activities_synced = n_activities
    log.weights_synced = n_weights
    db.add(log)
    db.commit()
    return log


def sync_last_days(db: Session, source: DataSource, days: int) -> models.SyncLog:
    end = today_local()
    start = end - timedelta(days=days - 1)
    return sync_range(db, source, start, end)
