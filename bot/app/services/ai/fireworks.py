import logging
import re
import asyncio
from functools import lru_cache
from typing import Optional

import httpx

from app.services.i18n.localization import get_text, resolve_language
from config.config import settings

logger = logging.getLogger(__name__)
_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_RETRY_BASE_DELAY_SECONDS = 2.0


def _setting_int(*keys: str, default: int) -> int:
    for key in keys:
        value = settings.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except Exception:
            continue
    return default


def _setting_float(*keys: str, default: float) -> float:
    for key in keys:
        value = settings.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except Exception:
            continue
    return default


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
    request_timeout = _setting_float(
        "AI_REQUEST_TIMEOUT_SEC",
        "ai_request_timeout_sec",
        default=30.0,
    )
    return httpx.AsyncClient(base_url=base_url, headers=headers, timeout=request_timeout)


@lru_cache(maxsize=1)
def _build_ai_semaphore() -> asyncio.Semaphore:
    limit = _setting_int("AI_MAX_CONCURRENCY", "ai_max_concurrency", default=4)
    if limit < 1:
        limit = 1
    logger.info("AI concurrency limit set to %s", limit)
    return asyncio.Semaphore(limit)


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

    max_retries = _setting_int("AI_MAX_RETRIES", "ai_max_retries", default=_MAX_RETRIES)
    retry_base_delay = _setting_float(
        "AI_RETRY_BASE_DELAY_SECONDS",
        "ai_retry_base_delay_seconds",
        default=_RETRY_BASE_DELAY_SECONDS,
    )
    queue_timeout_sec = _setting_float("AI_QUEUE_TIMEOUT_SEC", "ai_queue_timeout_sec", default=5.0)
    overall_timeout_sec = _setting_float("AI_OVERALL_TIMEOUT_SEC", "ai_overall_timeout_sec", default=90.0)

    semaphore = _build_ai_semaphore()
    acquired = False
    try:
        try:
            await asyncio.wait_for(semaphore.acquire(), timeout=queue_timeout_sec)
            acquired = True
        except asyncio.TimeoutError:
            logger.warning("AI request queue timeout after %.1fs", queue_timeout_sec)
            return get_text("ai.error.unavailable", lang)

        last_exc: Exception | None = None
        async def _run_request() -> str:
            nonlocal last_exc
            for attempt in range(1, max_retries + 1):
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
                except httpx.HTTPStatusError as exc:
                    last_exc = exc
                    status_code = exc.response.status_code
                    body_text = exc.response.text or ""
                    retryable = (
                        status_code in _RETRYABLE_STATUSES
                        or "DEPLOYMENT_SCALING_UP" in body_text
                    )
                    if not retryable or attempt >= max_retries:
                        raise
                    delay = retry_base_delay * attempt
                    logger.warning(
                        "AI provider returned %s (attempt %s/%s), retrying in %.1fs",
                        status_code,
                        attempt,
                        max_retries,
                        delay,
                    )
                    await asyncio.sleep(delay)
                except Exception as exc:
                    last_exc = exc
                    if attempt >= max_retries:
                        raise
                    delay = retry_base_delay * attempt
                    logger.warning(
                        "AI request failed on attempt %s/%s, retrying in %.1fs: %r",
                        attempt,
                        max_retries,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)
            if last_exc is not None:
                raise last_exc
            return get_text("ai.error.generic", lang)

        if overall_timeout_sec > 0:
            return await asyncio.wait_for(_run_request(), timeout=overall_timeout_sec)
        return await _run_request()
    except asyncio.TimeoutError:
        logger.warning("AI request timed out after %.1fs", overall_timeout_sec)
        return get_text("ai.error.unavailable", lang)
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
    finally:
        if acquired:
            semaphore.release()
