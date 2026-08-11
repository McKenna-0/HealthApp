"""Persistence for agent conversations.

Messages are stored in the provider's own wire format rather than a prettier
internal one, because a resumed conversation has to be handed straight back to
the model. The awkward part of that format is the pairing rule: an assistant
message carrying `tool_calls` must be followed by one `role: "tool"` message per
call id, or providers reject the request. Since we persist mid-turn - so a crash
doesn't lose the trace - a half-finished turn can leave that pairing broken, and
`transcript()` is what repairs it on the way back out.

No FastAPI import here: the whole module is drivable from a test with a session.
"""

import json
import logging

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from .. import models
from ..timeutil import iso_now
from . import ai_client, context, food, weight

logger = logging.getLogger(__name__)

TITLE_MAX_CHARS = 60


def _estimate_tokens(text: str | None) -> int:
    return max(1, len(text or "") // 4)


# ---- sessions --------------------------------------------------------------------


def create_session(db: Session, provider: ai_client.Provider) -> models.AIChatSession:
    """The model and provider are snapshotted at creation, so a conversation
    still says what answered it after the settings change."""
    now = iso_now()
    row = models.AIChatSession(
        created_at=now,
        updated_at=now,
        title=None,
        model=provider.model or None,
        provider=provider.base_url or None,
        message_count=0,
    )
    db.add(row)
    db.commit()
    return row


def list_sessions(db: Session, limit: int = 50) -> list[models.AIChatSession]:
    return list(
        db.scalars(
            select(models.AIChatSession)
            .order_by(models.AIChatSession.updated_at.desc(), models.AIChatSession.id.desc())
            .limit(limit)
        ).all()
    )


def delete_session(db: Session, session_id: int) -> bool:
    row = db.get(models.AIChatSession, session_id)
    if row is None:
        return False
    # Explicit rather than trusting ON DELETE CASCADE: the pragma is set per
    # connection, and an orphaned transcript is invisible until it isn't.
    db.execute(
        delete(models.AIChatMessage).where(models.AIChatMessage.session_id == session_id)
    )
    # Only the drafts go - anything already confirmed is a real logged entry the
    # user owns, and deleting a chat must not silently retract it.
    db.execute(
        delete(models.AIPendingAction).where(
            models.AIPendingAction.session_id == session_id
        )
    )
    db.delete(row)
    db.commit()
    return True


def touch(db: Session, session_id: int) -> None:
    row = db.get(models.AIChatSession, session_id)
    if row:
        row.updated_at = iso_now()
        db.commit()


# ---- messages --------------------------------------------------------------------


def append_message(db: Session, session_id: int, msg: dict) -> models.AIChatMessage:
    """Persist one wire-format message. Called for every message the agent loop
    produces, as it produces it."""
    content = msg.get("content")
    if content is not None and not isinstance(content, str):
        content = json.dumps(content)

    trace = None
    if msg.get("role") == "tool" and content:
        try:
            trace = json.loads(content).get("trace_summary")
        except (json.JSONDecodeError, AttributeError):
            trace = None

    tool_calls = msg.get("tool_calls")
    row = models.AIChatMessage(
        session_id=session_id,
        role=msg["role"],
        content=content,
        tool_calls_json=json.dumps(tool_calls) if tool_calls else None,
        tool_call_id=msg.get("tool_call_id"),
        tool_name=msg.get("name"),
        trace_summary=trace,
        token_estimate=_estimate_tokens(content) + _estimate_tokens(
            json.dumps(tool_calls) if tool_calls else None
        ),
        created_at=iso_now(),
    )
    db.add(row)

    session = db.get(models.AIChatSession, session_id)
    if session:
        session.message_count = (session.message_count or 0) + 1
        session.updated_at = row.created_at
    db.commit()
    return row


def _rows(db: Session, session_id: int) -> list[models.AIChatMessage]:
    return list(
        db.scalars(
            select(models.AIChatMessage)
            .where(models.AIChatMessage.session_id == session_id)
            .order_by(models.AIChatMessage.id)
        ).all()
    )


def transcript(db: Session, session_id: int) -> list[dict]:
    """Rebuild the stored conversation as messages the provider will accept.

    Two repairs happen here, both for turns that died partway through:
    a tool message whose assistant call is gone is dropped, and an assistant
    tool_call that never got an answer gets a synthetic one. Either would
    otherwise be a hard 400 from the provider on the next question."""
    out: list[dict] = []
    for row in _rows(db, session_id):
        if row.role == "tool":
            out.append(
                {
                    "role": "tool",
                    "tool_call_id": row.tool_call_id,
                    "name": row.tool_name,
                    "content": row.content or "{}",
                }
            )
            continue

        msg: dict = {"role": row.role, "content": row.content}
        if row.tool_calls_json:
            try:
                msg["tool_calls"] = json.loads(row.tool_calls_json)
            except json.JSONDecodeError:
                logger.warning("Unparseable tool_calls on message %s", row.id)
                msg["content"] = msg["content"] or "(tool call omitted)"
        out.append(msg)

    return _repair_pairing(out)


def _repair_pairing(messages: list[dict]) -> list[dict]:
    answered = {m.get("tool_call_id") for m in messages if m.get("role") == "tool"}

    repaired: list[dict] = []
    open_ids: set[str] = set()
    for msg in messages:
        if msg.get("role") == "tool":
            if msg.get("tool_call_id") not in open_ids:
                continue  # orphan: its assistant message never made it to disk
            open_ids.discard(msg["tool_call_id"])
            repaired.append(msg)
            continue

        repaired.append(msg)
        for call in msg.get("tool_calls") or []:
            call_id = call.get("id")
            if not call_id:
                continue
            open_ids.add(call_id)
            if call_id not in answered:
                # The turn was interrupted before this tool ran. Answer it so the
                # history stays well-formed, and say why rather than faking data.
                repaired.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": (call.get("function") or {}).get("name"),
                        "content": json.dumps(
                            {"error": "interrupted", "message": "This tool call did not finish."}
                        ),
                    }
                )
                open_ids.discard(call_id)
    return repaired


# ---- serialisation for the UI ----------------------------------------------------


def session_out(row: models.AIChatSession) -> dict:
    return {
        "id": row.id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "title": row.title,
        "model": row.model,
        "provider": row.provider,
        "message_count": row.message_count or 0,
    }


def message_out(row: models.AIChatMessage) -> dict:
    tool_calls = None
    if row.tool_calls_json:
        try:
            tool_calls = [
                {
                    "id": c.get("id"),
                    "name": (c.get("function") or {}).get("name"),
                    "arguments": (c.get("function") or {}).get("arguments"),
                }
                for c in json.loads(row.tool_calls_json)
            ]
        except json.JSONDecodeError:
            tool_calls = None
    return {
        "id": row.id,
        "role": row.role,
        "content": row.content,
        "tool_calls": tool_calls,
        "tool_call_id": row.tool_call_id,
        "tool_name": row.tool_name,
        "trace_summary": row.trace_summary,
        "created_at": row.created_at,
    }


def session_detail(db: Session, session_id: int) -> dict | None:
    row = db.get(models.AIChatSession, session_id)
    if row is None:
        return None
    return {
        **session_out(row),
        "messages": [message_out(m) for m in _rows(db, session_id)],
        "pending_actions": [
            pending_action_out(a) for a in list_pending_actions(db, session_id)
        ],
    }


# ---- write proposals -------------------------------------------------------------


class PendingActionError(Exception):
    """The action isn't in a state where this makes sense."""


def list_pending_actions(db: Session, session_id: int) -> list[models.AIPendingAction]:
    return list(
        db.scalars(
            select(models.AIPendingAction)
            .where(models.AIPendingAction.session_id == session_id)
            .order_by(models.AIPendingAction.id)
        ).all()
    )


def pending_action_out(row: models.AIPendingAction) -> dict:
    return {
        "id": row.id,
        "session_id": row.session_id,
        "kind": row.kind,
        "summary_text": row.summary_text,
        "status": row.status,
        "payload": json.loads(row.payload_json) if row.payload_json else {},
        "created_at": row.created_at,
        "resolved_at": row.resolved_at,
        "result": json.loads(row.resolved_result_json) if row.resolved_result_json else None,
    }


def _apply(db: Session, row: models.AIPendingAction) -> dict:
    """Perform the write through the same service the UI uses, so a confirmed
    proposal is indistinguishable from a hand-entered row."""
    p = json.loads(row.payload_json)

    if row.kind == "log_weight":
        saved = weight.upsert_manual_weight(
            db, date=p["date"], weight_kg=p["weight_kg"], note=p.get("note")
        )
        return {"table": "weight_log", "id": saved.id}

    if row.kind == "log_food":
        saved = food.log_manual_entry(
            db,
            date=p["date"],
            meal=p["meal"],
            description=p.get("description"),
            calories=p.get("calories"),
            quantity_g=p.get("quantity_g"),
        )
        return {"table": "food_log", "id": saved.id}

    if row.kind == "log_context":
        saved = context.add_entry(
            db,
            date=p["date"],
            type=p["type"],
            value=p.get("value"),
            label=p.get("label"),
            note=p.get("note"),
        )
        return {"table": "context_log", "id": saved.id}

    raise PendingActionError(f"unknown action kind {row.kind!r}")


def resolve_pending_action(
    db: Session, action_id: int, confirm: bool
) -> models.AIPendingAction | None:
    """Confirm or discard a drafted write, exactly once.

    The status is claimed with a conditional UPDATE before anything is written,
    so a double-tapped Confirm - or a retried request - can't produce two rows.
    Whichever call loses the race gets a PendingActionError instead."""
    row = db.get(models.AIPendingAction, action_id)
    if row is None:
        return None

    target = "confirmed" if confirm else "rejected"
    claimed = db.execute(
        update(models.AIPendingAction)
        .where(
            models.AIPendingAction.id == action_id,
            models.AIPendingAction.status == "pending",
        )
        .values(status=target, resolved_at=iso_now())
    ).rowcount
    if not claimed:
        db.rollback()
        db.refresh(row)
        raise PendingActionError(f"this entry was already {row.status}")
    db.commit()
    db.refresh(row)

    if not confirm:
        return row

    try:
        row.resolved_result_json = json.dumps(_apply(db, row))
    except Exception as exc:  # noqa: BLE001
        # The claim already happened, so leaving it as "confirmed" would tell the
        # user something was saved when nothing was.
        logger.exception("Applying pending action %s failed", action_id)
        row.status = "failed"
        row.resolved_result_json = json.dumps({"error": f"{type(exc).__name__}: {exc}"})
    db.commit()
    db.refresh(row)
    return row


# ---- auto-titling ----------------------------------------------------------------

_TITLE_PROMPT = (
    "Summarise this health question as a title of six words or fewer. "
    "Reply with the title only: no quotes, no trailing punctuation."
)


def generate_title(db: Session, session_id: int) -> str | None:
    """Best-effort, and deliberately on the cheap report model rather than the
    agent model - it is a one-line summarisation, not analysis. Falls back to a
    truncated question so a session is never left nameless."""
    row = db.get(models.AIChatSession, session_id)
    if row is None or row.title:
        return None

    first_user = next(
        (m.content for m in _rows(db, session_id) if m.role == "user" and m.content), None
    )
    if not first_user:
        return None

    title = None
    try:
        raw = ai_client.chat(
            [
                {"role": "system", "content": _TITLE_PROMPT},
                {"role": "user", "content": first_user[:500]},
            ],
            temperature=0.2,
            max_tokens=32,
        )
        title = (raw or "").strip().strip('"').splitlines()[0][:TITLE_MAX_CHARS].strip()
    except Exception:  # noqa: BLE001 - a missing title must never fail a turn
        logger.info("Auto-title failed; falling back to the question text", exc_info=True)

    if not title:
        title = first_user[:40].strip()

    row.title = title
    db.commit()
    return title
