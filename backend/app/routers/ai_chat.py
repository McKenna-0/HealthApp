"""Agent chat: saved sessions and one streaming endpoint.

The streaming endpoint is the unusual one. Once the first SSE byte is written
the HTTP status is fixed, so everything that can fail with a status code -
missing session, unconfigured provider - is checked *before* the response starts,
and everything after that becomes an `error` frame instead.
"""

import json
import logging
from collections.abc import Callable, Iterator

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models
from ..db import SessionLocal, get_db
from ..services import ai_agent, ai_chat, ai_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ai-chat"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    # nginx and friends buffer proxied responses by default, which turns a live
    # stream into one lump at the end.
    "X-Accel-Buffering": "no",
}


def get_db_factory() -> Callable[[], Session]:
    """A factory, not a session: the streaming generator runs outside the window
    in which a `Depends(get_db)` session is guaranteed open, and holding the
    request session for a minute-long turn would be wrong even if it worked.
    Overridable in tests, same as `get_db`."""
    return SessionLocal


class MessageIn(BaseModel):
    message: str = Field(min_length=2, max_length=4000)


class ProviderIn(BaseModel):
    base_url: str | None = Field(default=None, max_length=300)
    api_key: str | None = Field(default=None, max_length=300)
    model: str | None = Field(default=None, max_length=200)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ---- sessions --------------------------------------------------------------------


@router.get("/sessions")
def list_sessions(db: Session = Depends(get_db)):
    return [ai_chat.session_out(s) for s in ai_chat.list_sessions(db)]


@router.post("/sessions")
def create_session(db: Session = Depends(get_db)):
    provider = ai_client.resolve_agent_provider(db)
    return ai_chat.session_out(ai_chat.create_session(db, provider))


@router.get("/sessions/{session_id}")
def get_session(session_id: int, db: Session = Depends(get_db)):
    detail = ai_chat.session_detail(db, session_id)
    if detail is None:
        raise HTTPException(404, "Chat session not found")
    return detail


@router.delete("/sessions/{session_id}")
def delete_session(session_id: int, db: Session = Depends(get_db)):
    if not ai_chat.delete_session(db, session_id):
        raise HTTPException(404, "Chat session not found")
    return {"deleted": session_id}


@router.post("/sessions/{session_id}/messages")
def post_message(
    session_id: int,
    body: MessageIn,
    db: Session = Depends(get_db),
    factory: Callable[[], Session] = Depends(get_db_factory),
):
    if db.get(models.AIChatSession, session_id) is None:
        raise HTTPException(404, "Chat session not found")

    provider = ai_client.resolve_agent_provider(db)
    if not provider.configured:
        raise HTTPException(
            400, "AI agent not configured - set a model and API key in settings"
        )

    return StreamingResponse(
        _event_stream(session_id, body.message, factory, provider),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


def _event_stream(
    session_id: int,
    question: str,
    factory: Callable[[], Session],
    provider: ai_client.Provider,
) -> Iterator[str]:
    db = factory()
    try:
        user_row = ai_chat.append_message(
            db, session_id, {"role": "user", "content": question}
        )
        yield _sse("start", {"session_id": session_id, "user_message_id": user_row.id})

        # Rebuilt fresh every turn: the system prompt carries today's date and a
        # current data inventory, so a stored copy would go stale.
        messages = ai_agent.system_messages(db, session_id) + ai_chat.transcript(
            db, session_id
        )

        def persist(msg: dict) -> None:
            ai_chat.append_message(db, session_id, msg)

        failed = False
        for event in ai_agent.run_agent_turn(
            db, messages, provider, on_message=persist, session_id=session_id
        ):
            if event.type == "error":
                failed = True
            yield _sse(event.type, event.data)

        if not failed:
            title = ai_chat.generate_title(db, session_id)
            if title:
                yield _sse("title", {"title": title})

        yield _sse("done", {"session_id": session_id})
    except Exception as exc:  # noqa: BLE001 - the status is already sent; this is the only channel left
        logger.exception("Agent stream failed for session %s", session_id)
        yield _sse("error", {"message": f"{type(exc).__name__}: {exc}"})
    finally:
        db.close()


# ---- write proposals -------------------------------------------------------------


@router.get("/sessions/{session_id}/pending-actions")
def list_pending(session_id: int, db: Session = Depends(get_db)):
    if db.get(models.AIChatSession, session_id) is None:
        raise HTTPException(404, "Chat session not found")
    return [ai_chat.pending_action_out(a) for a in ai_chat.list_pending_actions(db, session_id)]


def _resolve(action_id: int, confirm: bool, db: Session):
    try:
        row = ai_chat.resolve_pending_action(db, action_id, confirm)
    except ai_chat.PendingActionError as exc:
        # 409, not 400: the request was well-formed, the row had just moved on.
        raise HTTPException(409, str(exc))
    if row is None:
        raise HTTPException(404, "Pending action not found")
    if row.status == "failed":
        raise HTTPException(500, f"Could not save that entry: {row.resolved_result_json}")
    return ai_chat.pending_action_out(row)


@router.post("/pending-actions/{action_id}/confirm")
def confirm_action(action_id: int, db: Session = Depends(get_db)):
    return _resolve(action_id, True, db)


@router.post("/pending-actions/{action_id}/reject")
def reject_action(action_id: int, db: Session = Depends(get_db)):
    return _resolve(action_id, False, db)


# ---- provider configuration ------------------------------------------------------


@router.get("/provider")
def get_provider(db: Session = Depends(get_db)):
    provider = ai_client.resolve_agent_provider(db)
    overrides = {
        key: bool(db.get(models.UserSetting, key) and db.get(models.UserSetting, key).value)
        for key in ai_client.AGENT_SETTING_KEYS
    }
    return {
        "base_url": provider.base_url,
        "model": provider.model,
        # never echoed back, only whether one is present
        "api_key_set": bool(provider.api_key),
        "configured": provider.configured,
        "is_openrouter": provider.is_openrouter,
        "privacy_routing": bool(ai_client.privacy_extra_body(provider)),
        "overridden": overrides,
    }


@router.put("/provider")
def put_provider(body: ProviderIn, db: Session = Depends(get_db)):
    """Stores overrides in the settings table so the provider can be switched
    from the phone. Note the key is held in plaintext in SQLite, the same
    posture as the MyFitnessPal cookie."""
    for key, value in (
        ("ai_agent_base_url", body.base_url),
        ("ai_agent_api_key", body.api_key),
        ("ai_agent_model", body.model),
    ):
        if value is None:
            continue  # omitted means "leave alone"; use DELETE to clear
        row = db.get(models.UserSetting, key)
        if row:
            row.value = value.strip()
        else:
            db.add(models.UserSetting(key=key, value=value.strip()))
    db.commit()
    return get_provider(db)


@router.delete("/provider")
def clear_provider(db: Session = Depends(get_db)):
    """Drop the overrides and fall back to whatever `.env` says."""
    for key in ai_client.AGENT_SETTING_KEYS:
        row = db.get(models.UserSetting, key)
        if row:
            db.delete(row)
    db.commit()
    return get_provider(db)


@router.get("/models")
def list_models(
    q: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
):
    """Passthrough to the provider's own catalogue. Never hardcode model IDs -
    PrivateMind's catalogue in particular is dynamic and host-specific."""
    provider = ai_client.resolve_agent_provider(db)
    if not provider.base_url:
        raise HTTPException(400, "No AI base URL configured")

    try:
        resp = httpx.get(
            f"{provider.base_url.rstrip('/')}/models",
            headers={"Authorization": f"Bearer {provider.api_key}"} if provider.api_key else {},
            timeout=20,
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Could not list models: {type(exc).__name__}: {exc}")

    raw = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(raw, list):
        raise HTTPException(502, "Provider returned an unexpected model list")

    models_out = [_model_out(m) for m in raw if isinstance(m, dict) and m.get("id")]
    if q:
        needle = q.lower()
        models_out = [m for m in models_out if needle in m["id"].lower() or needle in (m["name"] or "").lower()]
    models_out.sort(key=lambda m: m["id"])
    return {"models": models_out, "base_url": provider.base_url, "selected": provider.model}


def _model_out(m: dict) -> dict:
    """Trimmed to what the picker shows - OpenRouter alone returns hundreds of
    entries with far more detail than a phone needs."""
    pricing = m.get("pricing") or {}
    return {
        "id": m["id"],
        "name": m.get("name") or m["id"],
        "context_length": m.get("context_length") or m.get("context_window"),
        "prompt_price": pricing.get("prompt"),
        "completion_price": pricing.get("completion"),
    }
