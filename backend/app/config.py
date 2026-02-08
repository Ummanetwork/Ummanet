from typing import List
import os

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    default_languages: List[str] = ["en"]
    default_language: str = "en"
    # Optional: IDs of Telegram admins, protected from deletion
    admin_ids: List[int] = []
    # Optional AI translator for backend seeding/repair
    ai_api_key: str | None = None
    ai_base_url: str | None = None
    ai_model: str | None = None
    otp_bot_token: str | None = None
    otp_code_ttl_seconds: int = 300
    otp_max_attempts: int = 5

    @field_validator("default_languages", mode="before")
    @classmethod
    def _split_languages(cls, value):
        if isinstance(value, str):
            items = [item.strip() for item in value.split(",")]
            return [item for item in items if item]
        return value

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _split_admin_ids(cls, value):
        if not value:
            # Fallback to generic ADMIN_IDS (without BACKEND_ prefix)
            fallback = os.getenv("ADMIN_IDS")
            if fallback:
                value = fallback
        if isinstance(value, str):
            items = []
            for part in value.replace(";", ",").split(","):
                part = part.strip()
                if not part:
                    continue
                try:
                    items.append(int(part))
                except ValueError:
                    continue
            return items
        return value

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
