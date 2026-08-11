"""Minimal OpenAI-compatible chat client (works with OpenRouter, DeepInfra,
Ollama, PrivateMind, or any /chat/completions endpoint). Kept deliberately tiny
so the provider is swappable via AI_BASE_URL/AI_MODEL env vars alone."""

import json
from collections.abc import Iterator
from dataclasses import dataclass

import httpx
from sqlalchemy.orm import Session

from .. import models
from ..config import settings


class AInot_configured(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.ai_api_key and settings.ai_model)


# ---- agent provider resolution ---------------------------------------------------

# Settings keys that override .env, so the provider can be swapped from the app
# without a redeploy (same pattern as the MyFitnessPal cookie).
AGENT_SETTING_KEYS = ("ai_agent_base_url", "ai_agent_api_key", "ai_agent_model")


@dataclass(frozen=True)
class Provider:
    base_url: str
    api_key: str
    model: str

    @property
    def is_openrouter(self) -> bool:
        return "openrouter.ai" in self.base_url

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.model and self.base_url)


def _setting(db: Session | None, key: str) -> str | None:
    if db is None:
        return None
    row = db.get(models.UserSetting, key)
    return (row.value or "").strip() if row else None


def resolve_agent_provider(db: Session | None = None) -> Provider:
    """UserSetting override -> .env -> the report model's provider."""
    return Provider(
        base_url=(
            _setting(db, "ai_agent_base_url")
            or settings.ai_agent_base_url
            or settings.ai_base_url
        ),
        api_key=(
            _setting(db, "ai_agent_api_key")
            or settings.ai_agent_api_key
            or settings.ai_api_key
        ),
        model=(
            _setting(db, "ai_agent_model")
            or settings.ai_agent_model
        ),
    )


def privacy_extra_body(provider: Provider) -> dict:
    """OpenRouter-only routing controls. Open weights do not imply privacy - the
    host still sees every prompt - so ask OpenRouter to skip endpoints that
    retain or train on data. Other OpenAI-compatible servers may reject unknown
    top-level fields, so this is gated on the host rather than sent blindly."""
    if provider.is_openrouter and settings.ai_require_zdr:
        return {
            "provider": {
                "data_collection": "deny",
                "require_parameters": True,
            }
        }
    return {}


def chat(messages: list[dict], temperature: float = 0.4, max_tokens: int = 3000) -> str:
    if not is_configured():
        raise AInot_configured("Set AI_API_KEY (and optionally AI_MODEL) in .env")
    resp = httpx.post(
        f"{settings.ai_base_url.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.ai_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.ai_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


# ---- streaming (used by the agent loop) ------------------------------------------

# Generous read timeout: a single agent turn can sit waiting on the model while
# it thinks through several tool rounds.
_STREAM_TIMEOUT = httpx.Timeout(connect=10.0, read=180.0, write=30.0, pool=10.0)


def chat_stream(
    messages: list[dict],
    provider: Provider,
    tools: list[dict] | None = None,
    tool_choice: str = "auto",
    temperature: float = 0.3,
    max_tokens: int = 4096,
    extra_body: dict | None = None,
) -> Iterator[dict]:
    """Yield parsed SSE frames from an OpenAI-compatible streaming completion.

    Frames are handed back raw - assembling `delta` fragments (both content and
    tool_calls) is the caller's job, because only the caller knows when a tool
    call is complete enough to parse."""
    if not provider.configured:
        raise AInot_configured("Agent provider not configured - set AI_AGENT_API_KEY")

    payload: dict = {
        "model": provider.model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    if tools:
        # Sent explicitly rather than relying on the default: some providers
        # only enable tool support when tool_choice is present.
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice
    if extra_body:
        payload.update(extra_body)

    url = f"{provider.base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {provider.api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    with httpx.Client(timeout=_STREAM_TIMEOUT) as client:
        with client.stream("POST", url, headers=headers, json=payload) as resp:
            if resp.status_code >= 400:
                resp.read()  # body isn't loaded on a streamed response
                raise httpx.HTTPStatusError(
                    f"{resp.status_code}: {resp.text[:500]}",
                    request=resp.request,
                    response=resp,
                )
            for line in resp.iter_lines():
                if not line:
                    continue
                if line.startswith("data:"):
                    data = line[5:].strip()
                    if data == "[DONE]":
                        return
                    try:
                        yield json.loads(data)
                    except json.JSONDecodeError:
                        # Keep-alive padding or a partial frame; skip it rather
                        # than killing the turn.
                        continue
