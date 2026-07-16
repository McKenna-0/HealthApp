import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.db import Base, get_db
from app.main import app
from app.timeutil import now_local


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


def _log(db, status, finished_at, error=None):
    db.add(
        models.SyncLog(
            started_at=finished_at, finished_at=finished_at, source="garmin",
            days_requested=7, status=status, error=error,
        )
    )
    db.commit()


def test_status_no_logs_is_stale(client):
    r = client.get("/api/sync/status")
    assert r.status_code == 200
    data = r.json()
    assert data["stale"] is True
    assert data["last_success_at"] is None


def test_status_fresh_ok_not_stale(client, db):
    _log(db, "ok", now_local().isoformat())
    data = client.get("/api/sync/status").json()
    assert data["stale"] is False
    assert data["last_status"] == "ok"


def test_status_old_ok_is_stale_and_error_surfaced(client, db):
    from datetime import timedelta

    _log(db, "ok", (now_local() - timedelta(hours=48)).isoformat())
    _log(db, "error", now_local().isoformat(), error="Garmin login failed")
    data = client.get("/api/sync/status").json()
    assert data["stale"] is True
    assert data["last_status"] == "error"
    assert "Garmin login failed" in data["last_error"]
