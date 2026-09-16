from datetime import date

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.db import Base
from app.services import mfp_sync


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    session.add(models.UserSetting(key="mfp_cookie", value="x=y"))
    session.commit()
    yield session
    session.close()


def test_one_day_failing_does_not_cascade_to_later_days(db, monkeypatch):
    """A day that raises mid-sync used to leave the session in a rolled-back
    state, so every subsequent day in the same range also failed with
    'This Session's transaction has been rolled back...' even though nothing
    was wrong with them."""
    calls = []

    def fake_sync_date(session, cookies, day):
        calls.append(day)
        if day == date(2026, 9, 15):
            raise ValueError("boom")
        return 1

    monkeypatch.setattr(mfp_sync, "sync_date", fake_sync_date)

    result = mfp_sync.sync_range(db, date(2026, 9, 15), date(2026, 9, 16))

    assert calls == [date(2026, 9, 15), date(2026, 9, 16)]
    assert result["entries_synced"] == 1
    assert len(result["errors"]) == 1
    assert "2026-09-15" in result["errors"][0]


def test_add_missing_columns_drops_stale_mfp_unique_index(db, monkeypatch):
    """uq_foodlog_mfp used to enforce MFP sync idempotency, but sync_date()'s
    delete-then-insert already guarantees that - the index only served to
    reject a food logged twice in the same meal, which MFP genuinely allows.
    An existing Dell database still has the index from before this fix,
    so _add_missing_columns() must drop it on the next startup."""
    from app import db as db_module

    db.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_foodlog_mfp "
        "ON food_log(date, meal, description, source) "
        "WHERE source = 'myfitnesspal'"
    ))
    db.commit()

    monkeypatch.setattr(db_module, "engine", db.get_bind())
    db_module._add_missing_columns()

    db.add(models.FoodLog(
        date="2026-09-15", ts="2026-09-15T08:00", meal="breakfast",
        description="Honey, 10g", calories=33.0, protein_g=0.0,
        carbs_g=8.0, fat_g=0.0, logging_complete_day=0, source="myfitnesspal",
    ))
    db.add(models.FoodLog(
        date="2026-09-15", ts="2026-09-15T08:00", meal="breakfast",
        description="Honey, 10g", calories=33.0, protein_g=0.0,
        carbs_g=8.0, fat_g=0.0, logging_complete_day=0, source="myfitnesspal",
    ))
    db.commit()

    rows = db.query(models.FoodLog).filter_by(date="2026-09-15").all()
    assert len(rows) == 2
