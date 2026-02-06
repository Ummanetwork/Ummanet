import logging
import re
from functools import lru_cache
from typing import Optional

import httpx

from app.services.i18n.localization import get_text, resolve_language
from config.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _build_client() -> Optional[httpx.AsyncClient]:
    api_key = settings.get("AI_API_KEY") or settings.get("ai_api_key")
    if not api_key:
        logger.warning("AI_API_KEY is not configured. AI responses are disabled.")
        return None

    base_url = settings.get("AI_BASE_URL") or settings.get("ai_base_url")
    base_url = base_url or "https://api.fireworks.ai/inference/v1"
    account = (
        settings.get("AI_ACCOUNT")
        or settings.get("AI_FIREWORKS_ACCOUNT")
        or settings.get("ai_account")
        or settings.get("ai_fireworks_account")
    )
    headers = {"Authorization": f"Bearer {api_key}"}
    if account:
        headers["Fireworks-Account"] = account
    return httpx.AsyncClient(base_url=base_url, headers=headers, timeout=30.0)


def _resolve_runtime_language(lang_code: Optional[str]) -> str:
    default_locale = getattr(getattr(settings, "i18n", {}), "default_locale", None)
    return resolve_language(lang_code, default_locale)


def _system_prompt(lang: str) -> str:
    override = settings.get("AI_SYSTEM_PROMPT") or settings.get("ai_system_prompt")
    if override:
        return override
    return get_text("ai.system.prompt", lang)


async def generate_ai_response(message: str, lang_code: Optional[str] = None) -> str:
    lang = _resolve_runtime_language(lang_code)

    client = _build_client()
    if client is None:
        return get_text("ai.error.unavailable", lang)

    model = settings.get("AI_MODEL") or settings.get("ai_model")
    model = model or "accounts/fireworks/models/deepseek-r1-0528"

    try:
        response = await client.post(
            "/chat/completions",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": _system_prompt(lang)},
                    {"role": "user", "content": message},
                ],
            },
        )
        response.raise_for_status()
        payload = response.json()
        choices = payload.get("choices") or []
        content = ""
        if choices:
            message_payload = choices[0].get("message") or {}
            content = message_payload.get("content") or ""
        if not content:
            return get_text("ai.error.empty", lang)

        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        return content or get_text("ai.error.empty.trimmed", lang)
    except Exception as exc:
        logger.exception("Failed to generate AI response")
        detail = getattr(exc, "message", None) or getattr(exc, "body", None)
        if detail is None and isinstance(exc, httpx.HTTPStatusError):
            detail = exc.response.text
        if detail is None and hasattr(exc, "response"):
            response = getattr(exc, "response")
            detail = getattr(response, "text", None)
            if detail is None and hasattr(response, "json"):
                try:
                    detail = response.json()
                except Exception:
                    detail = None
        if detail is None:
            detail = repr(exc)
        debug_suffix = f"\n\n[AI error: {detail}]"
        return get_text("ai.error.generic", lang) + debug_suffix
