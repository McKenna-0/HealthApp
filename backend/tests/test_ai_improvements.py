"""Privacy routing on the non-agent AI path, truncated replies, the slimmed
strength overview, and HR-zone caching at sync time. No network anywhere."""

from datetime import timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app import models
from app.config import settings
from app.datasources.base import HrZoneDTO
from app.db import Base
from app.services import ai_agent, ai_client, ai_tools, ingest
from app.services.ai_client import Provider
from app.timeutil import today_local


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


# ---- privacy routing on chat() ---------------------------------------------------


class _Resp:
    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": {"content": "ok"}}]}


def _capture_post(monkeypatch):
    sent = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        sent["url"] = url
        sent["json"] = json
        return _Resp()

    monkeypatch.setattr(ai_client.httpx, "post", fake_post)
    return sent


def test_report_path_sends_the_zdr_block_to_openrouter(monkeypatch):
    """chat() carries the health report and the chat title. It went out with no
    provider block at all while the agent loop next to it sent one."""
    monkeypatch.setattr(settings, "ai_api_key", "k")
    monkeypatch.setattr(settings, "ai_base_url", "https://openrouter.ai/api/v1")
    monkeypatch.setattr(settings, "ai_require_zdr", True)
    sent = _capture_post(monkeypatch)

    ai_client.chat([{"role": "user", "content": "hi"}])

    assert sent["json"]["provider"] == {"data_collection": "deny", "require_parameters": True}


def test_report_path_omits_the_block_for_other_hosts(monkeypatch):
    """Other OpenAI-compatible servers reject unknown top-level fields."""
    monkeypatch.setattr(settings, "ai_api_key", "k")
    monkeypatch.setattr(settings, "ai_base_url", "http://localhost:11434/v1")
    monkeypatch.setattr(settings, "ai_require_zdr", True)
    sent = _capture_post(monkeypatch)

    ai_client.chat([{"role": "user", "content": "hi"}])

    assert "provider" not in sent["json"]


# ---- truncated replies -----------------------------------------------------------


def test_reply_cut_off_at_the_length_limit_says_so(db, monkeypatch):
    script = [
        {"choices": [{"delta": {"content": "Your sleep has been"}}]},
        {"choices": [{"delta": {}, "finish_reason": "length"}]},
    ]
    monkeypatch.setattr(ai_agent.ai_client, "chat_stream", lambda *a, **k: iter(script))
    messages = ai_agent.system_messages(db) + [{"role": "user", "content": "sleep?"}]
    events = list(ai_agent.run_agent_turn(
        db, messages, Provider(base_url="https://example.test/v1", api_key="k", model="m")
    ))

    done = [e for e in events if e.type == "message_done"][0]
    assert done.data["warning"] == "truncated"
    assert "cut off" in messages[-1]["content"]
    assert messages[-1]["content"].startswith("Your sleep has been")


# ---- strength overview -----------------------------------------------------------


def test_strength_overview_lists_recent_exercises_and_says_how_many_exist(db):
    n = ai_tools.MAX_OVERVIEW_EXERCISES + 15
    for i in range(n):
        ex = models.Exercise(name=f"Lift {i:03d}", category="push", created_at="x")
        db.add(ex)
        db.flush()
        act = models.Activity(
            external_id=f"a{i}", date=f"2025-{1 + i // 28:02d}-{1 + i % 28:02d}",
            type="strength_training", source="manual", synced_at="x",
        )
        db.add(act)
        db.flush()
        db.add(models.WorkoutSet(
            activity_id=act.id, exercise_id=ex.id, set_number=1, reps=5, weight_kg=50.0,
        ))
    db.commit()

    out = ai_tools.get_strength_progress(db)
    assert out["total_exercises"] == n
    assert len(out["exercises"]) == ai_tools.MAX_OVERVIEW_EXERCISES
    assert any(str(n) in note for note in out["notices"])
    # the most recently trained survive, the oldest are the ones left out
    names = {e["name"] for e in out["exercises"]}
    assert f"Lift {n - 1:03d}" in names
    assert "Lift 000" not in names


# ---- HR zone caching -------------------------------------------------------------


class _ZoneSource:
    name = "garmin"

    def __init__(self, fail=False):
        self.calls: list[str] = []
        self.fail = fail

    def fetch_activity_hr_zones(self, external_id):
        self.calls.append(external_id)
        if self.fail:
            raise RuntimeError("429")
        return [
            HrZoneDTO(zone_number=1, secs_in_zone=300.0, zone_low_boundary=100),
            HrZoneDTO(zone_number=2, secs_in_zone=900.0, zone_low_boundary=120),
        ]


def _activity(db, ext, type_="running", days_ago=1, avg_hr=150):
    act = models.Activity(
        external_id=ext, date=(today_local() - timedelta(days=days_ago)).isoformat(),
        type=type_, avg_hr=avg_hr, source="garmin", synced_at="x",
    )
    db.add(act)
    db.commit()
    return act


def test_sync_caches_zones_for_recent_cardio_only(db):
    run = _activity(db, "run1")
    _activity(db, "lift1", type_="strength_training")
    _activity(db, "old1", days_ago=ingest.ZONE_BACKFILL_DAYS + 30)
    src = _ZoneSource()

    assert ingest.cache_missing_hr_zones(db, src) == 1
    assert src.calls == ["run1"]
    zones = db.scalars(
        select(models.ActivityHrZone).where(models.ActivityHrZone.activity_id == run.id)
    ).all()
    assert len(zones) == 2

    # second sync has nothing left to do, so it makes no Garmin calls
    assert ingest.cache_missing_hr_zones(db, src) == 0
    assert src.calls == ["run1"]


def test_zone_backfill_is_capped_per_sync(db):
    for i in range(ingest.ZONE_BACKFILL_PER_SYNC + 5):
        _activity(db, f"run{i}", days_ago=i + 1)
    src = _ZoneSource()

    ingest.cache_missing_hr_zones(db, src)
    assert len(src.calls) == ingest.ZONE_BACKFILL_PER_SYNC
    assert src.calls[0] == "run0"  # newest first


def test_zone_fetch_failure_does_not_raise(db):
    _activity(db, "run1")
    _activity(db, "run2", days_ago=2)
    src = _ZoneSource(fail=True)

    assert ingest.cache_missing_hr_zones(db, src) == 0
    assert len(src.calls) == 1  # gave up after the first failure
