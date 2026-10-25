"""Minimal client for any OpenAI-compatible /chat/completions API (Groq, Gemini, OpenRouter, ...).
Provider, URL, model and key all come from environment variables."""
import logging

import httpx

from app.config import settings

log = logging.getLogger("llm")


class LLMNotConfigured(RuntimeError):
    pass


class LLMUnavailable(RuntimeError):
    """Provider failed (rate limit, outage, bad model name, network)."""


def _call(model: str, messages: list, max_tokens: int) -> str:
    url = settings.llm_base_url.rstrip("/") + "/chat/completions"
    payload = {"model": model, "messages": messages, "temperature": 0, "max_tokens": max_tokens}
    if settings.llm_reasoning_effort:
        payload["reasoning_effort"] = settings.llm_reasoning_effort
    try:
        r = httpx.post(
            url,
            headers={"Authorization": f"Bearer {settings.llm_api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=settings.llm_timeout,
        )
    except httpx.HTTPError as e:
        raise LLMUnavailable(f"network error: {type(e).__name__}") from e
    if r.status_code != 200:
        raise LLMUnavailable(f"HTTP {r.status_code}: {r.text[:200]}")
    try:
        text = (r.json()["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, ValueError) as e:
        raise LLMUnavailable("unexpected response format") from e
    if not text:  # e.g. a reasoning model used all its tokens thinking. Never show this as "not found".
        raise LLMUnavailable("empty response (model returned no text)")
    return text


def complete(messages: list, max_tokens: int | None = None) -> str:
    if not settings.llm_api_key:
        raise LLMNotConfigured("LLM_API_KEY is not set")
    models = [settings.llm_model]
    if settings.llm_fallback_model and settings.llm_fallback_model != settings.llm_model:
        models.append(settings.llm_fallback_model)
    last = None
    for m in models:
        try:
            return _call(m, messages, max_tokens or settings.llm_max_tokens)
        except LLMUnavailable as e:
            last = e
            log.warning("LLM model %s failed (%s)%s", m, e, "; trying fallback" if m != models[-1] else "")
    raise last
