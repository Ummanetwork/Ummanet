from datetime import datetime

from pydantic import BaseModel, Field

from app.bot.enums.roles import UserRole


class UserModel(BaseModel):
    id: int = Field(..., description="Internal auto-incrementing primary key")
    user_id: int = Field(..., description="Telegram user ID, unique per user")
    created_at: datetime = Field(
        ..., description="Timestamp of account creation (timezone-aware)"
    )
    tz_region: str | None = Field(
        None, description="Timezone region name (e.g., 'Europe/Moscow')"
    )
    tz_offset: str | None = Field(
        None, description="Manual timezone offset in the format '+03:00' or '-05:00'"
    )
    longitude: float | None = Field(
        None, description="Longitude coordinate of user's location"
    )
    latitude: float | None = Field(
        None, description="Latitude coordinate of user's location"
    )
    full_name: str | None = Field(None, description="User preferred full name")
    email: str | None = Field(None, description="Primary email address")
    phone_number: str | None = Field(None, description="Primary phone number")
    language_id: int = Field(..., description="Foreign key referencing languages table")
    language_code: str | None = Field(
        None, description="Preferred language code (e.g., 'ru', 'en')"
    )
    role: UserRole = Field(
        ..., description="User role within the bot (e.g., admin, user)"
    )
    is_alive: bool = Field(
        ..., description="Whether the user is considered active in the system"
    )
    banned: bool = Field(..., description="Whether the user is banned or blocked")
    email_verified: bool | None = Field(False, description="Email verified flag")
    phone_verified: bool | None = Field(False, description="Phone verified flag")
    class Config:
        from_attributes = True
        frozen = True
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "id": 1,
                "user_id": 123456789,
                "created_at": "2025-06-01T12:00:00+03:00",
                "tz_region": "Europe/Moscow",
            "tz_offset": "+03:00",
            "longitude": 37.6173,
            "latitude": 55.7558,
            "full_name": "РР±РЅ РЎРёРЅР°",
            "email": "ibn.sina@example.com",
            "phone_number": "+971500000000",
            "language_id": 1,
            "language_code": "ru",
            "role": "user",
            "is_alive": True,
            "banned": False,
            }
        }
