"""The agentic chat loop.

The model is given tools rather than a pre-baked summary, so it decides what data
the question actually needs and goes and gets it. The loop's job is to keep that
honest and bounded:

- every tool failure becomes a message the model can recover from, never an
  exception that kills the turn;
- tool-call arguments are never parsed until the provider says the call is
  complete, because providers fragment them differently;
- the whole thing is a generator of events so the UI can show the work in
  progress instead of a 30-second spinner.
"""

import json
import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..timeutil import today_local
from . import ai_client, ai_tools
from .ai_client import Provider

logger = logging.getLogger(__name__)

# Model passes per user turn. The last one is answer-only, so the model gets
# MAX_ITERATIONS - 1 rounds of tool calls. Six was too few for a question that
# spans domains (cardio + strength + context + correlations is four already).
MAX_ITERATIONS = 10

# Budget for the messages we resend each pass (tool schemas and the reply ride
# on top). 12k was small enough that a single multi-domain turn overflowed it,
# and the overflow was paid for with that same turn's tool results.
MAX_CONTEXT_TOKENS = 24000

# Appended to the final request only - never persisted, never shown.
FINAL_PASS_NUDGE = (
    "[System note: the tool budget for this question is used up and tools are "
    "now disabled. Write your final answer now, from the tool results above. Do "
    "not say what you are about to look up next. If something you wanted is "
    "missing, say so in the answer and work with what you have.]"
)

TRUNCATED_NOTE = (
    "\n\n*(This reply hit the length limit and was cut off - ask me to continue.)*"
)

EMPTY_ANSWER_NOTE = (
    "The model returned an empty reply, so there is nothing to show for that "
    "question. Please ask again - nothing was changed."
)

AGENT_SYSTEM_PROMPT = """You are an evidence-based health and fitness analyst with \
tool access to one person's self-tracked data: a Garmin wearable (sleep, HRV, resting \
heart rate, steps, stress, body battery), a food log, logged strength training, manually \
entered bloodwork, and subjective context logs (alcohol, caffeine, mood, illness).

Today's date is {today}.

HOW TO ANSWER
1. Work out what data would actually answer the question before reaching for a tool. \
You get at most {tool_rounds} rounds of tool calls per question, so plan them: request \
everything you can foresee needing in the same round, as parallel calls, instead of one \
call per round. Do not re-request data you already have.
2. Check the data inventory below before assuming a period is covered. Never request or \
reason about a period that has no data - say it isn't there.
3. Call the narrowest tools that answer the question. Prefer aggregated statistics over \
raw daily rows; only ask for day-level granularity over short, specific windows.
4. Reason from the numbers the tools return, and quote them. Never invent a number, a \
date, or a data point you were not given.
5. If a tool returns notices about clipped or re-bucketed data, take them seriously and \
tell the user what you actually looked at.
6. Do not narrate ("Let me check...", "Now let me look at..."). Call the tools silently, \
then write one complete answer. If the data you hoped for does not exist in any tool, \
stop looking and answer from what you have, saying what was missing.

HONESTY
- This is one person's data. Correlations over weeks are weak evidence; say so whenever \
you cite one, including anything from get_correlation_insights.
- Wearable calorie, HRV, and sleep-stage numbers are estimates. Treat them as \
directional, and describe them that way.
- If the data is thin, contradictory, or missing, say so plainly instead of filling the \
gap with a plausible-sounding guess. "I can't tell from this" is a valid answer.
- For blood markers outside their reference range, recommend discussing with a doctor \
rather than suggesting a treatment. You are not a physician.

CITING RESEARCH
- You may cite a study only if search_literature returned it in this conversation. \
Always include the PMID. Never cite a paper, statistic, or figure from memory - if you \
have not looked it up in this conversation, you do not have it.
- Prefer reviews and meta-analyses over single trials, and say which you are relying on.
- When published findings and this person's own data disagree, say so rather than \
picking a side by default. Population evidence does not override what their data shows, \
and their n=1 data does not overturn a body of research.
- General physiological principles (protein supports muscle retention, alcohol lowers \
HRV, sleep drives recovery) can be stated without a citation. Specific numbers cannot.

LOGGING DATA
- You cannot write to the user's records. The propose_* tools only draft an entry \
for them to confirm or discard.
- After proposing, say what you drafted and that it is waiting for confirmation. \
Never say it has been logged, saved or recorded - it has not.
- Only propose when the user has clearly asked to log something. Do not propose \
off the back of a question about their data.
- Never invent a value to fill a proposal. If you don't know the calories, the \
weight or the amount, ask.

STYLE
Be concise and direct. Most answers should be a few sentences; use markdown headers or \
bullets only when the answer genuinely has structure. Do not restate the question.

When an answer draws a health conclusion, end it with one line noting this is automated \
analysis of self-tracked data, not medical advice. Skip that line for trivial factual \
exchanges like "what was my weight on Tuesday"."""


@dataclass
class AgentEvent:
    type: str
    data: dict = field(default_factory=dict)


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def system_messages(db: Session, session_id: int | None = None) -> list[dict]:
    """System prompt first (byte-stable, so providers with automatic prefix
    caching can hit it), then the data inventory, which changes as data syncs,
    then - only when there are any - what happened to this session's proposals."""
    inventory = ai_tools.get_data_inventory(db)
    compact = {
        "overall_range": [inventory["overall_first_date"], inventory["overall_last_date"]],
        "domains": {
            d["domain"]: {"from": d["first_date"], "to": d["last_date"], "rows": d["n_rows"]}
            for d in inventory["domains"]
        },
        "activity_types": inventory["activity_types"],
        "context_types": inventory["context_types"],
        "workout_sets": inventory["workout_sets"],
    }
    messages = [
        {
            "role": "system",
            "content": AGENT_SYSTEM_PROMPT.format(
                today=today_local().isoformat(), tool_rounds=MAX_ITERATIONS - 1
            ),
        },
        {
            "role": "system",
            "content": "DATA INVENTORY (what exists right now):\n" + json.dumps(compact),
        },
    ]

    # The user confirms or discards a proposal outside the conversation, so
    # without this the model would keep believing every draft is still pending.
    if session_id is not None:
        actions = db.scalars(
            select(models.AIPendingAction)
            .where(models.AIPendingAction.session_id == session_id)
            .order_by(models.AIPendingAction.id)
        ).all()
        if actions:
            lines = [f"- {a.summary_text} -> {a.status}" for a in actions]
            messages.append({
                "role": "system",
                "content": "ENTRIES YOU DRAFTED IN THIS CONVERSATION:\n" + "\n".join(lines),
            })

    return messages


def _collapse_tool(m: dict) -> dict:
    """A tool result reduced to its one-line trace summary."""
    if m["role"] != "tool" or len(m.get("content") or "") <= 200:
        return m
    try:
        summary = json.loads(m["content"]).get("trace_summary")
    except (json.JSONDecodeError, AttributeError):
        summary = None
    return {**m, "content": json.dumps({"trace_summary": summary or "(older result omitted)"})}


def trim_history(messages: list[dict], budget: int = MAX_CONTEXT_TOKENS) -> list[dict]:
    """Keep the conversation inside a token budget, cheapest loss first.

    1. Tool results from *earlier* turns shrink to their trace summary - the
       assistant's conclusions about them survive in its replies.
    2. Only then the current turn's own results, oldest first, sparing the most
       recent round. These are the evidence the pending answer will be written
       from; collapsing them early is what made the model fetch the same runs
       three times in one turn.
    3. Finally whole earlier exchanges are dropped, with a note so the model
       knows the history is partial. The question being answered never goes."""
    system = [m for m in messages if m["role"] == "system"]
    body = [m for m in messages if m["role"] != "system"]

    def total(msgs: list[dict]) -> int:
        return sum(_estimate_tokens(json.dumps(m)) for m in system + msgs)

    if total(body) <= budget:
        return system + body

    # where the turn in progress starts: the last user message
    current = max((i for i, m in enumerate(body) if m["role"] == "user"), default=0)

    # 1. earlier turns
    trimmed = [_collapse_tool(m) if i < current else m for i, m in enumerate(body)]
    if total(trimmed) <= budget:
        return system + trimmed

    # 2. this turn, oldest first, one at a time so we stop as soon as it fits
    for i in range(current, len(trimmed) - 4):
        collapsed = _collapse_tool(trimmed[i])
        if collapsed is not trimmed[i]:
            trimmed[i] = collapsed
            if total(trimmed) <= budget:
                return system + trimmed

    # 3. drop oldest turns, but never orphan a tool message from its tool_call,
    #    and never reach into the turn in progress
    dropped = 0
    while current > 0 and total(trimmed) > budget:
        trimmed.pop(0)
        dropped += 1
        current -= 1
        while current > 0 and trimmed[0]["role"] == "tool":
            trimmed.pop(0)
            dropped += 1
            current -= 1

    if dropped:
        system = system + [{
            "role": "system",
            "content": (
                f"[{dropped} earlier messages in this conversation were dropped to fit "
                "the context window. If you need something from earlier, ask, or "
                "re-run the relevant tool.]"
            ),
        }]
    return system + trimmed


def _accumulate_tool_calls(buffer: dict[int, dict], deltas: list[dict]) -> None:
    """Providers fragment tool calls across chunks - id and name may arrive in one
    frame and arguments dribble in over several. Merge by stream index and do not
    parse anything yet."""
    for d in deltas:
        idx = d.get("index", 0)
        slot = buffer.setdefault(idx, {"id": None, "name": None, "arguments": ""})
        if d.get("id"):
            slot["id"] = d["id"]
        fn = d.get("function") or {}
        if fn.get("name"):
            slot["name"] = fn["name"]
        if fn.get("arguments"):
            slot["arguments"] += fn["arguments"]


def run_agent_turn(
    db: Session,
    messages: list[dict],
    provider: Provider,
    on_message: Callable[[dict], None] | None = None,
    max_iterations: int = MAX_ITERATIONS,
    session_id: int | None = None,
) -> Iterator[AgentEvent]:
    """Drive one user turn to completion, yielding events as it goes.

    `messages` must already contain the system messages and the new user message;
    it is appended to in place. `on_message` is called for every message the loop
    produces, so callers can persist mid-turn and survive a crash."""

    def emit(msg: dict) -> None:
        messages.append(msg)
        if on_message:
            on_message(msg)

    extra = ai_client.privacy_extra_body(provider)

    for iteration in range(max_iterations):
        content = ""
        tool_buffer: dict[int, dict] = {}
        finish_reason = None

        # Spend the last iteration answering, not fetching. Observed a turn
        # where a tool kept returning off-topic papers, the model kept
        # re-searching, and the budget ran out with nothing said at all - the
        # user got an apology instead of the data already in hand. Tools stay
        # in the request so the cached prefix doesn't change; only the choice
        # is taken away - and the model is told, because a model that doesn't
        # know this pass is the last one spends it announcing its next lookup.
        last = iteration == max_iterations - 1

        request = trim_history(messages)
        if last and iteration > 0:
            request = request + [{"role": "user", "content": FINAL_PASS_NUDGE}]

        try:
            for chunk in ai_client.chat_stream(
                request,
                provider=provider,
                tools=ai_tools.TOOL_SCHEMAS,
                tool_choice="none" if last else "auto",
                extra_body=extra,
            ):
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                choice = choices[0]
                delta = choice.get("delta") or {}

                if delta.get("content"):
                    content += delta["content"]
                    yield AgentEvent("token", {"text": delta["content"]})

                if delta.get("tool_calls"):
                    _accumulate_tool_calls(tool_buffer, delta["tool_calls"])

                if choice.get("finish_reason"):
                    finish_reason = choice["finish_reason"]
        except Exception as exc:  # noqa: BLE001 - the stream is the only thing that can't recover
            logger.exception("Agent stream failed")
            yield AgentEvent("error", {"message": f"{type(exc).__name__}: {exc}"})
            return

        # Trust the buffer over finish_reason: some providers report "stop" even
        # when they emitted tool calls.
        calls = [c for c in tool_buffer.values() if c.get("name")]

        if not calls:
            if not content.strip():
                # Nothing said and nothing asked for. Saved as-is this renders
                # as a blank space where the answer should be.
                emit({"role": "assistant", "content": EMPTY_ANSWER_NOTE})
                yield AgentEvent("token", {"text": EMPTY_ANSWER_NOTE})
                yield AgentEvent("message_done", {
                    "content": EMPTY_ANSWER_NOTE,
                    "finish_reason": finish_reason,
                    "warning": "empty_answer",
                })
                return
            done: dict = {"content": content, "finish_reason": finish_reason}
            if finish_reason == "length":
                # Otherwise a reply that stops mid-sentence looks finished.
                content += TRUNCATED_NOTE
                yield AgentEvent("token", {"text": TRUNCATED_NOTE})
                done.update(content=content, warning="truncated")
            emit({"role": "assistant", "content": content})
            yield AgentEvent("message_done", done)
            return

        emit({
            "role": "assistant",
            "content": content or None,
            "tool_calls": [
                {
                    "id": c["id"] or f"call_{i}",
                    "type": "function",
                    "function": {"name": c["name"], "arguments": c["arguments"] or "{}"},
                }
                for i, c in enumerate(calls)
            ],
        })

        for i, call in enumerate(calls):
            call_id = call["id"] or f"call_{i}"
            name = call["name"]
            yield AgentEvent("tool_call", {"call_id": call_id, "name": name, "arguments": call["arguments"]})

            result, ok, err = _run_tool(db, name, call["arguments"], session_id)

            emit({
                "role": "tool",
                "tool_call_id": call_id,
                "name": name,
                "content": json.dumps(result),
            })
            yield AgentEvent(
                "tool_result",
                {
                    "call_id": call_id,
                    "name": name,
                    "ok": ok,
                    "summary": result.get("trace_summary") if ok else None,
                    "error": err,
                },
            )
            if ok and result.get("pending_action_id"):
                # Surfaced as its own event so the UI can put a Confirm/Discard
                # card in front of the user without waiting for the reply.
                yield AgentEvent("pending_action", {
                    "id": result["pending_action_id"],
                    "summary_text": result["summary_text"],
                    "status": "pending",
                })

    # Only reachable if the provider ignored tool_choice="none" on the final
    # pass and asked for yet more tools.
    note = (
        "I wasn't able to finish working through that within my tool budget. "
        "Try narrowing the question - a specific metric or a shorter date range."
    )
    emit({"role": "assistant", "content": note})
    yield AgentEvent("message_done", {"content": note, "warning": "max_iterations"})


def _run_tool(
    db: Session, name: str, raw_arguments: str, session_id: int | None = None
) -> tuple[dict, bool, str | None]:
    """Every failure mode here becomes a result the model can read and react to.
    Nothing escapes as an exception, because a broken tool call should cost one
    iteration, not the whole conversation."""
    try:
        arguments = json.loads(raw_arguments or "{}")
    except json.JSONDecodeError:
        err = "arguments were not valid JSON"
        return (
            {"error": "invalid_json_arguments", "message": err, "received": (raw_arguments or "")[:300]},
            False,
            err,
        )

    if not isinstance(arguments, dict):
        err = "arguments must be a JSON object"
        return ({"error": "invalid_arguments", "message": err}, False, err)

    try:
        return ai_tools.dispatch(db, name, arguments, session_id), True, None
    except ai_tools.ToolError as exc:
        return ({"error": "tool_error", "message": str(exc)}, False, str(exc))
    except ValidationError as exc:
        msg = "; ".join(f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in exc.errors())
        return ({"error": "invalid_arguments", "message": msg}, False, msg)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Tool %s failed", name)
        msg = f"{type(exc).__name__}: {exc}"
        return ({"error": "tool_failed", "message": msg}, False, msg)
