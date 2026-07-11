"""Minimal OpenAI-compatible chat client (works with OpenRouter, DeepInfra,
Ollama, or any /chat/completions endpoint). Kept deliberately tiny so the
provider is swappable via AI_BASE_URL/AI_MODEL env vars alone."""

import httpx

from ..config import settings


class AInot_configured(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.ai_api_key and settings.ai_model)


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
