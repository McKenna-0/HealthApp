"""Write proposals.

The whole point of this path is that the agent cannot write. So the tests that
matter are the negative ones: proposing must leave the health tables untouched,
confirming must apply exactly once no matter how many times it's called, and
rejecting must leave nothing behind.
"""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.db import Base, get_db
from app.main import app
from app.services import ai_chat, ai_tools
from app.services.ai_client import Provider
from app.services.ai_tools import ToolError
from app.timeutil import today_local


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def db(engine):
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


@pytest.fixture
def client(db):
    def override():
        db.expire_all()
        yield db

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def session(db):
    return ai_chat.create_session(
        db, Provider(base_url="https://example.test/v1", api_key="k", model="m")
    )


TODAY = today_local().isoformat()


def _counts(db):
    return {
        "weight": len(db.scalars(select(models.WeightLog)).all()),
        "food": len(db.scalars(select(models.FoodLog)).all()),
        "context": len(db.scalars(select(models.ContextLog)).all()),
    }


# ---- proposing writes nothing ----------------------------------------------------


def test_proposing_leaves_every_health_table_untouched(db, session):
    ai_tools.propose_log_weight(db, session.id, TODAY, 78.4)
    ai_tools.propose_log_food(db, session.id, TODAY, "lunch", "Chicken salad", 450)
    ai_tools.propose_log_context(db, session.id, TODAY, "alcohol", value=3)

    assert _counts(db) == {"weight": 0, "food": 0, "context": 0}
    assert len(ai_chat.list_pending_actions(db, session.id)) == 3
    assert {a.status for a in ai_chat.list_pending_actions(db, session.id)} == {"pending"}


def test_proposal_tells_the_model_it_has_not_saved(db, session):
    out = ai_tools.propose_log_weight(db, session.id, TODAY, 78.4)
    assert out["status"] == "pending_user_confirmation"
    assert "78.4 kg" in out["summary_text"]
    assert any("not been saved" in n or "Nothing has been saved" in n for n in out["notices"])


def test_summaries_are_specific_enough_to_confirm_blind(db, session):
    weight = ai_tools.propose_log_weight(db, session.id, "2026-08-01", 78.45)
    food = ai_tools.propose_log_food(db, session.id, "2026-08-01", "dinner", "Steak", 620, 250)
    ctx = ai_tools.propose_log_context(db, session.id, "2026-08-01", "alcohol", value=2)

    assert weight["summary_text"] == "Log 78.45 kg for 2026-08-01"
    assert food["summary_text"] == "Log 'Steak' (620 kcal, 250g) as dinner on 2026-08-01"
    assert ctx["summary_text"] == "Log alcohol 2.0 on 2026-08-01"


# ---- bad proposals are refused, not staged ---------------------------------------


def test_impossible_weight_is_rejected_with_the_ui_s_own_bounds(db, session):
    with pytest.raises(ToolError, match="weight_kg"):
        ai_tools.propose_log_weight(db, session.id, TODAY, 4.0)
    assert ai_chat.list_pending_actions(db, session.id) == []


def test_future_dates_are_refused(db, session):
    with pytest.raises(ToolError, match="future"):
        ai_tools.propose_log_weight(db, session.id, "2099-01-01", 78.0)
    assert ai_chat.list_pending_actions(db, session.id) == []


def test_unknown_meal_is_refused(db, session):
    with pytest.raises(ToolError, match="meal"):
        ai_tools.propose_log_food(db, session.id, TODAY, "brunch", "Eggs", 300)


def test_unknown_context_type_is_refused(db, session):
    with pytest.raises(ToolError, match="type"):
        ai_tools.propose_log_context(db, session.id, TODAY, "vibes", value=1)


def test_write_tool_without_a_session_is_refused(db):
    """Nobody could ever confirm a proposal with no conversation attached."""
    with pytest.raises(ToolError, match="saved chat session"):
        ai_tools.dispatch(db, "propose_log_weight", {"date": TODAY, "weight_kg": 78.0})


def test_read_tools_still_work_without_a_session(db):
    assert ai_tools.dispatch(db, "get_data_inventory", {})["trace_summary"]


# ---- confirming ------------------------------------------------------------------


def test_confirm_writes_exactly_one_row_through_the_normal_service(db, session, client):
    out = ai_tools.propose_log_weight(db, session.id, TODAY, 78.4, note="after run")
    resp = client.post(f"/api/ai/pending-actions/{out['pending_action_id']}/confirm")

    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"
    assert resp.json()["result"]["table"] == "weight_log"

    db.expire_all()
    rows = db.scalars(select(models.WeightLog)).all()
    assert len(rows) == 1
    assert rows[0].weight_kg == 78.4
    assert rows[0].source == "manual"  # same shape as a hand-entered row
    assert rows[0].note == "after run"


def test_second_confirm_is_refused_and_writes_nothing_more(db, session, client):
    out = ai_tools.propose_log_food(db, session.id, TODAY, "lunch", "Soup", 200)
    first = client.post(f"/api/ai/pending-actions/{out['pending_action_id']}/confirm")
    second = client.post(f"/api/ai/pending-actions/{out['pending_action_id']}/confirm")

    assert first.status_code == 200
    assert second.status_code == 409
    assert "already confirmed" in second.json()["detail"]

    db.expire_all()
    assert len(db.scalars(select(models.FoodLog)).all()) == 1


def test_confirming_food_derives_the_same_row_the_ui_would(db, session, client):
    out = ai_tools.propose_log_food(db, session.id, TODAY, "dinner", "Pasta", 700, 300)
    client.post(f"/api/ai/pending-actions/{out['pending_action_id']}/confirm")

    db.expire_all()
    row = db.scalars(select(models.FoodLog)).one()
    assert (row.meal, row.description, row.calories, row.quantity_g) == (
        "dinner", "Pasta", 700, 300,
    )
    assert row.source == "manual"


def test_confirming_context_writes_the_entry(db, session, client):
    out = ai_tools.propose_log_context(db, session.id, TODAY, "caffeine", value=180, label="coffee")
    client.post(f"/api/ai/pending-actions/{out['pending_action_id']}/confirm")

    db.expire_all()
    row = db.scalars(select(models.ContextLog)).one()
    assert (row.type, row.value, row.label) == ("caffeine", 180, "coffee")


# ---- rejecting -------------------------------------------------------------------


def test_reject_leaves_no_trace_in_the_health_tables(db, session, client):
    out = ai_tools.propose_log_weight(db, session.id, TODAY, 78.4)
    resp = client.post(f"/api/ai/pending-actions/{out['pending_action_id']}/reject")

    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
    db.expire_all()
    assert _counts(db) == {"weight": 0, "food": 0, "context": 0}


def test_rejected_cannot_then_be_confirmed(db, session, client):
    out = ai_tools.propose_log_weight(db, session.id, TODAY, 78.4)
    client.post(f"/api/ai/pending-actions/{out['pending_action_id']}/reject")
    resp = client.post(f"/api/ai/pending-actions/{out['pending_action_id']}/confirm")

    assert resp.status_code == 409
    db.expire_all()
    assert _counts(db)["weight"] == 0


def test_unknown_action_is_404(client):
    assert client.post("/api/ai/pending-actions/999/confirm").status_code == 404


# ---- failure is not reported as success ------------------------------------------


def test_a_failing_write_is_marked_failed_not_confirmed(db, session, client, monkeypatch):
    out = ai_tools.propose_log_weight(db, session.id, TODAY, 78.4)

    def boom(*a, **k):
        raise RuntimeError("disk full")

    monkeypatch.setattr(ai_chat.weight, "upsert_manual_weight", boom)
    resp = client.post(f"/api/ai/pending-actions/{out['pending_action_id']}/confirm")

    assert resp.status_code == 500
    db.expire_all()
    row = db.get(models.AIPendingAction, out["pending_action_id"])
    assert row.status == "failed"
    assert "disk full" in row.resolved_result_json
    assert _counts(db)["weight"] == 0


# ---- the conversation knows what happened ----------------------------------------


def test_session_detail_carries_the_pending_actions(db, session, client):
    ai_tools.propose_log_weight(db, session.id, TODAY, 78.4)
    body = client.get(f"/api/ai/sessions/{session.id}").json()

    assert len(body["pending_actions"]) == 1
    assert body["pending_actions"][0]["status"] == "pending"
    assert body["pending_actions"][0]["payload"]["weight_kg"] == 78.4


def test_next_turn_tells_the_model_what_was_confirmed(db, session, client):
    """The user resolves a proposal outside the conversation, so without this the
    model would keep insisting it is still waiting."""
    from app.services import ai_agent

    out = ai_tools.propose_log_weight(db, session.id, TODAY, 78.4)
    client.post(f"/api/ai/pending-actions/{out['pending_action_id']}/confirm")

    db.expire_all()
    joined = " ".join(m["content"] for m in ai_agent.system_messages(db, session.id))
    assert "78.4 kg" in joined
    assert "confirmed" in joined


def test_no_proposal_means_no_extra_system_message(db, session):
    from app.services import ai_agent

    assert len(ai_agent.system_messages(db, session.id)) == 2


def test_deleting_a_chat_drops_drafts_but_keeps_confirmed_entries(db, session, client):
    confirmed = ai_tools.propose_log_weight(db, session.id, TODAY, 78.4)
    ai_tools.propose_log_food(db, session.id, TODAY, "lunch", "Soup", 200)
    client.post(f"/api/ai/pending-actions/{confirmed['pending_action_id']}/confirm")

    client.delete(f"/api/ai/sessions/{session.id}")

    db.expire_all()
    assert db.scalars(select(models.AIPendingAction)).all() == []
    # the logged weight is the user's data now, not the chat's
    assert len(db.scalars(select(models.WeightLog)).all()) == 1


# ---- schema hygiene --------------------------------------------------------------


def test_every_write_tool_is_registered_and_declared():
    names = {t["function"]["name"] for t in ai_tools.TOOL_SCHEMAS}
    assert ai_tools.WRITE_TOOLS <= names
    assert ai_tools.WRITE_TOOLS <= set(ai_tools.TOOL_REGISTRY)


def test_schemas_still_fit_the_per_turn_budget():
    assert len(json.dumps(ai_tools.TOOL_SCHEMAS)) < 12000


def test_prompt_forbids_claiming_a_write_happened(db):
    from app.services import ai_agent

    prompt = ai_agent.system_messages(db)[0]["content"]
    assert "propose_" in prompt
    assert "Never say it has been logged" in prompt
