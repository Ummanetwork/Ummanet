from typing import Any, List
import json
import os

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _strip_wrapping_quotes(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1].strip()
    return text


def _unwrap_singleton_brackets(value: str) -> str:
    text = _strip_wrapping_quotes(value)
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if inner and "," not in inner:
            return _strip_wrapping_quotes(inner)
    return text


def _parse_string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except Exception:
            parsed = None
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
        if isinstance(parsed, str):
            text = parsed.strip()
        else:
            text = _unwrap_singleton_brackets(text)
        return [part.strip() for part in text.replace(";", ",").split(",") if part.strip()]
    return [str(value).strip()] if str(value).strip() else []


def _parse_int_list(value: Any) -> List[int]:
    if value is None:
        return []
    candidates: list[Any]
    if isinstance(value, (list, tuple, set)):
        candidates = list(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except Exception:
            parsed = None
        if isinstance(parsed, list):
            candidates = list(parsed)
        elif parsed is not None:
            candidates = [parsed]
        else:
            candidates = [part.strip() for part in text.replace(";", ",").split(",") if part.strip()]
    else:
        candidates = [value]

    result: list[int] = []
    for item in candidates:
        if item is None:
            continue
        if isinstance(item, bool):
            continue
        if isinstance(item, int):
            result.append(item)
            continue
        text = _unwrap_singleton_brackets(str(item))
        if not text:
            continue
        try:
            result.append(int(text))
        except ValueError:
            continue
    return result


class Settings(BaseSettings):
    admin_email: str = "admin@example.com"
    admin_password: str = "admin123"
    admin_username: str = "admin"
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expires_minutes: int = 60
    postgres_dsn: str = (
        "postgresql+psycopg://postgres:postgres@postgres:5432/postgres"
    )
    # Keep Any here so env parser doesn't force JSON for list fields.
    default_languages: Any = ["en"]
    default_language: str = "en"
    # Optional: IDs of Telegram admins, protected from deletion.
    admin_ids: Any = []
    # Optional AI translator for backend seeding/repair.
    ai_api_key: str | None = None
    ai_base_url: str | None = None
    ai_model: str | None = None
    otp_bot_token: str | None = None
    otp_code_ttl_seconds: int = 300
    otp_max_attempts: int = 5

    @field_validator("default_languages", mode="before")
    @classmethod
    def _split_languages(cls, value: Any) -> List[str]:
        langs = _parse_string_list(value)
        return langs or ["en"]

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _split_admin_ids(cls, value: Any) -> List[int]:
        if not value:
            # Fallback to generic ADMIN_IDS (without BACKEND_ prefix).
            fallback = os.getenv("ADMIN_IDS")
            if fallback:
                value = fallback
        return _parse_int_list(value)

    @field_validator("default_language", mode="before")
    @classmethod
    def _normalize_default_language(cls, value: Any) -> str:
        if value is None:
            return "en"
        text = _unwrap_singleton_brackets(str(value)).strip()
        return text or "en"

    @field_validator("admin_email", "admin_username", "admin_password", mode="before")
    @classmethod
    def _normalize_scalar_settings(cls, value: Any) -> str:
        if value is None:
            return ""
        return _unwrap_singleton_brackets(str(value))

    @field_validator("otp_bot_token", mode="before")
    @classmethod
    def _fallback_otp_token(cls, v):
        return v or os.getenv("BOT_TOKEN")

    @field_validator("ai_api_key", mode="before")
    @classmethod
    def _fallback_ai_key(cls, v):
        return v or os.getenv("AI_API_KEY")

    @field_validator("ai_base_url", mode="before")
    @classmethod
    def _fallback_ai_base(cls, v):
        return v or os.getenv("AI_BASE_URL")

    @field_validator("ai_model", mode="before")
    @classmethod
    def _fallback_ai_model(cls, v):
        return v or os.getenv("AI_MODEL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="BACKEND_",
        extra="ignore",
    )


settings = Settings()
