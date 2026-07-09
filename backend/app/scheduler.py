"""APScheduler jobs + startup catch-up sync.

The laptop sleeps, so cron jobs are best-effort; the startup catch-up (fires
when the last successful sync is older than settings.catchup_after_hours) is
the primary mechanism.
"""

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from . import models
from .config import settings
from .datasources.factory import get_data_source
from .db import SessionLocal
from .services.ingest import sync_last_days
from .timeutil import now_local, tzinfo

logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def _run_sync():
    db = SessionLocal()
    try:
        log = sync_last_days(db, get_data_source(), settings.sync_lookback_days)
        logger.info("Scheduled sync finished: %s", log.status)
    finally:
        db.close()


def _catchup_if_stale():
    db = SessionLocal()
    try:
        last = db.scalar(
            select(models.SyncLog)
            .where(models.SyncLog.status == "ok")
            .order_by(models.SyncLog.id.desc())
            .limit(1)
        )
        stale = True
        if last and last.finished_at:
            age = now_local() - datetime.fromisoformat(last.finished_at)
            stale = age.total_seconds() > settings.catchup_after_hours * 3600
        if stale:
            logger.info("Last sync stale or missing - running catch-up sync")
            sync_last_days(db, get_data_source(), settings.sync_lookback_days)
    except Exception:
        logger.exception("Catch-up sync failed")
    finally:
        db.close()


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone=tzinfo())
    for hour, minute in ((7, 30), (21, 30)):
        _scheduler.add_job(
            _run_sync,
            CronTrigger(hour=hour, minute=minute),
            coalesce=True,
            misfire_grace_time=3600,
            id=f"sync_{hour:02d}{minute:02d}",
        )
    # catch-up shortly after startup so app start doesn't block
    _scheduler.add_job(_catchup_if_stale, "date")
    _scheduler.start()
    logger.info("Scheduler started (cron 07:30 & 21:30 %s)", settings.tz)


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
