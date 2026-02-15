import logging
import re
import asyncio
import json
from functools import lru_cache
from typing import Optional

import httpx

from app.services.i18n.localization import get_text, resolve_language
from config.config import settings

logger = logging.getLogger(__name__)
_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 8
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


def _setting_bool(*keys: str, default: bool) -> bool:
    for key in keys:
        value = settings.get(key)
        if value is None:
            continue
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "y", "on"}:
            return True
        if text in {"0", "false", "no", "n", "off"}:
            return False
    return default


def _parse_retry_after(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        seconds = float(text)
    except Exception:
        return None
    if seconds <= 0:
        return None
    return seconds


def _extract_provider_error_code(body_text: str) -> Optional[str]:
    if not body_text:
        return None
    try:
        data = json.loads(body_text)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    err = data.get("error")
    if not isinstance(err, dict):
        return None
    code = err.get("code")
    if not code:
        return None
    return str(code).strip() or None


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
    debug_errors = _setting_bool("AI_DEBUG_ERRORS", "ai_debug_errors", default=False)
    scaling_up_max_attempts = _setting_int(
        "AI_SCALING_UP_MAX_ATTEMPTS",
        "ai_scaling_up_max_attempts",
        default=2,
    )
    if scaling_up_max_attempts < 1:
        scaling_up_max_attempts = 1
    scaling_up_retry_delay_sec = _setting_float(
        "AI_SCALING_UP_RETRY_DELAY_SEC",
        "ai_scaling_up_retry_delay_sec",
        default=5.0,
    )
    if scaling_up_retry_delay_sec < 0:
        scaling_up_retry_delay_sec = 0.0

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
                    error_code = _extract_provider_error_code(body_text) or ""
                    is_scaling_up = (
                        error_code == "DEPLOYMENT_SCALING_UP"
                        or "DEPLOYMENT_SCALING_UP" in body_text
                    )
                    retryable = (
                        status_code in _RETRYABLE_STATUSES
                        or is_scaling_up
                    )
                    attempt_limit = min(max_retries, scaling_up_max_attempts) if is_scaling_up else max_retries
                    if not retryable or attempt >= attempt_limit:
                        if is_scaling_up:
                            return get_text("ai.error.warming_up", lang)
                        raise

                    retry_after = _parse_retry_after(exc.response.headers.get("Retry-After"))
                    if is_scaling_up:
                        # Fireworks cold start may take minutes; don't block user requests for too long.
                        delay = retry_after if retry_after is not None else scaling_up_retry_delay_sec
                    else:
                        delay = retry_after if retry_after is not None else (retry_base_delay * attempt)
                    logger.warning(
                        "AI provider returned %s/%s (attempt %s/%s), retrying in %.1fs",
                        status_code,
                        error_code or "-",
                        attempt,
                        attempt_limit,
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
        # Common case: provider is waking up from scale-to-zero.
        if isinstance(exc, httpx.HTTPStatusError):
            body_text = exc.response.text or ""
            error_code = _extract_provider_error_code(body_text) or ""
            if error_code == "DEPLOYMENT_SCALING_UP" or "DEPLOYMENT_SCALING_UP" in body_text:
                return get_text("ai.error.warming_up", lang)

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
        if debug_errors:
            detail_text = str(detail)
            if len(detail_text) > 800:
                detail_text = detail_text[:800] + "...(truncated)"
            debug_suffix = f"\n\n[AI error: {detail_text}]"
            return get_text("ai.error.generic", lang) + debug_suffix
        return get_text("ai.error.generic", lang)
    finally:
        if acquired:
            semaphore.release()
