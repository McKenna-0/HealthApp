"""The agent loop.

Everything here runs against a scripted fake stream - no network, no API key.
The behaviour under test is recovery: a model that emits garbage, a tool that
raises, or a conversation that never converges must all still produce a usable
turn rather than a broken stream."""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.db import Base
from app.services import ai_agent, ai_tools
from app.services.ai_client import Provider


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


PROVIDER = Provider(base_url="https://example.test/v1", api_key="k", model="m")
# The real deployment routes through OpenRouter, which is the only host sent the
# reasoning and privacy blocks.
OPENROUTER = Provider(base_url="https://openrouter.ai/api/v1", api_key="k", model="m")


# ---- fake stream construction ----------------------------------------------------


def _text_chunks(text: str, finish="stop"):
    for ch in text:
        yield {"choices": [{"delta": {"content": ch}}]}
    yield {"choices": [{"delta": {}, "finish_reason": finish}]}


def _tool_chunks(name: str, arguments: str, call_id="call_1"):
    """Fragmented the way real providers do it: id/name first, arguments in
    pieces across several frames."""
    yield {"choices": [{"delta": {"tool_calls": [
        {"index": 0, "id": call_id, "function": {"name": name, "arguments": ""}}
    ]}}]}
    mid = len(arguments) // 2
    for piece in (arguments[:mid], arguments[mid:]):
        yield {"choices": [{"delta": {"tool_calls": [
            {"index": 0, "function": {"arguments": piece}}
        ]}}]}
    yield {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}


def _reasoning_chunks(thinking: str, content: str = "", finish="stop", key="reasoning"):
    """A reasoning model streams its chain of thought on a separate channel and
    only then starts on the answer. With `content=""` and finish="length" this is
    the shape of the bug in issue #22: the thinking consumed the whole completion
    budget, so the visible reply is empty."""
    for ch in thinking:
        yield {"choices": [{"delta": {key: ch}}]}
    for ch in content:
        yield {"choices": [{"delta": {"content": ch}}]}
    yield {"choices": [{"delta": {}, "finish_reason": finish}]}


def _scripted(monkeypatch, *scripts):
    """Each script is consumed by one successive call to chat_stream."""
    calls = {"n": 0, "sent": [], "tool_choice": [], "tools": [], "max_tokens": [], "extra": []}

    def fake_stream(messages, provider, tools=None, **kw):
        i = calls["n"]
        calls["n"] += 1
        calls["sent"].append(list(messages))
        calls["tool_choice"].append(kw.get("tool_choice"))
        calls["tools"].append(tools)
        calls["max_tokens"].append(kw.get("max_tokens"))
        calls["extra"].append(kw.get("extra_body"))
        if i >= len(scripts):
            raise AssertionError(f"chat_stream called {i + 1}x, only {len(scripts)} scripted")
        return iter(scripts[i])

    monkeypatch.setattr(ai_agent.ai_client, "chat_stream", fake_stream)
    return calls


def _run(db, monkeypatch, *scripts, question="how did I sleep?", max_iterations=6):
    _scripted(monkeypatch, *scripts)
    messages = ai_agent.system_messages(db) + [{"role": "user", "content": question}]
    events = list(
        ai_agent.run_agent_turn(db, messages, PROVIDER, max_iterations=max_iterations)
    )
    return events, messages


def _by_type(events, t):
    return [e for e in events if e.type == t]


# ---- happy path ------------------------------------------------------------------


def test_plain_answer_streams_tokens_and_finishes(db, monkeypatch):
    events, messages = _run(db, monkeypatch, list(_text_chunks("Fine.")))

    assert "".join(e.data["text"] for e in _by_type(events, "token")) == "Fine."
    done = _by_type(events, "message_done")
    assert len(done) == 1
    assert done[0].data["content"] == "Fine."
    assert messages[-1] == {"role": "assistant", "content": "Fine."}


def test_tool_call_is_dispatched_then_answered(db, monkeypatch):
    events, messages = _run(
        db,
        monkeypatch,
        list(_tool_chunks("get_data_inventory", "{}")),
        list(_text_chunks("You have no data yet.")),
    )

    assert [e.data["name"] for e in _by_type(events, "tool_call")] == ["get_data_inventory"]
    result = _by_type(events, "tool_result")[0]
    assert result.data["ok"] is True
    assert result.data["summary"]  # trace summary surfaced for the UI

    # the wire format the next request depends on: assistant tool_calls, then a
    # tool message carrying the matching id
    assistant = messages[-3]
    tool_msg = messages[-2]
    assert assistant["tool_calls"][0]["id"] == "call_1"
    assert tool_msg["role"] == "tool"
    assert tool_msg["tool_call_id"] == "call_1"


def test_fragmented_arguments_are_reassembled(db, monkeypatch):
    args = json.dumps({"start": "2026-01-01", "end": "2026-01-05", "fields": ["steps"]})
    events, _ = _run(
        db,
        monkeypatch,
        list(_tool_chunks("get_daily_series", args)),
        list(_text_chunks("ok")),
    )
    assert _by_type(events, "tool_result")[0].data["ok"] is True


# ---- recovery --------------------------------------------------------------------


def test_malformed_json_arguments_recover(db, monkeypatch):
    events, messages = _run(
        db,
        monkeypatch,
        list(_tool_chunks("get_daily_series", "{not json at all")),
        list(_text_chunks("Let me try that differently.")),
    )

    result = _by_type(events, "tool_result")[0]
    assert result.data["ok"] is False
    assert "JSON" in result.data["error"]
    # the model is told what went wrong and gets another turn
    assert json.loads(messages[-2]["content"])["error"] == "invalid_json_arguments"
    assert _by_type(events, "message_done")


def test_invalid_arguments_recover(db, monkeypatch):
    events, _ = _run(
        db,
        monkeypatch,
        list(_tool_chunks("get_daily_series", json.dumps({"start": "yesterday", "end": "today"}))),
        list(_text_chunks("recovered")),
    )
    result = _by_type(events, "tool_result")[0]
    assert result.data["ok"] is False
    assert _by_type(events, "message_done")


def test_unknown_tool_recovers(db, monkeypatch):
    events, messages = _run(
        db,
        monkeypatch,
        list(_tool_chunks("get_horoscope", "{}")),
        list(_text_chunks("no such tool")),
    )
    assert _by_type(events, "tool_result")[0].data["ok"] is False
    # error names the real tools so the model can correct itself
    assert "get_daily_series" in json.loads(messages[-2]["content"])["message"]


def test_tool_exception_becomes_a_message_not_a_crash(db, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("database on fire")

    monkeypatch.setattr(ai_tools, "dispatch", boom)

    events, messages = _run(
        db,
        monkeypatch,
        list(_tool_chunks("get_data_inventory", "{}")),
        list(_text_chunks("Something went wrong fetching that.")),
    )
    result = _by_type(events, "tool_result")[0]
    assert result.data["ok"] is False
    assert "database on fire" in result.data["error"]
    assert json.loads(messages[-2]["content"])["error"] == "tool_failed"


def test_stream_failure_emits_error_event(db, monkeypatch):
    def explode(*a, **k):
        raise ConnectionError("provider unreachable")

    monkeypatch.setattr(ai_agent.ai_client, "chat_stream", explode)
    messages = ai_agent.system_messages(db) + [{"role": "user", "content": "hi"}]
    events = list(ai_agent.run_agent_turn(db, messages, PROVIDER))

    assert [e.type for e in events] == ["error"]
    assert "provider unreachable" in events[0].data["message"]


# ---- bounds ----------------------------------------------------------------------


def test_last_iteration_takes_the_tools_away_and_gets_a_real_answer(db, monkeypatch):
    """A model that keeps re-calling tools used to burn the whole budget and
    then apologise, throwing away everything it had already fetched. The final
    pass forbids tools so it has to answer from what it has."""
    scripts = [
        list(_tool_chunks("get_data_inventory", "{}", call_id="c0")),
        list(_tool_chunks("get_data_inventory", "{}", call_id="c1")),
        list(_text_chunks("You averaged 11,230 steps.")),
    ]
    calls = _scripted(monkeypatch, *scripts)
    messages = ai_agent.system_messages(db) + [{"role": "user", "content": "steps?"}]
    events = list(ai_agent.run_agent_turn(db, messages, PROVIDER, max_iterations=3))

    assert calls["tools"] == [ai_tools.TOOL_SCHEMAS, ai_tools.TOOL_SCHEMAS, None]
    done = _by_type(events, "message_done")
    assert done[0].data["content"] == "You averaged 11,230 steps."
    assert "warning" not in done[0].data


def test_a_model_that_never_converges_still_answers_from_what_it_has(db, monkeypatch):
    """Three tool rounds and still asking. The budget is gone, but the fetched
    data is not - so the last word goes on an answer, not an apology."""
    scripts = [
        *[list(_tool_chunks("get_data_inventory", "{}", call_id=f"c{i}")) for i in range(3)],
        list(_text_chunks("From what I fetched: 7h 10m average.")),
    ]
    events, messages = _run(db, monkeypatch, *scripts, max_iterations=3)

    done = _by_type(events, "message_done")
    assert len(done) == 1
    assert done[0].data["content"] == "From what I fetched: 7h 10m average."
    assert messages[-1]["content"] == "From what I fetched: 7h 10m average."


def test_max_iterations_with_nothing_to_say_explains_itself(db, monkeypatch):
    """Budget spent and the forced answer came back blank too. The user gets an
    explanation, not silence."""
    scripts = [
        *[list(_tool_chunks("get_data_inventory", "{}", call_id=f"c{i}")) for i in range(3)],
        list(_text_chunks("", finish="length")),
    ]
    events, messages = _run(db, monkeypatch, *scripts, max_iterations=3)

    done = _by_type(events, "message_done")
    assert len(done) == 1
    assert done[0].data["warning"] == "no_answer"
    assert "narrow" in messages[-1]["content"]


def test_tool_calls_honoured_even_when_finish_reason_says_stop(db, monkeypatch):
    """Some providers report finish_reason 'stop' alongside tool calls."""
    script = [
        {"choices": [{"delta": {"tool_calls": [
            {"index": 0, "id": "x", "function": {"name": "get_data_inventory", "arguments": "{}"}}
        ]}}]},
        {"choices": [{"delta": {}, "finish_reason": "stop"}]},
    ]
    events, _ = _run(db, monkeypatch, script, list(_text_chunks("done")))
    assert len(_by_type(events, "tool_call")) == 1


def test_empty_choices_frames_are_ignored(db, monkeypatch):
    """OpenRouter sends keep-alive frames with no choices."""
    script = [{"choices": []}, {}, *list(_text_chunks("fine"))]
    events, _ = _run(db, monkeypatch, script)
    assert _by_type(events, "message_done")[0].data["content"] == "fine"


# ---- reasoning models and empty answers (issue #22) ------------------------------


def test_reasoning_is_streamed_rather_than_discarded(db, monkeypatch):
    """The thinking channel is the only sign of life during a long pass. It used
    to be dropped on the floor, so the UI sat on a finished tool trace."""
    events, _ = _run(
        db, monkeypatch, list(_reasoning_chunks("weighing the options", "Sleep looks fine."))
    )

    assert "".join(e.data["text"] for e in _by_type(events, "reasoning")) == "weighing the options"
    assert _by_type(events, "message_done")[0].data["content"] == "Sleep looks fine."


@pytest.mark.parametrize("key", ["reasoning", "reasoning_content"])
def test_reasoning_read_under_either_field_name(db, monkeypatch, key):
    """OpenRouter streams `reasoning`; DeepSeek's own API, vLLM and SGLang use
    `reasoning_content`."""
    events, _ = _run(db, monkeypatch, list(_reasoning_chunks("hmm", "ok", key=key)))
    assert "".join(e.data["text"] for e in _by_type(events, "reasoning")) == "hmm"


def test_reasoning_details_are_read(db, monkeypatch):
    script = [
        {"choices": [{"delta": {"reasoning_details": [
            {"type": "reasoning.text", "text": "step one"},
            {"type": "reasoning.text", "text": " step two"},
        ]}}]},
        *list(_text_chunks("ok")),
    ]
    events, _ = _run(db, monkeypatch, script)
    assert "".join(e.data["text"] for e in _by_type(events, "reasoning")) == "step one step two"


def test_thinking_eating_the_budget_still_produces_an_answer(db, monkeypatch):
    """Issue #22. A reasoning model draws thinking and answer from one
    `max_tokens` budget; when thinking exhausts it the stream ends
    `finish_reason: "length"` with no visible content. The turn used to be
    reported as a success, persisting an empty assistant message, and the user
    watched the tool trace fill in and then got a blank bubble."""
    scripts = [
        list(_tool_chunks("get_data_inventory", "{}")),
        list(_reasoning_chunks("a very long think", "", finish="length")),
        list(_text_chunks("You averaged 7h 20m of sleep.")),
    ]
    calls = _scripted(monkeypatch, *scripts)
    messages = ai_agent.system_messages(db) + [{"role": "user", "content": "sleep?"}]
    events = list(ai_agent.run_agent_turn(db, messages, OPENROUTER, max_iterations=6))

    done = _by_type(events, "message_done")
    assert len(done) == 1
    assert done[0].data["content"] == "You averaged 7h 20m of sleep."
    # nothing blank is ever persisted as the answer
    assert messages[-1] == {"role": "assistant", "content": "You averaged 7h 20m of sleep."}

    # the recovery pass withholds the tools and caps the thinking, so the budget
    # goes on the reply this time
    assert calls["tools"][-1] is None
    assert calls["extra"][-1]["reasoning"] == {"effort": "low"}


def test_a_single_stray_space_does_not_count_as_an_answer(db, monkeypatch):
    """What the real session actually recorded: content of exactly one space,
    the one visible token the model got out before the budget ran out."""
    scripts = [
        list(_reasoning_chunks("thinking hard", " ", finish="length")),
        list(_text_chunks("Here is the answer.")),
    ]
    events, messages = _run(db, monkeypatch, *scripts)

    assert _by_type(events, "message_done")[0].data["content"] == "Here is the answer."
    assert messages[-1]["content"] == "Here is the answer."


def test_blank_twice_tells_the_user_instead_of_showing_nothing(db, monkeypatch):
    scripts = [
        list(_reasoning_chunks("think", "", finish="length")),
        list(_reasoning_chunks("think again", "", finish="length")),
    ]
    events, messages = _run(db, monkeypatch, *scripts)

    done = _by_type(events, "message_done")
    assert len(done) == 1
    assert done[0].data["warning"] == "no_answer"
    assert done[0].data["content"].strip()  # never an empty bubble
    assert messages[-1]["content"].strip()


def test_final_pass_withholds_the_tools_outright(db, monkeypatch):
    """tool_choice="none" is advisory and a provider was observed ignoring it,
    asking for more tools with the budget already spent. Omitting the tools from
    the request is the only version the provider cannot talk its way out of."""
    scripts = [
        list(_tool_chunks("get_data_inventory", "{}", call_id="c0")),
        list(_text_chunks("Two sources checked.")),
    ]
    calls = _scripted(monkeypatch, *scripts)
    messages = ai_agent.system_messages(db) + [{"role": "user", "content": "q"}]
    list(ai_agent.run_agent_turn(db, messages, PROVIDER, max_iterations=2))

    assert calls["tools"][0] is ai_tools.TOOL_SCHEMAS
    assert calls["tools"][1] is None


def test_tool_calls_on_the_final_pass_are_not_run(db, monkeypatch):
    """A preamble plus yet another tool call, on the pass that was supposed to
    answer. Running those tools would spend the user's time on results nothing
    will ever read - and the preamble is not an answer either."""
    preamble = [
        {"choices": [{"delta": {"content": "Let me pull your workout history."}}]},
        {"choices": [{"delta": {"tool_calls": [
            {"index": 0, "id": "late", "function": {"name": "get_data_inventory", "arguments": "{}"}}
        ]}}]},
        {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
    ]
    scripts = [
        list(_tool_chunks("get_data_inventory", "{}", call_id="c0")),
        preamble,
        list(_text_chunks("You trained legs twice this week.")),
    ]
    events, messages = _run(db, monkeypatch, *scripts, max_iterations=2)

    # one tool round, from the first iteration only
    assert [e.data["call_id"] for e in _by_type(events, "tool_call")] == ["c0"]
    assert _by_type(events, "message_done")[0].data["content"] == (
        "You trained legs twice this week."
    )
    # the unanswerable tool_calls message is never persisted: it would leave the
    # stored transcript needing a synthetic tool reply on the next question
    assert not any(m.get("tool_calls") for m in messages[-2:])


def test_the_answer_gets_a_bigger_budget_than_a_tool_pass(db, monkeypatch):
    calls = _scripted(monkeypatch, list(_text_chunks("fine")))
    messages = ai_agent.system_messages(db) + [{"role": "user", "content": "q"}]
    list(ai_agent.run_agent_turn(db, messages, PROVIDER))

    assert calls["max_tokens"][0] == ai_agent.MAX_RESPONSE_TOKENS
    assert ai_agent.MAX_RESPONSE_TOKENS > 4096  # the cap the bug was found under


def test_recovery_pass_still_carries_the_privacy_routing(db, monkeypatch):
    """The forced-answer pass sends the whole conversation - health data included
    - a second time. It must not lose the no-data-collection routing on the way."""
    calls = _scripted(
        monkeypatch,
        list(_reasoning_chunks("think", "", finish="length")),
        list(_text_chunks("answered")),
    )
    messages = ai_agent.system_messages(db) + [{"role": "user", "content": "q"}]
    list(ai_agent.run_agent_turn(db, messages, OPENROUTER))

    assert calls["n"] == 2  # the recovery pass happened
    for sent in calls["extra"]:
        assert sent["provider"] == {"data_collection": "deny", "require_parameters": True}


def test_reasoning_cap_is_not_sent_to_a_non_openrouter_host(db, monkeypatch):
    """Other OpenAI-compatible servers reject unknown top-level fields, so the
    reasoning block is gated on the host - same rule as the privacy block."""
    local = Provider(base_url="http://localhost:8080/v1", api_key="k", model="m")
    calls = _scripted(
        monkeypatch,
        list(_reasoning_chunks("think", "", finish="length")),
        list(_text_chunks("answered")),
    )
    messages = ai_agent.system_messages(db) + [{"role": "user", "content": "q"}]
    events = list(ai_agent.run_agent_turn(db, messages, local))

    assert _by_type(events, "message_done")[0].data["content"] == "answered"
    assert "reasoning" not in (calls["extra"][-1] or {})


# ---- persistence hook ------------------------------------------------------------


def test_on_message_fires_for_every_message_mid_turn(db, monkeypatch):
    seen = []
    _scripted(
        monkeypatch,
        list(_tool_chunks("get_data_inventory", "{}")),
        list(_text_chunks("all done")),
    )
    messages = ai_agent.system_messages(db) + [{"role": "user", "content": "q"}]
    list(ai_agent.run_agent_turn(db, messages, PROVIDER, on_message=seen.append))

    # assistant-with-tool_calls, tool result, final assistant - persisted as they
    # happen so a crash mid-turn doesn't lose the trace
    assert [m["role"] for m in seen] == ["assistant", "tool", "assistant"]


# ---- context trimming ------------------------------------------------------------


def test_trim_keeps_everything_when_small():
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    assert ai_agent.trim_history(msgs) == msgs


def test_trim_collapses_old_tool_payloads_first():
    big = json.dumps({"trace_summary": "Checked steps", "series": ["x" * 5000]})
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
        {"role": "tool", "tool_call_id": "1", "content": big},
        {"role": "user", "content": "q2"},
        {"role": "assistant", "content": "a2"},
        {"role": "user", "content": "q3"},
        {"role": "assistant", "content": "a3"},
    ]
    out = ai_agent.trim_history(msgs, budget=500)
    tool_msgs = [m for m in out if m["role"] == "tool"]
    if tool_msgs:
        # payload replaced by its summary, so the model still knows what was checked
        assert json.loads(tool_msgs[0]["content"])["trace_summary"] == "Checked steps"
        assert len(tool_msgs[0]["content"]) < 200


def test_trim_notes_when_it_drops_turns():
    msgs = [{"role": "system", "content": "sys"}]
    for i in range(40):
        msgs.append({"role": "user", "content": f"question {i} " + "x" * 200})
        msgs.append({"role": "assistant", "content": f"answer {i} " + "y" * 200})

    out = ai_agent.trim_history(msgs, budget=800)
    joined = " ".join(m["content"] for m in out if m["role"] == "system")
    assert "were dropped" in joined
    # newest exchange survives
    assert any("question 39" in m["content"] for m in out if m["role"] == "user")


def test_trim_never_orphans_a_tool_message():
    """A tool message whose assistant tool_call was dropped is a wire-format
    error at most providers."""
    msgs = [{"role": "system", "content": "sys"}]
    for i in range(30):
        msgs.append({"role": "user", "content": f"q{i} " + "x" * 300})
        msgs.append({"role": "assistant", "content": None, "tool_calls": [
            {"id": f"c{i}", "type": "function", "function": {"name": "get_data_inventory", "arguments": "{}"}}
        ]})
        msgs.append({"role": "tool", "tool_call_id": f"c{i}", "content": "z" * 300})
        msgs.append({"role": "assistant", "content": f"a{i} " + "y" * 300})

    out = ai_agent.trim_history(msgs, budget=900)
    body = [m for m in out if m["role"] != "system"]
    assert body, "trimming should not empty the conversation"
    assert body[0]["role"] != "tool"


# ---- system prompt ---------------------------------------------------------------


def test_system_messages_carry_inventory_and_today(db):
    db.add(models.DailyMetrics(
        date="2026-03-01", steps=100, source="mock", synced_at="x"
    ))
    db.commit()

    msgs = ai_agent.system_messages(db)
    assert len(msgs) == 2
    assert "not medical advice" in msgs[0]["content"]
    # inventory is a separate message so the stable prompt above it stays cacheable
    assert "DATA INVENTORY" in msgs[1]["content"]
    assert "2026-03-01" in msgs[1]["content"]


def test_prompt_forbids_citing_from_memory(db):
    prompt = ai_agent.system_messages(db)[0]["content"]
    assert "search_literature" in prompt
    assert "PMID" in prompt
