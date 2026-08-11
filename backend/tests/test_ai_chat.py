"""Streaming chat endpoint and conversation persistence.

Two things are load-bearing here and both are easy to get subtly wrong:
the SSE frames must arrive well-formed and in a usable order, and a stored
conversation must replay into a shape the provider will still accept - which
means an assistant `tool_calls[].id` and the answering `tool_call_id` have to
survive the round trip, including when a turn died halfway through.

No network: `chat_stream` is scripted throughout.
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
from app.routers.ai_chat import get_db_factory
from app.services import ai_agent, ai_chat


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
def client(db, engine):
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        # the stream writes through its own session, so anything this one has
        # already loaded is stale by the time we assert on it
        db.expire_all()
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_db_factory] = lambda: factory
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def configured(db):
    """Provider settings live in the same k/v table the UI writes to."""
    for key, value in (
        ("ai_agent_base_url", "https://openrouter.ai/api/v1"),
        ("ai_agent_api_key", "sk-test"),
        ("ai_agent_model", "test/model"),
    ):
        db.add(models.UserSetting(key=key, value=value))
    db.commit()


# ---- scripted provider -----------------------------------------------------------


def _text_chunks(text: str):
    for ch in text.split(" "):
        yield {"choices": [{"delta": {"content": ch + " "}}]}
    yield {"choices": [{"delta": {}, "finish_reason": "stop"}]}


def _tool_chunks(name: str, arguments: str = "{}", call_id: str = "call_1"):
    yield {"choices": [{"delta": {"tool_calls": [
        {"index": 0, "id": call_id, "function": {"name": name, "arguments": arguments}}
    ]}}]}
    yield {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}


def _script(monkeypatch, *scripts):
    calls = {"sent": []}

    def fake_stream(messages, provider, tools=None, **kw):
        i = len(calls["sent"])
        calls["sent"].append([dict(m) for m in messages])
        if i >= len(scripts):
            raise AssertionError(f"chat_stream called {i + 1}x, only {len(scripts)} scripted")
        return iter(scripts[i])

    monkeypatch.setattr(ai_agent.ai_client, "chat_stream", fake_stream)
    monkeypatch.setattr(ai_chat.ai_client, "chat", lambda *a, **k: "Sleep trend question")
    return calls


def _frames(body: str) -> list[tuple[str, dict]]:
    """Parse the SSE body into (event, data) pairs, asserting each block is
    well-formed on the way through."""
    out = []
    for block in body.split("\n\n"):
        if not block.strip():
            continue
        lines = block.split("\n")
        assert lines[0].startswith("event: "), f"malformed frame: {block!r}"
        assert lines[1].startswith("data: "), f"malformed frame: {block!r}"
        out.append((lines[0][7:], json.loads(lines[1][6:])))
    return out


def _new_session(client) -> int:
    return client.post("/api/ai/sessions").json()["id"]


# ---- session CRUD ----------------------------------------------------------------


def test_create_session_snapshots_the_provider(client, configured):
    body = client.post("/api/ai/sessions").json()
    assert body["model"] == "test/model"
    assert body["provider"] == "https://openrouter.ai/api/v1"
    assert body["title"] is None
    assert body["message_count"] == 0

    assert [s["id"] for s in client.get("/api/ai/sessions").json()] == [body["id"]]


def test_missing_session_is_404_everywhere(client, configured):
    assert client.get("/api/ai/sessions/999").status_code == 404
    assert client.delete("/api/ai/sessions/999").status_code == 404
    assert client.post("/api/ai/sessions/999/messages", json={"message": "hi"}).status_code == 404


def test_delete_takes_the_transcript_with_it(client, configured, db, monkeypatch):
    _script(monkeypatch, list(_text_chunks("all fine")))
    sid = _new_session(client)
    client.post(f"/api/ai/sessions/{sid}/messages", json={"message": "how did I sleep?"})

    assert db.scalars(select(models.AIChatMessage)).all()
    client.delete(f"/api/ai/sessions/{sid}")
    db.expire_all()
    assert db.scalars(select(models.AIChatMessage)).all() == []


# ---- streaming -------------------------------------------------------------------


def test_stream_emits_ordered_wellformed_frames(client, configured, monkeypatch):
    _script(
        monkeypatch,
        list(_tool_chunks("get_data_inventory")),
        list(_text_chunks("You have no data yet.")),
    )
    sid = _new_session(client)
    resp = client.post(f"/api/ai/sessions/{sid}/messages", json={"message": "how did I sleep?"})

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert resp.headers["x-accel-buffering"] == "no"

    events = [name for name, _ in _frames(resp.text)]
    assert events[0] == "start"
    assert events[-1] == "done"
    # the work is announced before the answer that depends on it
    assert events.index("tool_call") < events.index("tool_result") < events.index("token")
    assert events.index("message_done") < events.index("title")


def test_tokens_reassemble_into_the_saved_answer(client, configured, db, monkeypatch):
    _script(monkeypatch, list(_text_chunks("Your average was 7.4 hours.")))
    sid = _new_session(client)
    resp = client.post(f"/api/ai/sessions/{sid}/messages", json={"message": "sleep average?"})

    frames = _frames(resp.text)
    streamed = "".join(d["text"] for n, d in frames if n == "token")
    done = next(d for n, d in frames if n == "message_done")
    assert streamed.strip() == done["content"].strip()

    saved = client.get(f"/api/ai/sessions/{sid}").json()["messages"]
    assert [m["role"] for m in saved] == ["user", "assistant"]
    assert saved[-1]["content"].strip() == "Your average was 7.4 hours."


def test_tool_trace_is_persisted_for_replay_in_the_ui(client, configured, monkeypatch):
    _script(
        monkeypatch,
        list(_tool_chunks("get_data_inventory")),
        list(_text_chunks("nothing there")),
    )
    sid = _new_session(client)
    client.post(f"/api/ai/sessions/{sid}/messages", json={"message": "what data do I have?"})

    saved = client.get(f"/api/ai/sessions/{sid}").json()["messages"]
    assert [m["role"] for m in saved] == ["user", "assistant", "tool", "assistant"]
    assert saved[1]["tool_calls"][0]["name"] == "get_data_inventory"
    assert saved[2]["tool_call_id"] == saved[1]["tool_calls"][0]["id"]
    assert saved[2]["trace_summary"]  # the collapsible line the UI shows


def test_title_is_set_once_and_streamed(client, configured, db, monkeypatch):
    _script(monkeypatch, list(_text_chunks("ok")), list(_text_chunks("ok again")))
    sid = _new_session(client)

    first = client.post(f"/api/ai/sessions/{sid}/messages", json={"message": "q1"})
    assert next(d for n, d in _frames(first.text) if n == "title")["title"] == "Sleep trend question"

    second = client.post(f"/api/ai/sessions/{sid}/messages", json={"message": "q2"})
    # already titled - not re-asked, not re-emitted
    assert [n for n, _ in _frames(second.text) if n == "title"] == []


def test_title_falls_back_to_the_question_when_the_model_is_down(client, configured, db, monkeypatch):
    _script(monkeypatch, list(_text_chunks("ok")))

    def boom(*a, **k):
        raise RuntimeError("no title model")

    monkeypatch.setattr(ai_chat.ai_client, "chat", boom)

    sid = _new_session(client)
    resp = client.post(
        f"/api/ai/sessions/{sid}/messages", json={"message": "why is my resting heart rate rising?"}
    )
    title = next(d for n, d in _frames(resp.text) if n == "title")["title"]
    assert title == "why is my resting heart rate rising?"


# ---- failure modes ---------------------------------------------------------------


def test_unconfigured_provider_fails_before_the_stream_starts(client, db, monkeypatch):
    """A 400 is only possible while the status line is still unwritten."""
    # no settings override and no .env fallback - the developer's own .env would
    # otherwise decide whether this test means anything
    from app.services.ai_client import settings as client_settings

    for field in ("ai_agent_api_key", "ai_api_key", "ai_agent_model"):
        monkeypatch.setattr(client_settings, field, "")

    sid = _new_session(client)
    resp = client.post(f"/api/ai/sessions/{sid}/messages", json={"message": "hello"})
    assert resp.status_code == 400
    assert "not configured" in resp.json()["detail"]


def test_provider_failure_mid_stream_becomes_an_error_frame(client, configured, monkeypatch):
    def explode(*a, **k):
        raise ConnectionError("provider unreachable")

    monkeypatch.setattr(ai_agent.ai_client, "chat_stream", explode)

    sid = _new_session(client)
    resp = client.post(f"/api/ai/sessions/{sid}/messages", json={"message": "hello there"})

    # 200 with an error frame, because the headers are long gone by then
    assert resp.status_code == 200
    events = dict(_frames(resp.text))
    assert "provider unreachable" in events["error"]["message"]
    assert "title" not in events  # a failed turn does not get named


def test_short_message_is_rejected(client, configured):
    sid = _new_session(client)
    assert client.post(f"/api/ai/sessions/{sid}/messages", json={"message": "x"}).status_code == 422


# ---- transcript round-tripping ---------------------------------------------------


def test_resumed_conversation_replays_with_pairing_intact(client, configured, monkeypatch):
    calls = _script(
        monkeypatch,
        list(_tool_chunks("get_data_inventory", call_id="call_abc")),
        list(_text_chunks("first answer")),
        list(_text_chunks("second answer")),
    )
    sid = _new_session(client)
    client.post(f"/api/ai/sessions/{sid}/messages", json={"message": "first question"})
    client.post(f"/api/ai/sessions/{sid}/messages", json={"message": "second question"})

    replayed = calls["sent"][2]
    assert [m["role"] for m in replayed] == [
        "system", "system", "user", "assistant", "tool", "assistant", "user",
    ]
    # the pairing the provider validates
    assert replayed[3]["tool_calls"][0]["id"] == "call_abc"
    assert replayed[4]["tool_call_id"] == "call_abc"
    # system messages are rebuilt, never stored
    assert replayed[0]["content"].startswith("You are an evidence-based")


def test_transcript_answers_a_tool_call_that_never_finished(db):
    """A crash between the assistant message and the tool result is exactly what
    persisting mid-turn buys us - and exactly what breaks the wire format."""
    session = ai_chat.create_session(db, _provider())
    ai_chat.append_message(db, session.id, {"role": "user", "content": "q"})
    ai_chat.append_message(db, session.id, {
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": "orphan", "type": "function",
            "function": {"name": "get_daily_series", "arguments": "{}"},
        }],
    })

    out = ai_chat.transcript(db, session.id)
    assert [m["role"] for m in out] == ["user", "assistant", "tool"]
    assert out[2]["tool_call_id"] == "orphan"
    assert json.loads(out[2]["content"])["error"] == "interrupted"


def test_transcript_drops_a_tool_message_with_no_call(db):
    session = ai_chat.create_session(db, _provider())
    ai_chat.append_message(db, session.id, {"role": "user", "content": "q"})
    ai_chat.append_message(db, session.id, {
        "role": "tool", "tool_call_id": "ghost", "name": "get_daily_series", "content": "{}"
    })

    out = ai_chat.transcript(db, session.id)
    assert [m["role"] for m in out] == ["user"]


def test_transcript_preserves_multiple_calls_in_one_turn(db):
    session = ai_chat.create_session(db, _provider())
    ai_chat.append_message(db, session.id, {"role": "user", "content": "q"})
    ai_chat.append_message(db, session.id, {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": "a", "type": "function", "function": {"name": "t1", "arguments": "{}"}},
            {"id": "b", "type": "function", "function": {"name": "t2", "arguments": "{}"}},
        ],
    })
    for call_id in ("a", "b"):
        ai_chat.append_message(db, session.id, {
            "role": "tool", "tool_call_id": call_id, "name": "t", "content": "{}"
        })

    out = ai_chat.transcript(db, session.id)
    assert [m.get("tool_call_id") for m in out if m["role"] == "tool"] == ["a", "b"]
    assert len(out) == 4  # nothing synthesised


def _provider():
    from app.services.ai_client import Provider

    return Provider(base_url="https://example.test/v1", api_key="k", model="m")


# ---- provider settings + model catalogue -----------------------------------------


def test_status_reports_agent_and_report_models_separately(client, configured):
    body = client.get("/api/ai/status").json()
    assert body["agent_model"] == "test/model"
    assert body["agent_base_url"] == "https://openrouter.ai/api/v1"
    assert "agent_configured" in body and "configured" in body


def test_provider_put_stores_overrides_without_echoing_the_key(client):
    body = client.put(
        "/api/ai/provider",
        json={"base_url": "https://uat.privatemind.com/v1", "api_key": "secret-key", "model": "m1"},
    ).json()

    assert body["api_key_set"] is True
    assert "secret-key" not in json.dumps(body)
    assert body["is_openrouter"] is False
    assert body["privacy_routing"] is False  # OpenRouter-only block stays off


def test_provider_delete_clears_overrides(client, configured):
    assert client.get("/api/ai/provider").json()["overridden"]["ai_agent_model"] is True
    body = client.delete("/api/ai/provider").json()
    assert body["overridden"]["ai_agent_model"] is False


def test_openrouter_gets_the_privacy_block(client, configured):
    assert client.get("/api/ai/provider").json()["privacy_routing"] is True


def test_models_passthrough_normalises_and_filters(client, configured, monkeypatch):
    payload = {"data": [
        {"id": "z/model", "name": "Zed", "context_length": 8000,
         "pricing": {"prompt": "0.1", "completion": "0.2"}},
        {"id": "deepseek/v4-flash", "context_length": 128000},
        {"no_id": True},
    ]}

    class _Resp:
        def raise_for_status(self): pass
        def json(self): return payload

    import app.routers.ai_chat as mod
    monkeypatch.setattr(mod.httpx, "get", lambda *a, **k: _Resp())

    body = client.get("/api/ai/models").json()
    assert [m["id"] for m in body["models"]] == ["deepseek/v4-flash", "z/model"]
    assert body["models"][0]["name"] == "deepseek/v4-flash"  # falls back to the id
    assert body["selected"] == "test/model"

    filtered = client.get("/api/ai/models", params={"q": "deepseek"}).json()
    assert [m["id"] for m in filtered["models"]] == ["deepseek/v4-flash"]


def test_models_passthrough_surfaces_provider_errors(client, configured, monkeypatch):
    import app.routers.ai_chat as mod

    def boom(*a, **k):
        raise RuntimeError("catalogue down")

    monkeypatch.setattr(mod.httpx, "get", boom)
    resp = client.get("/api/ai/models")
    assert resp.status_code == 502
    assert "catalogue down" in resp.json()["detail"]


def test_old_oneshot_chat_endpoint_is_gone(client):
    assert client.post("/api/ai/chat", json={"question": "hi"}).status_code == 405
