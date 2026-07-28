import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.db import Base, get_db
from app.main import app


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


@pytest.fixture
def client(db):
    def override():
        yield db

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


BODY = {
    "mood": 4,
    "alcohol_units": 2,
    "caffeine_cups": 3,
    "caffeine_last_time": "14:30",
    "illness": 0,
}


def test_put_creates_and_get_returns(client, db):
    r = client.put("/api/checkin/2026-07-20", json=BODY)
    assert r.status_code == 200
    data = r.json()
    assert data["exists"] is True
    assert data["checkin"]["mood"] == 4
    assert data["checkin"]["caffeine_last_time"] == "14:30"

    g = client.get("/api/checkin?date=2026-07-20").json()
    assert g["exists"] is True
    assert g["checkin"]["alcohol_units"] == 2


def test_put_updates_no_duplicate(client, db):
    client.put("/api/checkin/2026-07-20", json=BODY)
    first_ts = db.get(models.DailyCheckin, "2026-07-20").ts
    client.put("/api/checkin/2026-07-20", json={**BODY, "mood": 2})
    rows = db.scalars(select(models.DailyCheckin)).all()
    assert len(rows) == 1
    assert rows[0].mood == 2
    assert rows[0].ts >= first_ts


def test_context_write_through(client, db):
    client.put("/api/checkin/2026-07-20", json=BODY)
    ctx = {c.type: c for c in db.scalars(select(models.ContextLog))}
    assert set(ctx) == {"mood", "alcohol", "caffeine"}
    assert all(c.label == "checkin" for c in ctx.values())
    assert ctx["mood"].value == 4
    assert ctx["alcohol"].value == 2
    assert ctx["caffeine"].value == 3 * 80  # cups -> mg
    assert ctx["caffeine"].note == "14:30"


def test_edit_updates_context_rows_in_place(client, db):
    client.put("/api/checkin/2026-07-20", json=BODY)
    client.put("/api/checkin/2026-07-20", json={**BODY, "caffeine_cups": 1})
    rows = db.scalars(select(models.ContextLog)).all()
    assert len(rows) == 3  # no duplicates
    caff = next(c for c in rows if c.type == "caffeine")
    assert caff.value == 80


def test_zeroing_deletes_context_row(client, db):
    client.put("/api/checkin/2026-07-20", json=BODY)
    client.put("/api/checkin/2026-07-20", json={**BODY, "alcohol_units": 0})
    types = {c.type for c in db.scalars(select(models.ContextLog))}
    assert "alcohol" not in types


def test_manual_context_row_survives(client, db):
    db.add(
        models.ContextLog(
            date="2026-07-20", ts="x", type="alcohol", value=5, label=None
        )
    )
    db.commit()
    client.put("/api/checkin/2026-07-20", json={**BODY, "alcohol_units": 0})
    manual = db.scalar(
        select(models.ContextLog).where(models.ContextLog.label.is_(None))
    )
    assert manual is not None
    assert manual.value == 5


def test_weight_upsert(client, db):
    db.add(
        models.WeightLog(
            date="2026-07-20", ts="x", weight_kg=80, source="garmin"
        )
    )
    db.commit()
    client.put("/api/checkin/2026-07-20", json={**BODY, "weight_kg": 78.5})
    rows = db.scalars(select(models.WeightLog)).all()
    by_source = {w.source: w for w in rows}
    assert by_source["manual"].weight_kg == 78.5
    assert by_source["garmin"].weight_kg == 80  # untouched

    # second put updates the same manual row
    client.put("/api/checkin/2026-07-20", json={**BODY, "weight_kg": 78.0})
    assert len(db.scalars(select(models.WeightLog)).all()) == 2

    # prefill echoed in response
    g = client.get("/api/checkin?date=2026-07-20").json()
    assert g["weight_kg"] == 78.0


def test_validation(client):
    assert client.put("/api/checkin/2026-07-20", json={**BODY, "mood": 6}).status_code == 422
    assert (
        client.put(
            "/api/checkin/2026-07-20", json={**BODY, "caffeine_last_time": "9:5"}
        ).status_code
        == 422
    )


def test_derived_eating_window(client, db):
    for ts, day in [
        ("2026-07-19T21:10:00", "2026-07-19"),
        ("2026-07-20T11:20:00", "2026-07-20"),
        ("2026-07-20T19:45:00", "2026-07-20"),
    ]:
        db.add(
            models.FoodLog(
                date=day, ts=ts, meal="dinner", calories=100, logging_complete_day=0
            )
        )
    db.commit()
    g = client.get("/api/checkin?date=2026-07-20").json()
    assert g["derived_eating_start"] == "11:20"
    assert g["derived_eating_end"] == "19:45"
    assert g["fasting_hours"] == pytest.approx(14.2, abs=0.01)


def test_no_food_no_derived(client):
    g = client.get("/api/checkin?date=2026-07-20").json()
    assert g["exists"] is False
    assert g["derived_eating_start"] is None
    assert g["fasting_hours"] is None
