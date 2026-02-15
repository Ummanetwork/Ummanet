from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import asyncio
import json
import uuid
import secrets
import hashlib
from typing import Any, Dict, Iterable, List, Optional
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
    Body,
    Request,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import StreamingResponse
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, Field, field_validator
import re
import logging
import requests
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Date,
    Integer,
    ForeignKey,
    BigInteger,
    LargeBinary,
    MetaData,
    String,
    Table,
    Text,
    Numeric,
    and_,
    or_,
    delete,
    func,
    insert,
    select,
    literal,
    text,
    update,
)
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.config import settings
from app.database import engine, get_session
from app.default_translation_keys import DEFAULT_TRANSLATION_KEYS
from app.default_translations import DEFAULT_TRANSLATIONS
from app.ai_translate import AITranslator
from shared.contract_templates import CONTRACT_TEMPLATES_TREE
from shared.document_tree import ALL_DOCUMENT_TOPIC_LOOKUP, DOCUMENT_TREE
from shared.link_slots import DEFAULT_LINKS, LINK_SLOTS
metadata = MetaData()
LANGUAGE_LABELS = {
    "en": "English",
    "ru": "\\u0420\\u0443\\u0441\\u0441\\u043a\\u0438\\u0439",
    "ar": "\\u0627\\u0644\\u0639\\u0631\\u0628\\u064a\\u0629",
    "tr": "T\\u00fcrk\\u00e7e",
    "dev": "DEV (identifiers)",
}
LINK_SLOT_SLUGS = {slot["slug"] for slot in LINK_SLOTS}
BLACKLIST_MEDIA_MAX_BYTES = 25 * 1024 * 1024
BLACKLIST_ALLOWED_MEDIA_PREFIXES = ("image/", "video/")
OTP_DEFAULT_TTL_SECONDS = 300
OTP_DEFAULT_ATTEMPTS = 5
OWNER_ROLE = "owner"
SUPERADMIN_ROLE = "superadmin"
DEFAULT_ADMIN_ROLE = "admin_users"
ADMIN_LANG_ROLE = "admin_languages"
ADMIN_LINKS_ROLE = "admin_links"
ADMIN_BLACKLIST_ROLE = "admin_blacklist"
ADMIN_DOCS_ROLE = "admin_documents"
ADMIN_TEMPLATES_ROLE = "admin_templates"
ADMIN_WORK_ITEMS_VIEW_ROLE = "admin_work_items_view"
ADMIN_WORK_ITEMS_MANAGE_ROLE = "admin_work_items_manage"
SCHOLAR_ROLE = "scholar"

TZ_NIKAH_ROLE = "tz_nikah"
TZ_INHERITANCE_ROLE = "tz_inheritance"
TZ_SPOUSE_SEARCH_ROLE = "tz_spouse_search"
TZ_COURTS_ROLE = "tz_courts"
TZ_GOOD_DEEDS_ROLE = "tz_good_deeds"
TZ_CONTRACTS_ROLE = "tz_contracts"
TZ_EXECUTION_ROLE = "tz_execution"
SHARIAH_CHIEF_ROLE = "shariah_chief"
SHARIAH_OBSERVER_ROLE = "shariah_observer"
users_table = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True),
    # Telegram user ids may exceed 32-bit; use BigInteger to avoid ::INTEGER casts
    Column("user_id", BigInteger, nullable=False),
    Column("created_at", DateTime(timezone=True)),
    Column("language_id", Integer),
    Column("role", String(50)),
    Column("is_alive", Boolean, nullable=False, default=True),
    Column("banned", Boolean, nullable=False, default=False),
    # Contact & verification fields (may be NULL)
    Column("full_name", Text),
    Column("email", Text),
    Column("phone_number", Text),
    Column("email_verified", Boolean, nullable=False, server_default=func.false()),
    Column("phone_verified", Boolean, nullable=False, server_default=func.false()),
    # Unban request fields
    Column("unban_request_text", Text),
    Column("unban_requested_at", DateTime(timezone=True)),
)
languages_table = Table(
    "languages",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("code", String(32), nullable=False, unique=True),
    Column("is_default", Boolean, nullable=False, default=False),
)
translation_keys_table = Table(
    "translation_keys",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("identifier", Text, nullable=False, unique=True),
    Column("description", Text),
)
translations_table = Table(
    "translations",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("language_id", Integer, nullable=False),
    Column("key_id", Integer, nullable=False),
    Column("value", Text),
)
notifications_table = Table(
    "notifications",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", BigInteger, nullable=False),
    Column("kind", String(64), nullable=False),
    Column("payload", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("sent_at", DateTime(timezone=True)),
)
work_items_table = Table(
    "work_items",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("topic", String(64), nullable=False),  # nikah|inheritance|spouse_search|courts
    Column("kind", String(64), nullable=False),  # scholar_request|moderation_incident|needs_review|...
    Column("status", String(32), nullable=False, server_default="new"),
    Column("priority", String(16), nullable=False, server_default="normal"),
    Column("created_by_user_id", BigInteger, nullable=True),
    Column("target_user_id", BigInteger, nullable=True),
    Column("assignee_admin_id", Integer, ForeignKey("admin_accounts.id", ondelete="SET NULL"), nullable=True),
    Column("payload", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
    Column("done_at", DateTime(timezone=True), nullable=True),
)
work_item_events_table = Table(
    "work_item_events",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("work_item_id", Integer, ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False),
    Column("actor_admin_id", Integer, ForeignKey("admin_accounts.id", ondelete="SET NULL"), nullable=True),
    Column("event_type", String(32), nullable=False),  # comment|status|assign|notify_user
    Column("message", Text, nullable=True),
    Column("payload", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
court_cases_table = Table(
    "court_cases",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("case_number", Text, nullable=True),
    Column("user_id", BigInteger, nullable=False),
    Column("category", Text, nullable=False),
    Column("plaintiff", Text, nullable=False),
    Column("defendant", Text, nullable=False),
    Column("claim", Text, nullable=False),
    Column("amount", Numeric, nullable=True),
    Column("evidence", Text, nullable=True),
    Column("status", Text, nullable=False),
    Column("sent_to_scholar", Boolean, nullable=False, server_default=func.false()),
    Column(
        "responsible_admin_id",
        Integer,
        ForeignKey("admin_accounts.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("scholar_id", Text, nullable=True),
    Column("scholar_name", Text, nullable=True),
    Column("scholar_contact", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
)
contracts_table = Table(
    "contracts",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", BigInteger, nullable=True),
    Column("type", Text, nullable=False),
    Column("template_topic", Text, nullable=True),
    Column("language", Text, nullable=True),
    Column("data", Text, nullable=True),
    Column("rendered_text", Text, nullable=True),
    Column("status", Text, nullable=True),
    Column("invite_code", Text, nullable=True),
    Column(
        "responsible_admin_id",
        Integer,
        ForeignKey("admin_accounts.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("scholar_id", Text, nullable=True),
    Column("scholar_name", Text, nullable=True),
    Column("scholar_contact", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
)
good_deeds_table = Table(
    "good_deeds",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", BigInteger, nullable=False),
    Column("title", Text, nullable=False),
    Column("description", Text, nullable=False),
    Column("city", Text, nullable=False),
    Column("country", Text, nullable=False),
    Column("help_type", Text, nullable=False),
    Column("amount", Numeric, nullable=True),
    Column("comment", Text, nullable=True),
    Column("status", Text, nullable=False, server_default="pending"),
    Column("approved_category", Text, nullable=True),
    Column("review_comment", Text, nullable=True),
    Column(
        "reviewed_by_admin_id",
        Integer,
        ForeignKey("admin_accounts.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("clarification_text", Text, nullable=True),
    Column("clarification_attachment", Text, nullable=True),
    Column("history", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
    Column("approved_at", DateTime(timezone=True), nullable=True),
    Column("completed_at", DateTime(timezone=True), nullable=True),
)
good_deed_needy_table = Table(
    "good_deed_needy",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("created_by_user_id", BigInteger, nullable=False),
    Column("person_type", Text, nullable=False),
    Column("city", Text, nullable=False),
    Column("country", Text, nullable=False),
    Column("reason", Text, nullable=False),
    Column("allow_zakat", Boolean, nullable=False, server_default=func.false()),
    Column("allow_fitr", Boolean, nullable=False, server_default=func.false()),
    Column("sadaqa_only", Boolean, nullable=False, server_default=func.false()),
    Column("comment", Text, nullable=True),
    Column("status", Text, nullable=False, server_default="pending"),
    Column("review_comment", Text, nullable=True),
    Column(
        "reviewed_by_admin_id",
        Integer,
        ForeignKey("admin_accounts.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("history", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
    Column("approved_at", DateTime(timezone=True), nullable=True),
)
good_deed_confirmations_table = Table(
    "good_deed_confirmations",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("good_deed_id", Integer, ForeignKey("good_deeds.id", ondelete="CASCADE"), nullable=False),
    Column("created_by_user_id", BigInteger, nullable=False),
    Column("text", Text, nullable=True),
    Column("attachment", Text, nullable=True),
    Column("status", Text, nullable=False, server_default="pending"),
    Column("review_comment", Text, nullable=True),
    Column(
        "reviewed_by_admin_id",
        Integer,
        ForeignKey("admin_accounts.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
    Column("reviewed_at", DateTime(timezone=True), nullable=True),
)
shariah_admin_applications_table = Table(
    "shariah_admin_applications",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", BigInteger, nullable=False),
    Column("full_name", Text, nullable=False),
    Column("country", Text, nullable=False),
    Column("city", Text, nullable=False),
    Column("education_place", Text, nullable=False),
    Column("education_completed", Boolean, nullable=False, server_default=func.false()),
    Column("education_details", Text, nullable=True),
    Column("knowledge_areas", Text, nullable=True),
    Column("experience", Text, nullable=True),
    Column("responsibility_accepted", Boolean, nullable=False, server_default=func.false()),
    Column("status", Text, nullable=False, server_default="pending_intro"),
    Column("meeting_type", Text, nullable=True),
    Column("meeting_link", Text, nullable=True),
    Column("meeting_at", DateTime(timezone=True), nullable=True),
    Column("decision_comment", Text, nullable=True),
    Column(
        "decision_by_admin_id",
        Integer,
        ForeignKey("admin_accounts.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("assigned_roles", Text, nullable=True),
    Column("history", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
)
channels_table = Table(
    "channels",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("lang", String(32), nullable=False),
    Column("kind", String(128), nullable=False),
    Column("url", Text, nullable=False),
)
knowledge_documents_table = Table(
    "knowledge_documents",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("topic", String(128), nullable=False),
    Column("language_id", Integer, nullable=False),
    Column("filename", String(255), nullable=False),
    Column("content_type", String(128), nullable=False),
    Column("content", LargeBinary, nullable=False),
    Column("size", Integer, nullable=False),
    Column("uploaded_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
)

blacklist_table = Table(
    "blacklist",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("date_added", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("name", Text, nullable=False),
    Column("phone", Text, nullable=True),
    Column("birthdate", Date, nullable=True),
    Column("city", Text, nullable=True),
    Column("is_active", Boolean, nullable=False, server_default=func.false()),
)
blacklist_complaints_table = Table(
    "blacklist_complaints",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("blacklist_id", BigInteger, ForeignKey("blacklist.id", ondelete="CASCADE"), nullable=False),
    Column("complaint_date", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("added_by", Text, nullable=False),
    Column("added_by_phone", Text, nullable=True),
    Column("added_by_id", BigInteger, nullable=True),
    Column("reason", Text, nullable=False),
)
blacklist_appeals_table = Table(
    "blacklist_appeals",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("blacklist_id", BigInteger, ForeignKey("blacklist.id", ondelete="CASCADE"), nullable=False),
    Column("appeal_date", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("is_appeal", Boolean, nullable=False, server_default=func.false()),
    Column("appeal_by", Text, nullable=False),
    Column("appeal_by_phone", Text, nullable=True),
    Column("appeal_by_id", BigInteger, nullable=True),
    Column("reason", Text, nullable=False),
)
blacklist_complaint_media_table = Table(
    "blacklist_complaint_media",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column(
        "complaint_id",
        BigInteger,
        ForeignKey("blacklist_complaints.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("filename", Text, nullable=False),
    Column("content_type", Text, nullable=False),
    Column("content", LargeBinary, nullable=False),
    Column("size", Integer, nullable=False),
    Column("uploaded_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
blacklist_appeal_media_table = Table(
    "blacklist_appeal_media",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column(
        "appeal_id",
        BigInteger,
        ForeignKey("blacklist_appeals.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("filename", Text, nullable=False),
    Column("content_type", Text, nullable=False),
    Column("content", LargeBinary, nullable=False),
    Column("size", Integer, nullable=False),
    Column("uploaded_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
roles_table = Table(
    "roles",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("slug", String(64), unique=True, nullable=False),
    Column("title", String(255), nullable=False),
    Column("description", Text),
)
admin_accounts_table = Table(
    "admin_accounts",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("username", String(128), unique=True, nullable=False),
    Column("password_hash", String(255), nullable=False),
    Column("telegram_id", BigInteger, nullable=True),
    Column("is_active", Boolean, nullable=False, server_default=text("true")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
admin_account_roles_table = Table(
    "admin_account_roles",
    metadata,
    Column("admin_account_id", Integer, ForeignKey("admin_accounts.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)
login_challenges_table = Table(
    "login_challenges",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("admin_account_id", Integer, ForeignKey("admin_accounts.id", ondelete="CASCADE"), nullable=False),
    Column("pending_token", String(128), unique=True, nullable=False),
    Column("otp_code", String(16), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("attempts_left", Integer, nullable=False, default=5),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
class LegacyLoginRequest(BaseModel):
    email: EmailStr
    password: str


class ServiceLoginRequest(BaseModel):
    api_key: str
    service: str = "bot"

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
class ProfileResponse(BaseModel):
    username: str
    roles: List[str]
    admin_account_id: Optional[int] = None
class UserOut(BaseModel):
    id: int
    user_id: int
    created_at: Optional[datetime]
    language_code: Optional[str]
    role: Optional[str]
    is_alive: bool
    banned: bool
    full_name: Optional[str] | None = None
    email: Optional[str] | None = None
    phone_number: Optional[str] | None = None
    email_verified: bool | None = None
    phone_verified: bool | None = None
    unban_request_text: Optional[str] | None = None
    unban_requested_at: Optional[datetime] | None = None
class CreateUserIn(BaseModel):
    telegram_user_id: int = Field(..., ge=1)
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    language_code: Optional[str] = None
    role: Optional[str] = None

class BanRequest(BaseModel):
    banned: bool

class AliveRequest(BaseModel):
    is_alive: bool
class LanguageOut(BaseModel):
    id: int
    code: str
    is_default: bool
class LanguageCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=32)
    is_default: bool = False
class TranslationRow(BaseModel):
    identifier: str
    value: Optional[str] = None
class TranslationUpdate(BaseModel):
    language: str = Field(..., description="Language code")
    identifier: str = Field(..., description="Translation key identifier")
    value: Optional[str] = Field(None, description="Translated phrase")


async def _parse_translation_update(
    request: Request,
    payload: Any = Body(default=None),
) -> TranslationUpdate:
    data: Any = payload
    if data is None:
        try:
            data = await request.json()
        except Exception:
            data = {}
    if isinstance(data, dict) and isinstance(data.get("payload"), dict):
        data = data["payload"]
    if isinstance(data, list):
        if data and isinstance(data[0], dict):
            data = data[0]
        else:
            data = {}
    try:
        return TranslationUpdate.model_validate(data or {})
    except Exception as exc:
        from pydantic import ValidationError

        if isinstance(exc, ValidationError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.errors(),
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
class LinkLanguageOut(BaseModel):
    code: str
    label: str
class LinkSlotOut(BaseModel):
    slug: str
    titles: Dict[str, str]
class LinkSettingsResponse(BaseModel):
    languages: List[LinkLanguageOut]
    slots: List[LinkSlotOut]
    links: Dict[str, Dict[str, Optional[str]]]
class LinkSlotUpdate(BaseModel):
    language: str
    url: Optional[str] = None
class LinkSlotResolveResponse(BaseModel):
    slug: str
    links: Dict[str, Optional[str]]
class KnowledgeDocumentOut(BaseModel):
    id: int
    topic: str
    language_code: str
    filename: str
    size: int
    uploaded_at: datetime


class BlacklistIdentity(BaseModel):
    name: str
    phone: Optional[str] | None = None
    birthdate: Optional[date] | None = None
    city: Optional[str] | None = None


class BlacklistMediaOut(BaseModel):
    id: int
    filename: str
    content_type: Optional[str] | None = None
    size: int
    uploaded_at: datetime


class BlacklistEntryOut(BlacklistIdentity):
    id: int
    date_added: datetime
    is_active: bool
    complaints_count: int = 0
    appeals_count: int = 0


class BlacklistComplaintOut(BaseModel):
    id: int
    blacklist_id: int
    complaint_date: datetime
    added_by: str
    added_by_phone: Optional[str] | None = None
    added_by_id: Optional[int] | None = None
    reason: str
    media: List[BlacklistMediaOut] = []


class BlacklistAppealOut(BaseModel):
    id: int
    blacklist_id: int
    appeal_date: datetime
    is_appeal: bool
    appeal_by: str
    appeal_by_phone: Optional[str] | None = None
    appeal_by_id: Optional[int] | None = None
    reason: str
    media: List[BlacklistMediaOut] = []


class BlacklistEntryDetail(BlacklistEntryOut):
    complaints: List[BlacklistComplaintOut]
    appeals: List[BlacklistAppealOut]


class BlacklistStatusUpdate(BaseModel):
    is_active: bool


class BlacklistComplaintCreate(BlacklistIdentity):
    reason: str
    added_by: str
    added_by_phone: Optional[str] | None = None
    added_by_id: Optional[int] | None = None


class BlacklistAppealCreate(BlacklistIdentity):
    reason: str
    is_appeal: bool = True
    appeal_by: str
    appeal_by_phone: Optional[str] | None = None
    appeal_by_id: Optional[int] | None = None


class BlacklistComplaintResponse(BaseModel):
    created_entry: bool
    blacklist: BlacklistEntryOut
    complaint: BlacklistComplaintOut


class BlacklistAppealResponse(BaseModel):
    blacklist: BlacklistEntryOut
    appeal: BlacklistAppealOut


class RoleOut(BaseModel):
    id: int
    slug: str
    title: str
    description: Optional[str] = None


class RoleCreate(BaseModel):
    slug: str = Field(..., min_length=2, max_length=64)
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class AdminAccountOut(BaseModel):
    id: int
    username: str
    telegram_id: Optional[int]
    is_active: bool
    roles: List[str]


class AssignRoleRequest(BaseModel):
    admin_account_id: int


async def _parse_assign_role_request(request: Request) -> AssignRoleRequest:
    data: Any = {}
    try:
        data = await request.json()
    except Exception:
        data = {}
    if isinstance(data, dict) and isinstance(data.get("payload"), dict):
        data = data["payload"]
    if isinstance(data, list):
        if not data:
            data = {}
        else:
            first = data[0]
            if isinstance(first, dict):
                data = first
            elif isinstance(first, int):
                data = {"admin_account_id": first}
            elif isinstance(first, str):
                first_str = first.strip()
                if first_str.isdigit():
                    data = {"admin_account_id": int(first_str)}
                else:
                    data = {"admin_account_id": first_str}
            else:
                data = {}
    elif isinstance(data, int):
        data = {"admin_account_id": data}
    elif isinstance(data, str):
        data_str = data.strip()
        data = {"admin_account_id": int(data_str)} if data_str.isdigit() else {"admin_account_id": data_str}
    try:
        return AssignRoleRequest.model_validate(data or {})
    except Exception as exc:
        from pydantic import ValidationError

        if isinstance(exc, ValidationError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.errors(),
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


class AdminAccountCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=128)
    password: str = Field("", min_length=0, max_length=255)
    telegram_id: Optional[int] = Field(None, ge=1)
    roles: Optional[List[str]] = None

    @field_validator("telegram_id", mode="before")
    @classmethod
    def _coerce_telegram_id(cls, v):
        if v is None or v == "":
            return None
        try:
            return int(v)
        except Exception:
            raise ValueError("telegram_id must be an integer")


class AdminAccountUpdate(BaseModel):
    password: Optional[str] = Field(None, min_length=0, max_length=255)
    roles: Optional[List[str]] = None


class LoginOtpRequest(BaseModel):
    username: str
    password: str


class VerifyOtpRequest(BaseModel):
    pending_token: str
    code: str


class LoginOtpResponse(BaseModel):
    pending_token: str
    expires_in: int


class WorkItemOut(BaseModel):
    id: int
    topic: str
    kind: str
    status: str
    priority: str
    created_by_user_id: Optional[int] = None
    target_user_id: Optional[int] = None
    assignee_admin_id: Optional[int] = None
    payload: Optional[dict] = None
    created_at: datetime
    updated_at: datetime
    done_at: Optional[datetime] = None


class WorkItemEventOut(BaseModel):
    id: int
    work_item_id: int
    actor_admin_id: Optional[int] = None
    event_type: str
    message: Optional[str] = None
    payload: Optional[dict] = None
    created_at: datetime


class WorkItemStatusUpdate(BaseModel):
    status: str = Field(..., min_length=2, max_length=32)


async def _parse_work_item_status_request(
    request: Request,
    payload: Any = Body(default=None),
) -> WorkItemStatusUpdate:
    data: Any = payload
    if data is None:
        try:
            data = await request.json()
        except Exception:
            data = {}
    if isinstance(data, dict) and "payload" in data:
        data = data["payload"]
    if isinstance(data, list):
        if not data:
            data = {}
        else:
            first = data[0]
            if isinstance(first, dict):
                data = first
            elif isinstance(first, str):
                data = {"status": first}
            elif isinstance(first, int):
                data = {"status": str(first)}
            else:
                data = {}
    elif isinstance(data, str):
        data = {"status": data}
    try:
        return WorkItemStatusUpdate.model_validate(data or {})
    except Exception as exc:
        from pydantic import ValidationError

        if isinstance(exc, ValidationError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.errors(),
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


class WorkItemCommentCreate(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


class WorkItemNotifyUser(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)


class CourtCaseOut(BaseModel):
    id: int
    case_number: Optional[str] = None
    user_id: int
    category: str
    plaintiff: str
    defendant: str
    claim: str
    amount: Optional[float] = None
    evidence: Optional[list] = None
    status: str
    sent_to_scholar: bool
    responsible_admin_id: Optional[int] = None
    responsible_admin_username: Optional[str] = None
    scholar_id: Optional[str] = None
    scholar_name: Optional[str] = None
    scholar_contact: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class CourtCaseUpdate(BaseModel):
    status: Optional[str] = Field(default=None, min_length=2, max_length=32)
    scholar_id: Optional[str] = Field(default=None, max_length=128)
    scholar_name: Optional[str] = Field(default=None, max_length=256)
    scholar_contact: Optional[str] = Field(default=None, max_length=512)


async def _parse_court_case_update_request(
    request: Request,
    payload: Any = Body(default=None),
) -> CourtCaseUpdate:
    data: Any = payload
    if data is None:
        try:
            data = await request.json()
        except Exception:
            data = {}
    if isinstance(data, dict) and "payload" in data:
        data = data["payload"]
    if isinstance(data, list):
        if data:
            first = data[0]
            if isinstance(first, dict):
                data = first
            elif isinstance(first, str):
                data = {"status": first}
            else:
                data = {}
        else:
            data = {}
    elif isinstance(data, str):
        data = {"status": data}
    try:
        return CourtCaseUpdate.model_validate(data or {})
    except Exception as exc:
        from pydantic import ValidationError

        if isinstance(exc, ValidationError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.errors(),
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


class CourtCaseAssign(BaseModel):
    assignee_admin_id: Optional[int] = None


class ContractOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    contract_type: str
    template_topic: Optional[str] = None
    language: Optional[str] = None
    data: Optional[dict] = None
    rendered_text: Optional[str] = None
    status: Optional[str] = None
    invite_code: Optional[str] = None
    responsible_admin_id: Optional[int] = None
    responsible_admin_username: Optional[str] = None
    scholar_id: Optional[str] = None
    scholar_name: Optional[str] = None
    scholar_contact: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ContractUpdate(BaseModel):
    status: Optional[str] = Field(default=None, min_length=2, max_length=32)
    scholar_id: Optional[str] = Field(default=None, max_length=128)
    scholar_name: Optional[str] = Field(default=None, max_length=256)
    scholar_contact: Optional[str] = Field(default=None, max_length=512)


async def _parse_contract_update_request(
    request: Request,
    payload: Any = Body(default=None),
) -> ContractUpdate:
    data: Any = payload
    if data is None:
        try:
            data = await request.json()
        except Exception:
            data = {}
    if isinstance(data, dict) and "payload" in data:
        data = data["payload"]
    if isinstance(data, list):
        if data:
            first = data[0]
            if isinstance(first, dict):
                data = first
            elif isinstance(first, str):
                data = {"status": first}
            else:
                data = {}
        else:
            data = {}
    elif isinstance(data, str):
        data = {"status": data}
    try:
        return ContractUpdate.model_validate(data or {})
    except Exception as exc:
        from pydantic import ValidationError

        if isinstance(exc, ValidationError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.errors(),
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


class ContractAssign(BaseModel):
    assignee_admin_id: Optional[int] = None


async def _parse_contract_assign_request(
    request: Request,
    payload: Any = Body(default=None),
) -> ContractAssign:
    data: Any = payload
    if data is None:
        try:
            data = await request.json()
        except Exception:
            data = {}
    if isinstance(data, dict) and isinstance(data.get("payload"), dict):
        data = data["payload"]
    if isinstance(data, list):
        if not data:
            data = {}
        else:
            first = data[0]
            if isinstance(first, dict):
                data = first
            elif isinstance(first, int):
                data = {"assignee_admin_id": first}
            elif isinstance(first, str) and first.strip().isdigit():
                data = {"assignee_admin_id": int(first.strip())}
            else:
                data = {}
    elif isinstance(data, int):
        data = {"assignee_admin_id": data}
    elif isinstance(data, str):
        data_str = data.strip()
        if data_str.isdigit():
            data = {"assignee_admin_id": int(data_str)}
    try:
        return ContractAssign.model_validate(data or {})
    except Exception as exc:
        from pydantic import ValidationError

        if isinstance(exc, ValidationError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.errors(),
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


class GoodDeedOut(BaseModel):
    id: int
    user_id: int
    user_full_name: Optional[str] = None
    user_phone: Optional[str] = None
    user_email: Optional[str] = None
    title: str
    description: str
    city: str
    country: str
    help_type: str
    amount: Optional[float] = None
    comment: Optional[str] = None
    status: str
    approved_category: Optional[str] = None
    review_comment: Optional[str] = None
    reviewed_by_admin_id: Optional[int] = None
    clarification_text: Optional[str] = None
    clarification_attachment: Optional[dict] = None
    history: Optional[list] = None
    created_at: datetime
    updated_at: datetime
    approved_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class GoodDeedDecision(BaseModel):
    status: str = Field(..., min_length=2, max_length=32)
    review_comment: str = Field(..., min_length=1, max_length=2000)
    approved_category: Optional[str] = Field(default=None, max_length=32)


class GoodDeedNeedyOut(BaseModel):
    id: int
    created_by_user_id: int
    user_full_name: Optional[str] = None
    user_phone: Optional[str] = None
    user_email: Optional[str] = None
    person_type: str
    city: str
    country: str
    reason: str
    allow_zakat: bool
    allow_fitr: bool
    sadaqa_only: bool
    comment: Optional[str] = None
    status: str
    review_comment: Optional[str] = None
    reviewed_by_admin_id: Optional[int] = None
    history: Optional[list] = None
    created_at: datetime
    updated_at: datetime
    approved_at: Optional[datetime] = None


class GoodDeedNeedyDecision(BaseModel):
    status: str = Field(..., min_length=2, max_length=32)
    review_comment: str = Field(..., min_length=1, max_length=2000)


class GoodDeedConfirmationOut(BaseModel):
    id: int
    good_deed_id: int
    good_deed_title: Optional[str] = None
    good_deed_status: Optional[str] = None
    created_by_user_id: int
    user_full_name: Optional[str] = None
    user_phone: Optional[str] = None
    user_email: Optional[str] = None
    text: Optional[str] = None
    attachment: Optional[dict] = None
    status: str
    review_comment: Optional[str] = None
    reviewed_by_admin_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    reviewed_at: Optional[datetime] = None


class GoodDeedConfirmationDecision(BaseModel):
    status: str = Field(..., min_length=2, max_length=32)
    review_comment: str = Field(..., min_length=1, max_length=2000)


class ShariahAdminApplicationOut(BaseModel):
    id: int
    user_id: int
    user_full_name: Optional[str] = None
    user_phone: Optional[str] = None
    user_email: Optional[str] = None
    full_name: str
    country: str
    city: str
    education_place: str
    education_completed: bool
    education_details: Optional[str] = None
    knowledge_areas: Optional[list] = None
    experience: Optional[str] = None
    responsibility_accepted: bool
    status: str
    meeting_type: Optional[str] = None
    meeting_link: Optional[str] = None
    meeting_at: Optional[datetime] = None
    decision_comment: Optional[str] = None
    decision_by_admin_id: Optional[int] = None
    assigned_roles: Optional[list] = None
    history: Optional[list] = None
    created_at: datetime
    updated_at: datetime


class ShariahAdminSchedule(BaseModel):
    meeting_type: str = Field(..., min_length=2, max_length=32)
    meeting_link: str = Field(..., min_length=3, max_length=1024)
    meeting_at: datetime


class ShariahAdminDecision(BaseModel):
    status: str = Field(..., min_length=2, max_length=32)
    comment: str = Field(..., min_length=1, max_length=2000)
    roles: Optional[List[str]] = None


class ScholarOut(BaseModel):
    id: int
    username: str
    telegram_id: Optional[int] = None


async def _parse_court_case_assign_request(
    request: Request,
    payload: Any = Body(default=None),
) -> CourtCaseAssign:
    data: Any = payload
    if data is None:
        try:
            data = await request.json()
        except Exception:
            data = {}
    if isinstance(data, dict) and isinstance(data.get("payload"), dict):
        data = data["payload"]
    if isinstance(data, list):
        if not data:
            data = {}
        else:
            first = data[0]
            if isinstance(first, dict):
                data = first
            elif isinstance(first, int):
                data = {"assignee_admin_id": first}
            elif isinstance(first, str) and first.strip().isdigit():
                data = {"assignee_admin_id": int(first.strip())}
            else:
                data = {}
    elif isinstance(data, int):
        data = {"assignee_admin_id": data}
    elif isinstance(data, str):
        data_str = data.strip()
        if data_str.isdigit():
            data = {"assignee_admin_id": int(data_str)}
    try:
        return CourtCaseAssign.model_validate(data or {})
    except Exception as exc:
        from pydantic import ValidationError

        if isinstance(exc, ValidationError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.errors(),
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


async def _parse_good_deed_decision_request(
    request: Request,
    payload: Any = Body(default=None),
) -> GoodDeedDecision:
    data: Any = payload
    if data is None:
        try:
            data = await request.json()
        except Exception:
            data = {}
    if isinstance(data, dict) and "payload" in data:
        data = data["payload"]
    if isinstance(data, list):
        if data:
            first = data[0]
            if isinstance(first, dict):
                data = first
            elif isinstance(first, str):
                data = {"status": first}
            else:
                data = {}
        else:
            data = {}
    elif isinstance(data, str):
        data = {"status": data}
    try:
        return GoodDeedDecision.model_validate(data or {})
    except Exception as exc:
        from pydantic import ValidationError

        if isinstance(exc, ValidationError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.errors(),
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


async def _parse_needy_decision_request(
    request: Request,
    payload: Any = Body(default=None),
) -> GoodDeedNeedyDecision:
    data: Any = payload
    if data is None:
        try:
            data = await request.json()
        except Exception:
            data = {}
    if isinstance(data, dict) and "payload" in data:
        data = data["payload"]
    if isinstance(data, list):
        if data:
            first = data[0]
            if isinstance(first, dict):
                data = first
            elif isinstance(first, str):
                data = {"status": first}
            else:
                data = {}
        else:
            data = {}
    elif isinstance(data, str):
        data = {"status": data}
    try:
        return GoodDeedNeedyDecision.model_validate(data or {})
    except Exception as exc:
        from pydantic import ValidationError

        if isinstance(exc, ValidationError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.errors(),
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


async def _parse_confirmation_decision_request(
    request: Request,
    payload: Any = Body(default=None),
) -> GoodDeedConfirmationDecision:
    data: Any = payload
    if data is None:
        try:
            data = await request.json()
        except Exception:
            data = {}
    if isinstance(data, dict) and "payload" in data:
        data = data["payload"]
    if isinstance(data, list):
        if data:
            first = data[0]
            if isinstance(first, dict):
                data = first
            elif isinstance(first, str):
                data = {"status": first}
            else:
                data = {}
        else:
            data = {}
    elif isinstance(data, str):
        data = {"status": data}
    try:
        return GoodDeedConfirmationDecision.model_validate(data or {})
    except Exception as exc:
        from pydantic import ValidationError

        if isinstance(exc, ValidationError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.errors(),
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


async def _parse_shariah_schedule_request(
    request: Request,
    payload: Any = Body(default=None),
) -> ShariahAdminSchedule:
    data: Any = payload
    if data is None:
        try:
            data = await request.json()
        except Exception:
            data = {}
    if isinstance(data, dict) and "payload" in data:
        data = data["payload"]
    if isinstance(data, list):
        if data and isinstance(data[0], dict):
            data = data[0]
        else:
            data = {}
    try:
        return ShariahAdminSchedule.model_validate(data or {})
    except Exception as exc:
        from pydantic import ValidationError

        if isinstance(exc, ValidationError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.errors(),
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


async def _parse_shariah_decision_request(
    request: Request,
    payload: Any = Body(default=None),
) -> ShariahAdminDecision:
    data: Any = payload
    if data is None:
        try:
            data = await request.json()
        except Exception:
            data = {}
    if isinstance(data, dict) and "payload" in data:
        data = data["payload"]
    if isinstance(data, list):
        if data and isinstance(data[0], dict):
            data = data[0]
        else:
            data = {}
    try:
        return ShariahAdminDecision.model_validate(data or {})
    except Exception as exc:
        from pydantic import ValidationError

        if isinstance(exc, ValidationError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.errors(),
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


class SpecFileOut(BaseModel):
    key: str
    filename: str
    title: str


class SpecContentOut(BaseModel):
    key: str
    filename: str
    content: str


class ContractTemplateOut(BaseModel):
    template: str
    topic: str
    titles: Dict[str, str]


class ContractTemplateCategoryOut(BaseModel):
    category: str
    titles: Dict[str, str]
    templates: List[ContractTemplateOut]
 
# Utilities for translations maintenance
_EMOJI_PREFIX_RE = re.compile(
    r"^\s*((?:[\u2600-\u27BF\u2700-\u27BF\u2B50\U0001F000-\U0001FFFF])+)[\s\-\u2013\u2014:]*",
    flags=re.UNICODE,
)
_PLACEHOLDER_RE = re.compile(r"\{[^}]+\}")


def _extract_icon_prefix(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    m = _EMOJI_PREFIX_RE.match(text)
    if m:
        icon = m.group(1).strip()
        return icon or None
    return None


def _ensure_placeholders(base: str, target: str) -> str:
    base_ph = set(_PLACEHOLDER_RE.findall(base or ""))
    tgt_ph = set(_PLACEHOLDER_RE.findall(target or ""))
    missing = [ph for ph in base_ph if ph not in tgt_ph]
    if not missing:
        return target
    suffix = (" " + " ".join(missing)).strip()
    return (target or "").rstrip() + (" " if target and not target.endswith(" ") else "") + suffix


def _repair_translations_internal(
    session: Session,
    targets_for_icons: List[str] | None = None,
    use_ru_for_missing: bool = True,
    ensure_placeholders: bool = True,
    translator: AITranslator | None = None,
    prefer_ai: bool = False,
) -> tuple[int, int, Dict[str, int]]:
    targets_for_icons = list(targets_for_icons or ["ar", "tr", "en"])

    # Languages
    langs = session.execute(
        select(languages_table.c.id, languages_table.c.code)
    ).mappings().all()
    if not langs:
        return (0, 0, {})
    code_by_id = {row["id"]: row["code"] for row in langs}
    id_by_code = {row["code"]: row["id"] for row in langs}
    ru_id = id_by_code.get("ru")

    # Keys
    keys = session.execute(
        select(translation_keys_table.c.id, translation_keys_table.c.identifier)
    ).mappings().all()
    if not keys:
        return (0, 0, {})
    key_id_to_ident = {row["id"]: row["identifier"] for row in keys}
    ident_to_key_id = {row["identifier"]: row["id"] for row in keys}

    # Translations
    tr_rows = session.execute(
        select(
            translations_table.c.id,
            translations_table.c.language_id,
            translations_table.c.key_id,
            translations_table.c.value,
        )
    ).mappings().all()

    translations: Dict[str, Dict[str, Dict[str, object]]] = {}
    for row in tr_rows:
        code = code_by_id.get(row["language_id"])
        ident = key_id_to_ident.get(row["key_id"])
        if not code or not ident:
            continue
        translations.setdefault(code, {})[ident] = {
            "id": row["id"],
            "value": row["value"],
            "key_id": row["key_id"],
            "language_id": row["language_id"],
        }

    per_lang_updated: Dict[str, int] = {code: 0 for code in id_by_code.keys()}
    total_updated = 0
    examined = 0

    ru_map = translations.get("ru", {}) if ru_id else {}
    ru_icons: Dict[str, Optional[str]] = {}
    for ident, payload_ru in ru_map.items():
        ru_val = (payload_ru.get("value") or "").strip()
        ru_icons[ident] = _extract_icon_prefix(ru_val)

    tf_icons = set(targets_for_icons)

    def _update(row_id: int, new_value: str) -> None:
        nonlocal total_updated
        session.execute(
            update(translations_table)
            .where(translations_table.c.id == row_id)
            .values(value=new_value)
        )
        total_updated += 1

    default_code = settings.default_language or "en"
    default_map = DEFAULT_TRANSLATIONS.get(default_code, {}) or {}

    def _compute_base_value(lang_code: str, ident: str) -> str:
        # 1) per-language built-in defaults
        val = (DEFAULT_TRANSLATIONS.get(lang_code, {}) or {}).get(ident)
        if val:
            return val
        # 2) RU DB value (to keep icons and real texts)
        ru_val = (ru_map.get(ident, {}).get("value") if ru_map else None)
        if ru_val:
            # If translator available and different language requested, prefer AI translation
            if translator and prefer_ai and lang_code not in ("ru", "dev"):
                try:
                    placeholders = list(_PLACEHOLDER_RE.findall(ru_val))
                    icon = ru_icons.get(ident)
                    translated = translator.translate(
                        text=str(ru_val),
                        target_lang=lang_code,
                        placeholders=placeholders,
                        emoji_prefix=icon,
                    )
                    if translated:
                        return translated
                except Exception:
                    pass
            return str(ru_val)
        # 3) default language built-in defaults
        val = (DEFAULT_TRANSLATIONS.get(default_code, {}) or {}).get(ident)
        if val:
            if translator and prefer_ai and lang_code not in (default_code, "dev"):
                try:
                    placeholders = list(_PLACEHOLDER_RE.findall(val))
                    icon = ru_icons.get(ident)
                    translated = translator.translate(
                        text=str(val),
                        target_lang=lang_code,
                        placeholders=placeholders,
                        emoji_prefix=icon,
                    )
                    if translated:
                        return translated
                except Exception:
                    pass
            return val
        # 4) dev language shows identifiers
        if lang_code == "dev":
            return ident
        # 5) humanized identifier
        return ident.replace(".", " ").replace("_", " ").title()

    # Walk across all languages and all keys; create missing rows and fix empties
    for lang_code, lang_id in id_by_code.items():
        by_ident = translations.setdefault(lang_code, {})
        for ident, key_id in ident_to_key_id.items():
            existing = by_ident.get(ident)
            if existing is None:
                examined += 1
                # Create new row
                value = _compute_base_value(lang_code, ident)
                icon = ru_icons.get(ident)
                if icon and lang_code in tf_icons and value and not _extract_icon_prefix(value):
                    value = f"{icon} " + value
                if ensure_placeholders and ru_map:
                    ru_val = (ru_map.get(ident, {}).get("value") if ru_map else None) or ""
                    value = _ensure_placeholders(ru_val, value)
                session.execute(
                    insert(translations_table).values(
                        language_id=lang_id,
                        key_id=key_id,
                        value=value,
                    )
                )
                total_updated += 1
                per_lang_updated[lang_code] = per_lang_updated.get(lang_code, 0) + 1
                continue

            # Row exists: fix empties and icons/placeholders
            examined += 1
            current_val = (existing.get("value") or "").strip()
            row_id = int(existing["id"])  # type: ignore[index]
            ru_val = (ru_map.get(ident, {}).get("value") if ru_map else None) or ""
            icon = ru_icons.get(ident)

            new_val = current_val
            changed = False

            if not new_val:
                base_val = _compute_base_value(lang_code, ident)
                if base_val:
                    new_val = base_val
                    changed = True

            # If value equals RU or equals default language text or equals humanized identifier,
            # and we have translator for non-RU language, convert it.
            if translator and prefer_ai and lang_code not in ("ru", "dev"):
                try:
                    base_candidates: list[str] = []
                    if ru_val:
                        base_candidates.append(str(ru_val).strip())
                    default_src = str(default_map.get(ident, "")).strip()
                    if default_src:
                        base_candidates.append(default_src)
                    humanized = ident.replace(".", " ").replace("_", " ").title()
                    base_candidates.append(humanized)
                    if new_val and new_val.strip() in base_candidates:
                        placeholders = list(_PLACEHOLDER_RE.findall(new_val))
                        translated = translator.translate(
                            text=new_val,
                            target_lang=lang_code,
                            placeholders=placeholders,
                            emoji_prefix=icon,
                        )
                        if translated and translated.strip() != new_val:
                            new_val = translated.strip()
                            changed = True
                except Exception:
                    pass

            if icon and lang_code in tf_icons:
                if new_val and not _extract_icon_prefix(new_val):
                    new_val = f"{icon} " + new_val
                    changed = True

            if ensure_placeholders and (ru_val or new_val):
                fixed = _ensure_placeholders(ru_val, new_val)
                if fixed != new_val:
                    new_val = fixed
                    changed = True

            if changed and new_val != current_val:
                _update(row_id, new_val)
                per_lang_updated[lang_code] = per_lang_updated.get(lang_code, 0) + 1

    return (total_updated, examined, {k: v for k, v in per_lang_updated.items() if v > 0})
app = FastAPI(title="Shariat Backend API")
logger = logging.getLogger(__name__)
_ai_translator: AITranslator | None = None
def _bootstrap_database() -> None:
    metadata.create_all(bind=engine)

    def _ensure_blacklist_identity_index(connection) -> None:
        connection.exec_driver_sql(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_blacklist_identity
            ON blacklist (
                name,
                COALESCE(phone, ''),
                COALESCE(birthdate, DATE '0001-01-01'),
                COALESCE(city, '')
            )
            """
        )
    def _ensure_court_cases_schema(connection) -> None:
        connection.exec_driver_sql(
            "ALTER TABLE court_cases ADD COLUMN IF NOT EXISTS case_number TEXT"
        )
        connection.exec_driver_sql(
            "ALTER TABLE court_cases ADD COLUMN IF NOT EXISTS sent_to_scholar BOOLEAN DEFAULT FALSE"
        )
        connection.exec_driver_sql(
            "ALTER TABLE court_cases ADD COLUMN IF NOT EXISTS responsible_admin_id INTEGER"
        )
        connection.exec_driver_sql(
            "ALTER TABLE court_cases ADD COLUMN IF NOT EXISTS scholar_id TEXT"
        )
        connection.exec_driver_sql(
            "ALTER TABLE court_cases ADD COLUMN IF NOT EXISTS scholar_name TEXT"
        )
        connection.exec_driver_sql(
            "ALTER TABLE court_cases ADD COLUMN IF NOT EXISTS scholar_contact TEXT"
        )
        connection.exec_driver_sql(
            "ALTER TABLE court_cases ADD COLUMN IF NOT EXISTS evidence TEXT"
        )
    def _ensure_contracts_schema(connection) -> None:
        connection.exec_driver_sql(
            "ALTER TABLE contracts ADD COLUMN IF NOT EXISTS invite_code TEXT"
        )
        connection.exec_driver_sql(
            "ALTER TABLE contracts ADD COLUMN IF NOT EXISTS responsible_admin_id INTEGER"
        )
        connection.exec_driver_sql(
            "ALTER TABLE contracts ADD COLUMN IF NOT EXISTS scholar_id TEXT"
        )
        connection.exec_driver_sql(
            "ALTER TABLE contracts ADD COLUMN IF NOT EXISTS scholar_name TEXT"
        )
        connection.exec_driver_sql(
            "ALTER TABLE contracts ADD COLUMN IF NOT EXISTS scholar_contact TEXT"
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_contracts_invite_code ON contracts(invite_code)"
        )
    def _humanize_identifier(identifier: str) -> str:
        parts = identifier.replace('.', ' ').replace('_', ' ').split()
        return ' '.join(part.capitalize() for part in parts)
    codes = list(settings.default_languages or [])
    # Ensure base languages always exist
    for base in ("ru", "en", "ar", "tr"):
        if base not in codes:
            codes.append(base)
    default_code = settings.default_language or (codes[0] if codes else "en")
    if default_code not in codes:
        codes.append(default_code)
    with engine.begin() as connection:
        _ensure_court_cases_schema(connection)
        _ensure_contracts_schema(connection)
        existing_roles = set(connection.execute(select(roles_table.c.slug)).scalars().all())
        system_roles = [
            (
                SUPERADMIN_ROLE,
                "Super Administrator",
                "Full access to all administrative actions.",
            ),
            (
                OWNER_ROLE,
                "Owner",
                "Full access; can manage superadmin and other roles.",
            ),
            (
                DEFAULT_ADMIN_ROLE,
                "Admin users",
                "Manages users (ban/unban/approve).",
            ),
            (
                ADMIN_LANG_ROLE,
                "Admin languages",
                "Manage languages and translations.",
            ),
            (
                ADMIN_LINKS_ROLE,
                "Admin links",
                "Manage external links for channels and resources.",
            ),
            (
                ADMIN_BLACKLIST_ROLE,
                "Admin blacklist",
                "Manage blacklist complaints, appeals and status.",
            ),
            (
                ADMIN_DOCS_ROLE,
                "Admin documents",
                "Manage knowledge base documents.",
            ),
            (
                ADMIN_TEMPLATES_ROLE,
                "Admin templates",
                "Manage contract/document templates and trees.",
            ),
            (
                ADMIN_WORK_ITEMS_VIEW_ROLE,
                "Admin work items (view)",
                "View assigned and topic-available work items.",
            ),
            (
                ADMIN_WORK_ITEMS_MANAGE_ROLE,
                "Admin work items (manage)",
                "Assign, update status, and notify users for work items.",
            ),
            (
                TZ_NIKAH_ROLE,
                "TZ: Nikah",
                "Responsible for Nikah technical specification tasks.",
            ),
            (
                TZ_INHERITANCE_ROLE,
                "TZ: Inheritance",
                "Responsible for Inheritance technical specification tasks.",
            ),
            (
                TZ_SPOUSE_SEARCH_ROLE,
                "TZ: Spouse search",
                "Responsible for Spouse search technical specification tasks.",
            ),
            (
                TZ_COURTS_ROLE,
                "TZ: Courts",
                "Responsible for Courts technical specification tasks.",
            ),
            (
                TZ_CONTRACTS_ROLE,
                "TZ: Contracts",
                "Responsible for Contracts technical specification tasks.",
            ),
            (
                TZ_GOOD_DEEDS_ROLE,
                "TZ: Good deeds",
                "Responsible for Good deeds technical specification tasks.",
            ),
            (
                TZ_EXECUTION_ROLE,
                "TZ: Execution",
                "Responsible for Execution technical specification tasks.",
            ),
            (
                SHARIAH_CHIEF_ROLE,
                "Shariah chief",
                "Main Shariah controller; assigns and revokes Shariah roles.",
            ),
            (
                SHARIAH_OBSERVER_ROLE,
                "Shariah observer",
                "Observer role for Shariah control.",
            ),
            (
                SCHOLAR_ROLE,
                "Scholar",
                "Scholar account (available for court case assignments).",
            ),
        ]
        for slug, title, description in system_roles:
            if slug not in existing_roles:
                connection.execute(
                    insert(roles_table).values(
                        slug=slug,
                        title=title,
                        description=description,
                    )
                )
        existing_admins = dict(
            connection.execute(
                select(admin_accounts_table.c.username, admin_accounts_table.c.id)
            ).all()
        )
        super_username = (settings.admin_username or "admin").strip() or "admin"
        if super_username not in existing_admins:
            bootstrap_admin_password = settings.admin_password
            if not bootstrap_admin_password:
                raise RuntimeError(
                    "BACKEND_ADMIN_PASSWORD is required to create the initial admin account."
                )
            telegram_id_seed = None
            if settings.admin_ids:
                try:
                    telegram_id_seed = int(settings.admin_ids[0])
                except Exception:
                    telegram_id_seed = None
            super_id = connection.execute(
                insert(admin_accounts_table)
                .values(
                    username=super_username,
                    password_hash=_hash_password(bootstrap_admin_password),
                    telegram_id=telegram_id_seed,
                    is_active=True,
                )
                .returning(admin_accounts_table.c.id)
            ).scalar_one()
        else:
            super_id = existing_admins[super_username]
            update_values: dict[str, object] = {"is_active": True}
            if settings.admin_ids:
                try:
                    update_values["telegram_id"] = int(settings.admin_ids[0])
                except Exception:
                    pass
            connection.execute(
                update(admin_accounts_table)
                .where(admin_accounts_table.c.id == super_id)
                .values(**update_values)
            )
        super_role_id = connection.execute(
            select(roles_table.c.id).where(roles_table.c.slug == SUPERADMIN_ROLE)
        ).scalar_one()
        assigned = connection.execute(
            select(admin_account_roles_table.c.admin_account_id).where(
                and_(
                    admin_account_roles_table.c.admin_account_id == super_id,
                    admin_account_roles_table.c.role_id == super_role_id,
                )
            )
        ).first()
        if not assigned:
            connection.execute(
                insert(admin_account_roles_table).values(
                    admin_account_id=super_id, role_id=super_role_id
                )
            )
        # Do not auto-create owner with a predictable password.
        # If an owner account already exists from previous deployments, keep role bindings valid.
        owner_username = "owner"
        owner_id = connection.execute(
            select(admin_accounts_table.c.id).where(
                admin_accounts_table.c.username == owner_username
            )
        ).scalar_one_or_none()
        if owner_id is not None:
            owner_role_id = connection.execute(
                select(roles_table.c.id).where(roles_table.c.slug == OWNER_ROLE)
            ).scalar_one()
            assigned_owner = connection.execute(
                select(admin_account_roles_table.c.admin_account_id).where(
                    and_(
                        admin_account_roles_table.c.admin_account_id == owner_id,
                        admin_account_roles_table.c.role_id == owner_role_id,
                    )
                )
            ).first()
            if not assigned_owner:
                connection.execute(
                    insert(admin_account_roles_table).values(
                        admin_account_id=owner_id, role_id=owner_role_id
                    )
                )
            owner_super = connection.execute(
                select(admin_account_roles_table.c.admin_account_id).where(
                    and_(
                        admin_account_roles_table.c.admin_account_id == owner_id,
                        admin_account_roles_table.c.role_id == super_role_id,
                    )
                )
            ).first()
            if not owner_super:
                connection.execute(
                    insert(admin_account_roles_table).values(
                        admin_account_id=owner_id, role_id=super_role_id
                    )
                )
        _ensure_blacklist_identity_index(connection)
        existing_codes = set(
            connection.execute(select(languages_table.c.code)).scalars().all()
        )
        for code in codes:
            if code not in existing_codes:
                connection.execute(
                    insert(languages_table).values(code=code, is_default=False)
                )
        default_lang_id = connection.execute(
            select(languages_table.c.id).where(languages_table.c.code == default_code)
        ).scalar_one()
        connection.execute(update(languages_table).values(is_default=False))
        connection.execute(
            update(languages_table)
            .where(languages_table.c.id == default_lang_id)
            .values(is_default=True)
        )
        language_rows = connection.execute(
            select(languages_table.c.id, languages_table.c.code)
        ).mappings().all()
        code_to_language_id = {row["code"]: row["id"] for row in language_rows}
        existing_keys = set(
            connection.execute(
                select(translation_keys_table.c.identifier)
            ).scalars().all()
        )
        missing_keys = [
            {"identifier": identifier}
            for identifier in DEFAULT_TRANSLATION_KEYS
            if identifier not in existing_keys
        ]
        if missing_keys:
            connection.execute(insert(translation_keys_table), missing_keys)
        for code, language_id in code_to_language_id.items():
            identifier = f"language.name.{code}"
            label = LANGUAGE_LABELS.get(code, code.upper())
            key_id = connection.execute(
                select(translation_keys_table.c.id).where(
                    translation_keys_table.c.identifier == identifier
                )
            ).scalar_one_or_none()
            if key_id is None:
                key_id = connection.execute(
                    insert(translation_keys_table)
                    .values(identifier=identifier)
                    .returning(translation_keys_table.c.id)
                ).scalar_one()
            existing_translation = connection.execute(
                select(
                    translations_table.c.id,
                    translations_table.c.value,
                ).where(
                    and_(
                        translations_table.c.language_id == language_id,
                        translations_table.c.key_id == key_id,
                    )
                )
            ).first()
            if existing_translation is None:
                connection.execute(
                    insert(translations_table).values(
                        language_id=language_id,
                        key_id=key_id,
                        value=label,
                    )
                )
            elif not existing_translation.value:
                connection.execute(
                    update(translations_table)
                    .where(translations_table.c.id == existing_translation.id)
                    .values(value=label)
                )
        # Seed translations: use per-language defaults when available, otherwise
        # fall back to default_code texts or humanized identifier.
        default_texts = DEFAULT_TRANSLATIONS.get(default_code, {})
        identifiers = set(DEFAULT_TRANSLATION_KEYS)
        for code, language_id in code_to_language_id.items():
            per_lang_defaults = DEFAULT_TRANSLATIONS.get(code, {})
            for identifier in identifiers:
                key_id = connection.execute(
                    select(translation_keys_table.c.id).where(
                        translation_keys_table.c.identifier == identifier
                    )
                ).scalar_one_or_none()
                if key_id is None:
                    key_id = connection.execute(
                        insert(translation_keys_table)
                        .values(identifier=identifier)
                        .returning(translation_keys_table.c.id)
                    ).scalar_one()
                existing_translation = connection.execute(
                    select(
                        translations_table.c.id,
                        translations_table.c.value,
                    ).where(
                        and_(
                            translations_table.c.language_id == language_id,
                            translations_table.c.key_id == key_id,
                        )
                    )
                ).first()
                # Resolve value with fallbacks
                value = per_lang_defaults.get(identifier) or default_texts.get(identifier) or _humanize_identifier(identifier)
                if existing_translation is None:
                    connection.execute(
                        insert(translations_table).values(
                            language_id=language_id,
                            key_id=key_id,
                            value=value,
                        )
                    )
                else:
                    placeholder = _humanize_identifier(identifier)
                    if (not existing_translation.value) or (existing_translation.value == placeholder):
                        connection.execute(
                            update(translations_table)
                            .where(translations_table.c.id == existing_translation.id)
                            .values(value=value)
                        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_channels_lang_kind ON channels (lang, kind)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_knowledge_documents_topic ON knowledge_documents (topic)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_knowledge_documents_language ON knowledge_documents (language_id)"
        )
        existing_channel_links = {
            (row["kind"], row["lang"]): row["url"]
            for row in connection.execute(
                select(
                    channels_table.c.kind,
                    channels_table.c.lang,
                    channels_table.c.url,
                )
            ).mappings()
        }
        for slot in LINK_SLOTS:
            slug = slot["slug"]
            defaults = DEFAULT_LINKS.get(slug, {})
            for code in code_to_language_id.keys():
                key = (slug, code)
                if key in existing_channel_links:
                    continue
                default_url = (defaults.get(code) or defaults.get(default_code) or "").strip()
                if not default_url:
                    continue
                connection.execute(
                    insert(channels_table).values(
                        kind=slug,
                        lang=code,
                        url=default_url,
                )
                )
        # Ensure notifications table exists
        metadata.create_all(bind=engine)
        # Ensure unban fields exist in users
        connection.exec_driver_sql(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS unban_request_text TEXT"
        )
        connection.exec_driver_sql(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS unban_requested_at TIMESTAMPTZ"
        )
@app.on_event("startup")
def on_startup() -> None:
    _bootstrap_database()
    if settings.jwt_secret_key == "change-me":
        raise RuntimeError(
            "BACKEND_JWT_SECRET_KEY must be set to a non-default secure value."
        )

    global _ai_translator
    _ai_translator = None
    if settings.ai_api_key and settings.ai_model:
        base_url = settings.ai_base_url or "https://api.fireworks.ai/inference/v1"
        _ai_translator = AITranslator(
            base_url=base_url,
            api_key=settings.ai_api_key,
            model=settings.ai_model,
        )

    if settings.auto_repair_translations_on_startup:
        try:
            with get_session() as session:
                updated, examined, per_lang = _repair_translations_internal(
                    session=session,
                    targets_for_icons=["ar", "tr", "en"],
                    use_ru_for_missing=True,
                    ensure_placeholders=True,
                    translator=_ai_translator,
                    prefer_ai=True,
                )
                if updated:
                    logger.info(
                        "Translations auto-repair: updated=%s examined=%s per_language=%s",
                        updated,
                        examined,
                        per_lang,
                    )
        except Exception:
            logger.exception("Translations auto-repair failed")
    else:
        logger.info(
            "Translations auto-repair on startup is disabled (BACKEND_AUTO_REPAIR_TRANSLATIONS_ON_STARTUP=false)."
        )
cors_origins = list(settings.cors_origins or [])
allow_all_origins = "*" in cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all_origins else cors_origins,
    allow_credentials=not allow_all_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
security_scheme = HTTPBearer(auto_error=False)


def _legacy_login_enabled() -> bool:
    return bool(
        settings.enable_legacy_login
        and settings.admin_email
        and settings.admin_password
    )


def _ensure_service_account(
    session: Session,
    *,
    service_name: str,
) -> tuple[int, str, list[str]]:
    configured_username = (settings.service_account_username or "").strip()
    if configured_username:
        if "{service}" in configured_username:
            username = configured_username.format(service=service_name)
        elif service_name == "bot":
            username = configured_username
        else:
            username = f"{configured_username}_{service_name}"
    else:
        username = f"{service_name}_service"
    account = _load_admin_account(session, username)
    if account is None:
        inserted_id = session.execute(
            insert(admin_accounts_table)
            .values(
                username=username,
                password_hash=_hash_password(secrets.token_urlsafe(32)),
                telegram_id=None,
                is_active=True,
            )
            .returning(admin_accounts_table.c.id)
        ).scalar_one()
        account_id = int(inserted_id)
    else:
        account_id = int(account["id"])
        if not account.get("is_active"):
            session.execute(
                update(admin_accounts_table)
                .where(admin_accounts_table.c.id == account_id)
                .values(is_active=True)
            )

    required_roles = {DEFAULT_ADMIN_ROLE, ADMIN_DOCS_ROLE}
    if service_name in {"maintenance", "ops", "translations"}:
        required_roles.add(ADMIN_LANG_ROLE)
    role_rows = session.execute(
        select(roles_table.c.id, roles_table.c.slug).where(
            roles_table.c.slug.in_(required_roles)
        )
    ).mappings().all()
    role_by_slug = {str(row["slug"]): int(row["id"]) for row in role_rows}
    missing_roles = [slug for slug in required_roles if slug not in role_by_slug]
    if missing_roles:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Missing required roles for service account: {', '.join(sorted(missing_roles))}",
        )

    for slug, role_id in role_by_slug.items():
        assigned = session.execute(
            select(admin_account_roles_table.c.admin_account_id).where(
                and_(
                    admin_account_roles_table.c.admin_account_id == account_id,
                    admin_account_roles_table.c.role_id == role_id,
                )
            )
        ).first()
        if not assigned:
            session.execute(
                insert(admin_account_roles_table).values(
                    admin_account_id=account_id,
                    role_id=role_id,
                )
            )

    return account_id, username, _load_admin_roles(session, account_id)


def create_admin_token(username: str, roles: List[str], account_id: int) -> str:
    expires_delta = timedelta(minutes=settings.jwt_access_token_expires_minutes)
    expire = datetime.utcnow() + expires_delta
    payload = {
        "sub": username,
        "exp": expire,
        "roles": roles,
        "aid": account_id,
    }
    return jwt.encode(
        payload,
        key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
def decode_admin_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            key=settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from None
    if "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    return payload
def db_session_dependency() -> Iterable[Session]:
    with get_session() as session:
        yield session
async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
        )
    raw = credentials.credentials
    payload = decode_admin_token(raw)
    roles = payload.get("roles") or []
    if SUPERADMIN_ROLE not in roles and OWNER_ROLE not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions.",
        )
    return payload.get("sub") or "admin"
async def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    session: Session = Depends(db_session_dependency),
    required_roles: Optional[List[str]] = None,
) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
        )
    raw_token = credentials.credentials
    payload = decode_admin_token(raw_token)
    username = payload.get("sub")
    aid = payload.get("aid")
    if not username or aid is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    account = _load_admin_account(session, username)
    if account is None or not account.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled.",
        )
    roles = set(_load_admin_roles(session, account["id"]))
    # Owner bypass
    if OWNER_ROLE in roles:
        return {"id": account["id"], "username": username, "roles": list(roles)}
    # Ensure token roles are still valid
    if SUPERADMIN_ROLE in roles:
        return {"id": account["id"], "username": username, "roles": list(roles)}
    if required_roles:
        if not roles.intersection(required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions.",
            )
    return {"id": account["id"], "username": username, "roles": list(roles)}


def require_roles(*roles: str):
    async def dependency(
        admin=Depends(get_current_admin),
    ):
        roles_set = set(admin.get("roles") or [])
        if OWNER_ROLE in roles_set or SUPERADMIN_ROLE in roles_set:
            return admin
        if not set(roles).intersection(roles_set):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions.",
            )
        return admin

    return dependency


def require_superadmin():
    return require_roles(SUPERADMIN_ROLE)


def require_owner():
    return require_roles(OWNER_ROLE)


def require_owner_or_superadmin():
    return require_roles(OWNER_ROLE, SUPERADMIN_ROLE)


def _admin_topics(admin: dict) -> set[str]:
    roles_set = set(admin.get("roles") or [])
    if OWNER_ROLE in roles_set or SUPERADMIN_ROLE in roles_set:
        return {"nikah", "inheritance", "spouse_search", "courts", "contracts", "execution", "good_deeds"}
    topics: set[str] = set()
    if TZ_NIKAH_ROLE in roles_set:
        topics.add("nikah")
    if TZ_INHERITANCE_ROLE in roles_set:
        topics.add("inheritance")
    if TZ_SPOUSE_SEARCH_ROLE in roles_set:
        topics.add("spouse_search")
    if TZ_COURTS_ROLE in roles_set:
        topics.add("courts")
    if TZ_CONTRACTS_ROLE in roles_set:
        topics.add("contracts")
    if TZ_EXECUTION_ROLE in roles_set:
        topics.add("execution")
    if TZ_GOOD_DEEDS_ROLE in roles_set:
        topics.add("good_deeds")
    return topics


def _require_topic_access(admin: dict, topic: str) -> None:
    topic = (topic or "").strip().lower()
    if topic not in {"nikah", "inheritance", "spouse_search", "courts", "contracts", "execution", "good_deeds"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown topic.")
    topics = _admin_topics(admin)
    if topic not in topics:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions.")
@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
@app.post("/auth/login", response_model=TokenResponse)
async def login(
    payload: LegacyLoginRequest,
    session: Session = Depends(db_session_dependency),
) -> TokenResponse:
    if not _legacy_login_enabled():
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Legacy /auth/login is disabled. Use OTP login.",
        )
    if not (
        payload.email.lower() == str(settings.admin_email).lower()
        and payload.password == settings.admin_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    legacy_username = (settings.admin_username or "admin").strip() or "admin"
    account = _load_admin_account(session, legacy_username)
    if account is None or not account.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled.",
        )
    roles = _load_admin_roles(session, int(account["id"]))
    token = create_admin_token(
        username=legacy_username,
        roles=roles,
        account_id=int(account["id"]),
    )
    return TokenResponse(access_token=token)


@app.post("/auth/service-login", response_model=TokenResponse)
async def service_login(
    payload: ServiceLoginRequest,
    session: Session = Depends(db_session_dependency),
) -> TokenResponse:
    configured_api_key = settings.service_api_key
    if not configured_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service login is not configured.",
        )
    provided_api_key = (payload.api_key or "").strip()
    if not provided_api_key or not secrets.compare_digest(
        provided_api_key, configured_api_key
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service credentials.",
        )

    service_name = (payload.service or "").strip().lower() or "bot"
    if not re.fullmatch(r"[a-z0-9_-]{1,32}", service_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid service name.",
        )
    account_id, username, roles = _ensure_service_account(
        session,
        service_name=service_name,
    )
    token = create_admin_token(
        username=username,
        roles=roles,
        account_id=account_id,
    )
    return TokenResponse(access_token=token)


@app.post("/auth/login-otp", response_model=LoginOtpResponse)
async def login_otp(
    payload: LoginOtpRequest,
    session: Session = Depends(db_session_dependency),
) -> LoginOtpResponse:
    account = _load_admin_account(session, payload.username)
    if account is None or not account.get("is_active"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
    if not _verify_password(payload.password, account.get("password_hash", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
    if not account.get("telegram_id"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Telegram is not linked.")
    ttl = settings.otp_code_ttl_seconds or OTP_DEFAULT_TTL_SECONDS
    attempts = settings.otp_max_attempts or OTP_DEFAULT_ATTEMPTS
    pending_token, otp_code, expires_at = _create_login_challenge(
        session,
        admin_account_id=account["id"],
        ttl_seconds=ttl,
        max_attempts=attempts,
    )
    _send_otp_to_telegram(account["telegram_id"], f"Your admin login code: {otp_code}")
    return LoginOtpResponse(pending_token=pending_token, expires_in=ttl)


@app.post("/auth/verify-otp", response_model=TokenResponse)
async def verify_otp(
    payload: VerifyOtpRequest,
    session: Session = Depends(db_session_dependency),
) -> TokenResponse:
    admin_id = _verify_login_challenge(
        session, pending_token=payload.pending_token, code=payload.code
    )
    account = session.execute(
        select(
            admin_accounts_table.c.id,
            admin_accounts_table.c.username,
            admin_accounts_table.c.is_active,
        ).where(admin_accounts_table.c.id == admin_id)
    ).mappings().one_or_none()
    if account is None or not account["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled.",
        )
    roles = _load_admin_roles(session, admin_id)
    token = create_admin_token(username=account["username"], roles=roles, account_id=admin_id)
    return TokenResponse(access_token=token)


@app.post("/auth/resend-otp", response_model=LoginOtpResponse)
async def resend_otp(
    payload: LoginOtpRequest,
    session: Session = Depends(db_session_dependency),
) -> LoginOtpResponse:
    # Same as login_otp but does not validate existing challenges
    return await login_otp(payload, session=session)
@app.get("/auth/profile", response_model=ProfileResponse)
async def profile(credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme)) -> ProfileResponse:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
        )
    token = credentials.credentials
    payload = decode_admin_token(token)
    username = payload.get("sub") or "admin"
    roles = payload.get("roles") or []
    admin_account_id = payload.get("aid")
    return ProfileResponse(
        username=username,
        roles=roles,
        admin_account_id=admin_account_id,
    )
@app.get(
    "/admin/users",
    response_model=List[UserOut],
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, DEFAULT_ADMIN_ROLE))],
)
async def list_users(session: Session = Depends(db_session_dependency)) -> List[UserOut]:
    stmt = (
        select(
            users_table.c.id,
            users_table.c.user_id,
            users_table.c.created_at,
            users_table.c.role,
            users_table.c.is_alive,
            users_table.c.banned,
            users_table.c.full_name,
            users_table.c.email,
            users_table.c.phone_number,
            users_table.c.email_verified,
            users_table.c.phone_verified,
            users_table.c.unban_request_text,
            users_table.c.unban_requested_at,
            languages_table.c.code.label("language_code"),
        )
        .select_from(
            users_table.join(
                languages_table,
                users_table.c.language_id == languages_table.c.id,
                isouter=True,
            )
        )
        .order_by(
            users_table.c.unban_requested_at.desc().nullslast(),
            users_table.c.created_at.desc().nullslast(),
        )
    )
    rows = session.execute(stmt).mappings().all()
    return [UserOut(**row) for row in rows]
@app.get(
    "/admin/languages",
    response_model=List[LanguageOut],
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_LANG_ROLE))],
)
async def list_languages(
    session: Session = Depends(db_session_dependency),
) -> List[LanguageOut]:
    stmt = select(
        languages_table.c.id,
        languages_table.c.code,
        languages_table.c.is_default,
    ).order_by(languages_table.c.code)
    rows = session.execute(stmt).mappings().all()
    return [LanguageOut(**row) for row in rows]
def _get_language_id(session: Session, code: Optional[str]) -> Optional[int]:
    if not code:
        return None
    language_code = _normalize_code(code)
    return session.execute(
        select(languages_table.c.id).where(languages_table.c.code == language_code)
    ).scalar_one_or_none()

def _fetch_user_out(session: Session, telegram_user_id: int) -> Optional[UserOut]:
    stmt = (
        select(
            users_table.c.id,
            users_table.c.user_id,
            users_table.c.created_at,
            users_table.c.role,
            users_table.c.is_alive,
            users_table.c.banned,
            users_table.c.full_name,
            users_table.c.email,
            users_table.c.phone_number,
            users_table.c.email_verified,
            users_table.c.phone_verified,
            users_table.c.unban_request_text,
            users_table.c.unban_requested_at,
            languages_table.c.code.label("language_code"),
        )
        .select_from(
            users_table.join(
                languages_table,
                users_table.c.language_id == languages_table.c.id,
                isouter=True,
            )
        )
        .where(users_table.c.user_id == telegram_user_id)
    )
    row = session.execute(stmt).mappings().one_or_none()
    return UserOut(**row) if row else None

@app.post(
    "/admin/users",
    response_model=UserOut,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, DEFAULT_ADMIN_ROLE))],
)
async def create_user(
    payload: CreateUserIn,
    session: Session = Depends(db_session_dependency),
) -> UserOut:
    lang_id = _get_language_id(session, payload.language_code)
    exists = session.execute(
        select(users_table.c.id).where(users_table.c.user_id == payload.telegram_user_id)
    ).scalar_one_or_none()

    values_common = dict(
        language_id=lang_id,
        role=(payload.role or None),
        is_alive=True,
        banned=False,
        full_name=(payload.full_name or None),
        email=(str(payload.email) if payload.email else None),
        phone_number=(payload.phone_number or None),
    )
    if exists is None:
        session.execute(
            insert(users_table).values(
                user_id=payload.telegram_user_id,
                created_at=datetime.now(timezone.utc),
                **values_common,
            )
        )
    else:
        session.execute(
            update(users_table)
            .where(users_table.c.user_id == payload.telegram_user_id)
            .values(**values_common)
        )
    out = _fetch_user_out(session, payload.telegram_user_id)
    assert out is not None
    return out

@app.delete(
    "/admin/users/{telegram_user_id}",
    response_model=UserOut,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE))],
)
async def delete_user(
    telegram_user_id: int,
    session: Session = Depends(db_session_dependency),
) -> UserOut:
    # Protect admins from deletion
    existing = _fetch_user_out(session, telegram_user_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if (existing.role or "").lower() in {"admin", "owner"} or telegram_user_id in (settings.admin_ids or []):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete administrator user.")
    session.execute(
        delete(users_table).where(users_table.c.user_id == telegram_user_id)
    )
    return existing

@app.get(
    "/admin/roles",
    response_model=List[RoleOut],
    dependencies=[Depends(require_owner_or_superadmin())],
)
async def list_roles(
    session: Session = Depends(db_session_dependency),
) -> List[RoleOut]:
    rows = session.execute(
        select(
            roles_table.c.id,
            roles_table.c.slug,
            roles_table.c.title,
            roles_table.c.description,
        ).order_by(roles_table.c.slug)
    ).mappings().all()
    return [RoleOut(**row) for row in rows]


@app.get(
    "/admin/admin-accounts",
    response_model=List[AdminAccountOut],
    dependencies=[Depends(require_owner_or_superadmin())],
)
async def list_admin_accounts(
    session: Session = Depends(db_session_dependency),
) -> List[AdminAccountOut]:
    rows = session.execute(
        select(
            admin_accounts_table.c.id,
            admin_accounts_table.c.username,
            admin_accounts_table.c.telegram_id,
            admin_accounts_table.c.is_active,
        ).order_by(admin_accounts_table.c.username)
    ).mappings().all()
    result: List[AdminAccountOut] = []
    for row in rows:
        roles = _load_admin_roles(session, row["id"])
        result.append(
            AdminAccountOut(
                id=row["id"],
                username=row["username"],
                telegram_id=row["telegram_id"],
                is_active=row["is_active"],
                roles=roles,
            )
        )
    return result


@app.post(
    "/admin/admin-accounts",
    response_model=AdminAccountOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_admin_account(
    username: str = Body(...),
    password: str | None = Body(None),
    telegram_id: Optional[int] = Body(None),
    roles: Optional[List[str]] = Body(None),
    session: Session = Depends(db_session_dependency),
    current_admin: dict = Depends(require_owner_or_superadmin()),
) -> AdminAccountOut:
    try:
        payload_model = AdminAccountCreate(
            username=username,
            password=password or "",
            telegram_id=telegram_id,
            roles=roles,
        )
    except Exception as exc:
        from pydantic import ValidationError

        if isinstance(exc, ValidationError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.errors(),
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    username = payload_model.username.strip()
    if not username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username cannot be empty.")
    existing = session.execute(
        select(admin_accounts_table.c.id).where(admin_accounts_table.c.username == username)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists.")
    hashed = _hash_password(payload_model.password)
    inserted_id = session.execute(
        insert(admin_accounts_table)
        .values(
            username=username,
            password_hash=hashed,
            telegram_id=payload_model.telegram_id,
            is_active=True,
        )
        .returning(admin_accounts_table.c.id)
    ).scalar_one()
    # Assign roles if provided
    _ensure_role_assignment(
        session=session,
        admin_account_id=inserted_id,
        role_slugs=payload_model.roles or [],
        current_roles=set(current_admin.get("roles") or []),
    )
    roles = _load_admin_roles(session, inserted_id)
    return AdminAccountOut(
        id=inserted_id,
        username=username,
        telegram_id=payload_model.telegram_id,
        is_active=True,
        roles=roles,
    )


@app.patch(
    "/admin/admin-accounts/{account_id}",
    response_model=AdminAccountOut,
)
async def update_admin_account(
    account_id: int,
    payload: AdminAccountUpdate,
    session: Session = Depends(db_session_dependency),
    current_admin: dict = Depends(require_owner_or_superadmin()),
) -> AdminAccountOut:
    account = session.execute(
        select(
            admin_accounts_table.c.id,
            admin_accounts_table.c.username,
            admin_accounts_table.c.telegram_id,
            admin_accounts_table.c.is_active,
        ).where(admin_accounts_table.c.id == account_id)
    ).mappings().one_or_none()
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin account not found.")
    updated_fields: dict[str, Any] = {}
    if payload.password is not None:
        normalized = payload.password.strip()
        if not normalized:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password cannot be empty.")
        updated_fields["password_hash"] = _hash_password(normalized)
    if updated_fields:
        session.execute(
            update(admin_accounts_table)
            .where(admin_accounts_table.c.id == account_id)
            .values(**updated_fields)
        )
    if payload.roles is not None:
        _set_admin_roles(
            session=session,
            admin_account_id=account_id,
            role_slugs=payload.roles,
            current_roles=set(current_admin.get("roles") or []),
        )
    roles = _load_admin_roles(session, account_id)
    return AdminAccountOut(
        id=account["id"],
        username=account["username"],
        telegram_id=account["telegram_id"],
        is_active=account["is_active"],
        roles=roles,
    )


@app.delete(
    "/admin/admin-accounts/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_admin_account(
    account_id: int,
    session: Session = Depends(db_session_dependency),
    current_admin: dict = Depends(require_owner_or_superadmin()),
) -> None:
    # owner cannot be deleted unless caller is owner
    roles = set(_load_admin_roles(session, account_id))
    if OWNER_ROLE in roles and OWNER_ROLE not in set(current_admin.get("roles") or []):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner can delete owner.")
    session.execute(delete(admin_account_roles_table).where(admin_account_roles_table.c.admin_account_id == account_id))
    session.execute(delete(login_challenges_table).where(login_challenges_table.c.admin_account_id == account_id))
    deleted = session.execute(delete(admin_accounts_table).where(admin_accounts_table.c.id == account_id))
    if deleted.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin account not found.")


@app.post(
    "/admin/roles",
    response_model=RoleOut,
    dependencies=[Depends(require_owner_or_superadmin())],
)
async def create_role(
    payload: RoleCreate,
    session: Session = Depends(db_session_dependency),
) -> RoleOut:
    existing = session.execute(
        select(roles_table.c.id).where(roles_table.c.slug == payload.slug)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role already exists.")
    row = session.execute(
        insert(roles_table)
        .values(slug=payload.slug, title=payload.title, description=payload.description)
        .returning(
            roles_table.c.id,
            roles_table.c.slug,
            roles_table.c.title,
            roles_table.c.description,
        )
    ).mappings().one()
    return RoleOut(**row)


@app.post(
    "/admin/roles/{role_id}/assign",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def assign_role(
    role_id: int,
    payload: AssignRoleRequest = Depends(_parse_assign_role_request),
    session: Session = Depends(db_session_dependency),
    current_admin: dict = Depends(require_owner_or_superadmin()),
) -> None:
    exists_role = session.execute(
        select(roles_table.c.id).where(roles_table.c.id == role_id)
    ).scalar_one_or_none()
    if exists_role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found.")
    # Only owner can assign owner/superadmin
    role_slug = session.execute(
        select(roles_table.c.slug).where(roles_table.c.id == role_id)
    ).scalar_one()
    roles = set(current_admin.get("roles") or [])
    if role_slug in {OWNER_ROLE, SUPERADMIN_ROLE} and OWNER_ROLE not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner can assign this role.")
    exists_admin = session.execute(
        select(admin_accounts_table.c.id).where(admin_accounts_table.c.id == payload.admin_account_id)
    ).scalar_one_or_none()
    if exists_admin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin account not found.")
    exists_pair = session.execute(
        select(admin_account_roles_table.c.admin_account_id).where(
            and_(
                admin_account_roles_table.c.admin_account_id == payload.admin_account_id,
                admin_account_roles_table.c.role_id == role_id,
            )
        )
    ).first()
    if not exists_pair:
        session.execute(
            insert(admin_account_roles_table).values(
                admin_account_id=payload.admin_account_id, role_id=role_id
            )
        )


@app.post(
    "/admin/roles/{role_id}/revoke",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_role(
    role_id: int,
    payload: AssignRoleRequest = Depends(_parse_assign_role_request),
    session: Session = Depends(db_session_dependency),
    current_admin: dict = Depends(require_owner_or_superadmin()),
) -> None:
    role_slug = session.execute(
        select(roles_table.c.slug).where(roles_table.c.id == role_id)
    ).scalar_one_or_none()
    roles = set(current_admin.get("roles") or [])
    if role_slug in {OWNER_ROLE, SUPERADMIN_ROLE} and OWNER_ROLE not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner can revoke this role.")
    session.execute(
        delete(admin_account_roles_table).where(
            and_(
                admin_account_roles_table.c.admin_account_id == payload.admin_account_id,
                admin_account_roles_table.c.role_id == role_id,
            )
        )
    )


def _decode_payload(value: Optional[str]) -> Optional[dict]:
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return {"raw": value}


def _encode_payload(value: Optional[dict]) -> Optional[str]:
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return json.dumps({"raw": str(value)}, ensure_ascii=False)


def _decode_json_list(value: Any) -> Optional[list]:
    if value is None:
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return None
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return [parsed]
        return None
    return None


def _decode_json_object(value: Any) -> Optional[dict]:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                return item
        return None
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return None
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict):
                    return item
    return None


def _append_history(existing: Any, event: dict) -> str:
    items = _decode_json_list(existing) or []
    items.append(event)
    return json.dumps(items, ensure_ascii=False)


def _sync_work_item_status_for_court_case(
    session: Session,
    *,
    case_id: int,
    case_status: str,
    actor_admin_id: Optional[int],
) -> None:
    status_map = {
        "open": "new",
        "in_progress": "in_progress",
        "closed": "done",
        "cancelled": "canceled",
    }
    normalized = (case_status or "").strip().lower()
    mapped = status_map.get(normalized)
    if not mapped:
        return
    rows = session.execute(
        select(
            work_items_table.c.id,
            work_items_table.c.status,
            work_items_table.c.payload,
        ).where(work_items_table.c.topic == "courts")
    ).mappings().all()
    case_id_str = str(case_id)
    now = datetime.now(timezone.utc)
    for row in rows:
        payload = _decode_payload(row.get("payload")) or {}
        payload_case = payload.get("case_id")
        if payload_case is None:
            continue
        if str(payload_case) != case_id_str:
            continue
        current = str(row.get("status") or "").lower()
        if current == mapped:
            continue
        values: dict[str, Any] = {"status": mapped, "updated_at": now}
        if mapped in {"done", "canceled"}:
            values["done_at"] = now
        session.execute(
            update(work_items_table)
            .where(work_items_table.c.id == row["id"])
            .values(**values)
        )
        session.execute(
            insert(work_item_events_table).values(
                work_item_id=row["id"],
                actor_admin_id=actor_admin_id,
                event_type="status",
                message=f"Status changed to {mapped} (synced from court case)",
                payload=_encode_payload(
                    {"status": mapped, "source": "court_case", "case_id": case_id}
                ),
            )
        )


def _telegram_file_endpoint(token: str, file_id: str) -> str:
    return f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}"


def _telegram_download_url(token: str, file_path: str) -> str:
    return f"https://api.telegram.org/file/bot{token}/{file_path}"


def _download_telegram_file(file_id: str) -> tuple[bytes, str]:
    token = settings.otp_bot_token
    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Telegram token not configured.")
    try:
        response = requests.get(_telegram_file_endpoint(token, file_id), timeout=15)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Telegram error: {exc}") from exc
    file_path = payload.get("result", {}).get("file_path")
    if not file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Telegram file not found.")
    try:
        download = requests.get(_telegram_download_url(token, file_path), timeout=30)
        download.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Telegram download failed: {exc}") from exc
    filename = file_path.split("/")[-1]
    return download.content, filename


@app.get(
    "/admin/work-items",
    response_model=List[WorkItemOut],
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_WORK_ITEMS_VIEW_ROLE))],
)
async def list_work_items(
    topic: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="Comma-separated statuses"),
    mine: bool = Query(False),
    unassigned: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(db_session_dependency),
    admin: dict = Depends(get_current_admin),
) -> List[WorkItemOut]:
    allowed_topics = _admin_topics(admin)
    if not allowed_topics:
        return []

    stmt = select(
        work_items_table.c.id,
        work_items_table.c.topic,
        work_items_table.c.kind,
        work_items_table.c.status,
        work_items_table.c.priority,
        work_items_table.c.created_by_user_id,
        work_items_table.c.target_user_id,
        work_items_table.c.assignee_admin_id,
        work_items_table.c.payload,
        work_items_table.c.created_at,
        work_items_table.c.updated_at,
        work_items_table.c.done_at,
    )

    filters = []
    if topic:
        normalized = topic.strip().lower()
        if normalized not in allowed_topics:
            return []
        filters.append(work_items_table.c.topic == normalized)
    else:
        filters.append(work_items_table.c.topic.in_(sorted(allowed_topics)))

    if status:
        statuses = [s.strip().lower() for s in status.split(",") if s.strip()]
        if statuses:
            filters.append(work_items_table.c.status.in_(statuses))

    if mine:
        filters.append(work_items_table.c.assignee_admin_id == int(admin["id"]))
    if unassigned:
        filters.append(work_items_table.c.assignee_admin_id.is_(None))

    if filters:
        stmt = stmt.where(and_(*filters))
    stmt = stmt.order_by(work_items_table.c.updated_at.desc()).limit(limit)

    rows = session.execute(stmt).mappings().all()
    return [
        WorkItemOut(
            id=row["id"],
            topic=row["topic"],
            kind=row["kind"],
            status=row["status"],
            priority=row["priority"],
            created_by_user_id=row["created_by_user_id"],
            target_user_id=row["target_user_id"],
            assignee_admin_id=row["assignee_admin_id"],
            payload=_decode_payload(row.get("payload")),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            done_at=row["done_at"],
        )
        for row in rows
    ]


@app.get(
    "/admin/work-items/{work_item_id}",
    response_model=WorkItemOut,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_WORK_ITEMS_VIEW_ROLE))],
)
async def get_work_item(
    work_item_id: int,
    session: Session = Depends(db_session_dependency),
    admin: dict = Depends(get_current_admin),
) -> WorkItemOut:
    row = session.execute(
        select(
            work_items_table.c.id,
            work_items_table.c.topic,
            work_items_table.c.kind,
            work_items_table.c.status,
            work_items_table.c.priority,
            work_items_table.c.created_by_user_id,
            work_items_table.c.target_user_id,
            work_items_table.c.assignee_admin_id,
            work_items_table.c.payload,
            work_items_table.c.created_at,
            work_items_table.c.updated_at,
            work_items_table.c.done_at,
        ).where(work_items_table.c.id == work_item_id)
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work item not found.")
    _require_topic_access(admin, row["topic"])
    return WorkItemOut(
        id=row["id"],
        topic=row["topic"],
        kind=row["kind"],
        status=row["status"],
        priority=row["priority"],
        created_by_user_id=row["created_by_user_id"],
        target_user_id=row["target_user_id"],
        assignee_admin_id=row["assignee_admin_id"],
        payload=_decode_payload(row.get("payload")),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        done_at=row["done_at"],
    )


@app.get(
    "/admin/work-items/{work_item_id}/events",
    response_model=List[WorkItemEventOut],
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_WORK_ITEMS_VIEW_ROLE))],
)
async def list_work_item_events(
    work_item_id: int,
    session: Session = Depends(db_session_dependency),
    admin: dict = Depends(get_current_admin),
) -> List[WorkItemEventOut]:
    item = session.execute(
        select(work_items_table.c.topic).where(work_items_table.c.id == work_item_id)
    ).mappings().one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work item not found.")
    _require_topic_access(admin, item["topic"])
    rows = session.execute(
        select(
            work_item_events_table.c.id,
            work_item_events_table.c.work_item_id,
            work_item_events_table.c.actor_admin_id,
            work_item_events_table.c.event_type,
            work_item_events_table.c.message,
            work_item_events_table.c.payload,
            work_item_events_table.c.created_at,
        )
        .where(work_item_events_table.c.work_item_id == work_item_id)
        .order_by(work_item_events_table.c.created_at.asc())
    ).mappings().all()
    return [
        WorkItemEventOut(
            id=row["id"],
            work_item_id=row["work_item_id"],
            actor_admin_id=row["actor_admin_id"],
            event_type=row["event_type"],
            message=row["message"],
            payload=_decode_payload(row.get("payload")),
            created_at=row["created_at"],
        )
        for row in rows
    ]


@app.post(
    "/admin/work-items/{work_item_id}/assign",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_WORK_ITEMS_MANAGE_ROLE))],
)
async def assign_work_item_to_self(
    work_item_id: int,
    session: Session = Depends(db_session_dependency),
    admin: dict = Depends(get_current_admin),
) -> None:
    row = session.execute(
        select(work_items_table.c.topic).where(work_items_table.c.id == work_item_id)
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work item not found.")
    _require_topic_access(admin, row["topic"])
    session.execute(
        update(work_items_table)
        .where(work_items_table.c.id == work_item_id)
        .values(assignee_admin_id=int(admin["id"]), status="in_progress")
    )
    session.execute(
        insert(work_item_events_table).values(
            work_item_id=work_item_id,
            actor_admin_id=int(admin["id"]),
            event_type="assign",
            message=f"Assigned to {admin.get('username')}",
            payload=_encode_payload({"assignee_admin_id": int(admin["id"])}),
        )
    )


@app.post(
    "/admin/work-items/{work_item_id}/status",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_WORK_ITEMS_MANAGE_ROLE))],
)
async def update_work_item_status(
    work_item_id: int,
    payload: WorkItemStatusUpdate = Depends(_parse_work_item_status_request),
    session: Session = Depends(db_session_dependency),
    admin: dict = Depends(get_current_admin),
) -> None:
    row = session.execute(
        select(
            work_items_table.c.topic,
            work_items_table.c.payload,
        ).where(work_items_table.c.id == work_item_id)
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work item not found.")
    _require_topic_access(admin, row["topic"])
    normalized = payload.status.strip().lower()
    values: dict[str, Any] = {"status": normalized}
    if normalized in {"done", "canceled"}:
        values["done_at"] = datetime.now(timezone.utc)
    session.execute(update(work_items_table).where(work_items_table.c.id == work_item_id).values(**values))
    session.execute(
        insert(work_item_events_table).values(
            work_item_id=work_item_id,
            actor_admin_id=int(admin["id"]),
            event_type="status",
            message=f"Status changed to {normalized}",
            payload=_encode_payload({"status": normalized}),
        )
    )
    if row.get("topic") == "courts":
        payload_data = _decode_payload(row.get("payload")) or {}
        case_id = payload_data.get("case_id")
        status_map = {
            "new": "open",
            "assigned": "in_progress",
            "in_progress": "in_progress",
            "waiting_user": "in_progress",
            "waiting_scholar": "in_progress",
            "done": "closed",
            "canceled": "cancelled",
        }
        mapped = status_map.get(normalized)
        if case_id and mapped:
            session.execute(
                update(court_cases_table)
                .where(court_cases_table.c.id == int(case_id))
                .values(status=mapped, updated_at=datetime.now(timezone.utc))
            )


@app.post(
    "/admin/work-items/{work_item_id}/comment",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_WORK_ITEMS_MANAGE_ROLE))],
)
async def add_work_item_comment(
    work_item_id: int,
    payload: WorkItemCommentCreate,
    session: Session = Depends(db_session_dependency),
    admin: dict = Depends(get_current_admin),
) -> None:
    row = session.execute(
        select(work_items_table.c.topic).where(work_items_table.c.id == work_item_id)
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work item not found.")
    _require_topic_access(admin, row["topic"])
    session.execute(
        insert(work_item_events_table).values(
            work_item_id=work_item_id,
            actor_admin_id=int(admin["id"]),
            event_type="comment",
            message=payload.message.strip(),
        )
    )


@app.post(
    "/admin/work-items/{work_item_id}/notify-user",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_WORK_ITEMS_MANAGE_ROLE))],
)
async def notify_user_from_work_item(
    work_item_id: int,
    payload: WorkItemNotifyUser,
    session: Session = Depends(db_session_dependency),
    admin: dict = Depends(get_current_admin),
) -> None:
    row = session.execute(
        select(work_items_table.c.topic, work_items_table.c.target_user_id).where(work_items_table.c.id == work_item_id)
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work item not found.")
    _require_topic_access(admin, row["topic"])
    target_user_id = row.get("target_user_id")
    if not target_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Work item has no target user.")
    session.execute(
        insert(notifications_table).values(
            user_id=int(target_user_id),
            kind="admin_message",
            payload=_encode_payload({"text": payload.text.strip(), "work_item_id": work_item_id}),
        )
    )
    session.execute(
        insert(work_item_events_table).values(
            work_item_id=work_item_id,
            actor_admin_id=int(admin["id"]),
            event_type="notify_user",
            message="Message sent to user via notifications",
            payload=_encode_payload({"target_user_id": int(target_user_id)}),
        )
    )


def _serialize_court_case(row: dict) -> CourtCaseOut:
    amount_value = row.get("amount")
    amount = float(amount_value) if amount_value is not None else None
    return CourtCaseOut(
        id=int(row.get("id") or 0),
        case_number=row.get("case_number"),
        user_id=int(row.get("user_id") or 0),
        category=str(row.get("category") or ""),
        plaintiff=str(row.get("plaintiff") or ""),
        defendant=str(row.get("defendant") or ""),
        claim=str(row.get("claim") or ""),
        amount=amount,
        evidence=_decode_json_list(row.get("evidence")),
        status=str(row.get("status") or ""),
        sent_to_scholar=bool(row.get("sent_to_scholar")),
        responsible_admin_id=row.get("responsible_admin_id"),
        responsible_admin_username=row.get("responsible_admin_username"),
        scholar_id=row.get("scholar_id"),
        scholar_name=row.get("scholar_name"),
        scholar_contact=row.get("scholar_contact"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _serialize_contract(row: dict) -> ContractOut:
    return ContractOut(
        id=int(row.get("id") or 0),
        user_id=int(row.get("user_id")) if row.get("user_id") is not None else None,
        contract_type=str(row.get("type") or ""),
        template_topic=row.get("template_topic"),
        language=row.get("language"),
        data=_decode_json_object(row.get("data")),
        rendered_text=row.get("rendered_text"),
        status=row.get("status"),
        invite_code=row.get("invite_code"),
        responsible_admin_id=row.get("responsible_admin_id"),
        responsible_admin_username=row.get("responsible_admin_username"),
        scholar_id=row.get("scholar_id"),
        scholar_name=row.get("scholar_name"),
        scholar_contact=row.get("scholar_contact"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _court_cases_select():
    return select(
        court_cases_table,
        admin_accounts_table.c.username.label("responsible_admin_username"),
    ).select_from(
        court_cases_table.outerjoin(
            admin_accounts_table,
            court_cases_table.c.responsible_admin_id == admin_accounts_table.c.id,
        )
    )


def _contracts_select():
    return select(
        contracts_table,
        admin_accounts_table.c.username.label("responsible_admin_username"),
    ).select_from(
        contracts_table.outerjoin(
            admin_accounts_table,
            contracts_table.c.responsible_admin_id == admin_accounts_table.c.id,
        )
    )


@app.get(
    "/admin/court-cases",
    response_model=List[CourtCaseOut],
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_WORK_ITEMS_VIEW_ROLE))],
)
async def admin_list_court_cases(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    admin: dict = Depends(get_current_admin),
    session: Session = Depends(db_session_dependency),
) -> List[CourtCaseOut]:
    _require_topic_access(admin, "courts")
    stmt = _court_cases_select().order_by(court_cases_table.c.created_at.desc()).limit(limit)
    if status:
        statuses = [s.strip().lower() for s in status.split(",") if s.strip()]
        if statuses:
            stmt = stmt.where(func.lower(court_cases_table.c.status).in_(statuses))
    rows = session.execute(stmt).mappings().all()
    return [_serialize_court_case(row) for row in rows]


@app.get(
    "/admin/court-cases/{case_id}",
    response_model=CourtCaseOut,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_WORK_ITEMS_VIEW_ROLE))],
)
async def admin_get_court_case(
    case_id: int,
    admin: dict = Depends(get_current_admin),
    session: Session = Depends(db_session_dependency),
) -> CourtCaseOut:
    _require_topic_access(admin, "courts")
    row = (
        session.execute(_court_cases_select().where(court_cases_table.c.id == case_id))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Court case not found.")
    return _serialize_court_case(row)


@app.patch(
    "/admin/court-cases/{case_id}",
    response_model=CourtCaseOut,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_WORK_ITEMS_MANAGE_ROLE))],
)
async def admin_update_court_case(
    case_id: int,
    payload: CourtCaseUpdate = Depends(_parse_court_case_update_request),
    admin: dict = Depends(get_current_admin),
    session: Session = Depends(db_session_dependency),
) -> CourtCaseOut:
    _require_topic_access(admin, "courts")
    updates: Dict[str, object] = {}
    next_status: Optional[str] = None
    if payload.status:
        next_status = payload.status.strip()
        updates["status"] = next_status
    if payload.scholar_id is not None:
        updates["scholar_id"] = payload.scholar_id.strip() or None
    if payload.scholar_name is not None:
        updates["scholar_name"] = payload.scholar_name.strip() or None
    if payload.scholar_contact is not None:
        updates["scholar_contact"] = payload.scholar_contact.strip() or None
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No updates provided.")
    updates["updated_at"] = datetime.now(timezone.utc)
    session.execute(
        update(court_cases_table)
        .where(court_cases_table.c.id == case_id)
        .values(**updates)
    )
    row = (
        session.execute(select(court_cases_table).where(court_cases_table.c.id == case_id))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Court case not found.")
    if next_status:
        _sync_work_item_status_for_court_case(
            session,
            case_id=case_id,
            case_status=next_status,
            actor_admin_id=int(admin.get("id") or 0) if admin else None,
        )
    return _serialize_court_case(row)


@app.post(
    "/admin/court-cases/{case_id}/assign",
    response_model=CourtCaseOut,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_WORK_ITEMS_MANAGE_ROLE))],
)
async def admin_assign_court_case(
    case_id: int,
    payload: CourtCaseAssign = Depends(_parse_court_case_assign_request),
    admin: dict = Depends(get_current_admin),
    session: Session = Depends(db_session_dependency),
) -> CourtCaseOut:
    _require_topic_access(admin, "courts")
    roles_set = set(admin.get("roles") or [])
    can_assign_any = OWNER_ROLE in roles_set or SUPERADMIN_ROLE in roles_set
    assignee_id = payload.assignee_admin_id or admin.get("id")
    if not assignee_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assignee is required.")
    if not can_assign_any and int(assignee_id) != int(admin.get("id") or 0):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions.")
    assignee = (
        session.execute(
            select(
                admin_accounts_table.c.id,
                admin_accounts_table.c.username,
                admin_accounts_table.c.telegram_id,
            ).where(admin_accounts_table.c.id == int(assignee_id))
        )
        .mappings()
        .one_or_none()
    )
    if assignee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin account not found.")
    session.execute(
        update(court_cases_table)
        .where(court_cases_table.c.id == case_id)
        .values(
            responsible_admin_id=int(assignee_id),
            updated_at=datetime.now(timezone.utc),
        )
    )
    case_row = (
        session.execute(_court_cases_select().where(court_cases_table.c.id == case_id))
        .mappings()
        .one_or_none()
    )
    if case_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Court case not found.")
    case_number = case_row.get("case_number") or case_row.get("id")
    telegram_id = assignee.get("telegram_id")
    if telegram_id:
        text = f"Вас назначили ответственным за дело № {case_number}."
        session.execute(
            insert(notifications_table).values(
                user_id=int(telegram_id),
                kind="admin_message",
                payload=_encode_payload({"text": text, "case_id": case_id}),
            )
        )
    return _serialize_court_case(case_row)


@app.get(
    "/admin/court-cases/{case_id}/evidence/{index}/download",
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_WORK_ITEMS_VIEW_ROLE))],
)
async def admin_download_court_evidence(
    case_id: int,
    index: int,
    admin: dict = Depends(get_current_admin),
    session: Session = Depends(db_session_dependency),
) -> StreamingResponse:
    _require_topic_access(admin, "courts")
    row = (
        session.execute(_court_cases_select().where(court_cases_table.c.id == case_id))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Court case not found.")
    evidence = _decode_json_list(row.get("evidence")) or []
    if index < 0 or index >= len(evidence):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found.")
    item = evidence[index] or {}
    file_id = item.get("file_id")
    if not file_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Evidence has no file.")
    content, filename = _download_telegram_file(str(file_id))
    media_type = item.get("mime_type") or "application/octet-stream"
    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get(
    "/admin/contracts",
    response_model=List[ContractOut],
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_WORK_ITEMS_VIEW_ROLE))],
)
async def admin_list_contracts(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    admin: dict = Depends(get_current_admin),
    session: Session = Depends(db_session_dependency),
) -> List[ContractOut]:
    _require_topic_access(admin, "contracts")
    stmt = _contracts_select().order_by(contracts_table.c.created_at.desc()).limit(limit)
    if status:
        statuses = [s.strip().lower() for s in status.split(",") if s.strip()]
        if statuses:
            stmt = stmt.where(func.lower(contracts_table.c.status).in_(statuses))
    rows = session.execute(stmt).mappings().all()
    return [_serialize_contract(row) for row in rows]


@app.get(
    "/admin/contracts/{contract_id}",
    response_model=ContractOut,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_WORK_ITEMS_VIEW_ROLE))],
)
async def admin_get_contract(
    contract_id: int,
    admin: dict = Depends(get_current_admin),
    session: Session = Depends(db_session_dependency),
) -> ContractOut:
    _require_topic_access(admin, "contracts")
    row = (
        session.execute(_contracts_select().where(contracts_table.c.id == contract_id))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found.")
    return _serialize_contract(row)


@app.patch(
    "/admin/contracts/{contract_id}",
    response_model=ContractOut,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_WORK_ITEMS_MANAGE_ROLE))],
)
async def admin_update_contract(
    contract_id: int,
    payload: ContractUpdate = Depends(_parse_contract_update_request),
    admin: dict = Depends(get_current_admin),
    session: Session = Depends(db_session_dependency),
) -> ContractOut:
    _require_topic_access(admin, "contracts")
    updates: Dict[str, object] = {}
    if payload.status:
        updates["status"] = payload.status.strip()
    if payload.scholar_id is not None:
        updates["scholar_id"] = payload.scholar_id.strip() or None
    if payload.scholar_name is not None:
        updates["scholar_name"] = payload.scholar_name.strip() or None
    if payload.scholar_contact is not None:
        updates["scholar_contact"] = payload.scholar_contact.strip() or None
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No updates provided.")
    updates["updated_at"] = datetime.now(timezone.utc)
    session.execute(
        update(contracts_table)
        .where(contracts_table.c.id == contract_id)
        .values(**updates)
    )
    row = (
        session.execute(select(contracts_table).where(contracts_table.c.id == contract_id))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found.")
    return _serialize_contract(row)


@app.post(
    "/admin/contracts/{contract_id}/assign",
    response_model=ContractOut,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_WORK_ITEMS_MANAGE_ROLE))],
)
async def admin_assign_contract(
    contract_id: int,
    payload: ContractAssign = Depends(_parse_contract_assign_request),
    admin: dict = Depends(get_current_admin),
    session: Session = Depends(db_session_dependency),
) -> ContractOut:
    _require_topic_access(admin, "contracts")
    roles_set = set(admin.get("roles") or [])
    can_assign_any = OWNER_ROLE in roles_set or SUPERADMIN_ROLE in roles_set
    assignee_id = payload.assignee_admin_id or admin.get("id")
    if not assignee_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assignee is required.")
    if not can_assign_any and int(assignee_id) != int(admin.get("id") or 0):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions.")
    assignee = (
        session.execute(
            select(
                admin_accounts_table.c.id,
                admin_accounts_table.c.username,
                admin_accounts_table.c.telegram_id,
            ).where(admin_accounts_table.c.id == int(assignee_id))
        )
        .mappings()
        .one_or_none()
    )
    if assignee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin account not found.")
    session.execute(
        update(contracts_table)
        .where(contracts_table.c.id == contract_id)
        .values(
            responsible_admin_id=int(assignee_id),
            updated_at=datetime.now(timezone.utc),
        )
    )
    contract_row = (
        session.execute(_contracts_select().where(contracts_table.c.id == contract_id))
        .mappings()
        .one_or_none()
    )
    if contract_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found.")
    telegram_id = assignee.get("telegram_id")
    if telegram_id:
        text = f"Вас назначили ответственным за договор № {contract_row.get('id')}."
        session.execute(
            insert(notifications_table).values(
                user_id=int(telegram_id),
                kind="admin_message",
                payload=_encode_payload({"text": text, "contract_id": contract_id}),
            )
        )
    return _serialize_contract(contract_row)


@app.delete(
    "/admin/contracts/{contract_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_WORK_ITEMS_MANAGE_ROLE))],
)
async def admin_delete_contract(
    contract_id: int,
    admin: dict = Depends(get_current_admin),
    session: Session = Depends(db_session_dependency),
) -> None:
    _require_topic_access(admin, "contracts")
    exists = session.execute(
        select(contracts_table.c.id).where(contracts_table.c.id == contract_id)
    ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found.")
    session.execute(delete(contracts_table).where(contracts_table.c.id == contract_id))


def _good_deeds_select():
    return select(
        good_deeds_table,
        users_table.c.full_name.label("user_full_name"),
        users_table.c.phone_number.label("user_phone"),
        users_table.c.email.label("user_email"),
    ).select_from(
        good_deeds_table.outerjoin(
            users_table,
            good_deeds_table.c.user_id == users_table.c.user_id,
        )
    )


def _good_deed_needy_select():
    return select(
        good_deed_needy_table,
        users_table.c.full_name.label("user_full_name"),
        users_table.c.phone_number.label("user_phone"),
        users_table.c.email.label("user_email"),
    ).select_from(
        good_deed_needy_table.outerjoin(
            users_table,
            good_deed_needy_table.c.created_by_user_id == users_table.c.user_id,
        )
    )


def _good_deed_confirmations_select():
    return select(
        good_deed_confirmations_table,
        users_table.c.full_name.label("user_full_name"),
        users_table.c.phone_number.label("user_phone"),
        users_table.c.email.label("user_email"),
        good_deeds_table.c.title.label("good_deed_title"),
        good_deeds_table.c.status.label("good_deed_status"),
    ).select_from(
        good_deed_confirmations_table.outerjoin(
            users_table,
            good_deed_confirmations_table.c.created_by_user_id == users_table.c.user_id,
        ).outerjoin(
            good_deeds_table,
            good_deed_confirmations_table.c.good_deed_id == good_deeds_table.c.id,
        )
    )


def _shariah_applications_select():
    return select(
        shariah_admin_applications_table,
        users_table.c.full_name.label("user_full_name"),
        users_table.c.phone_number.label("user_phone"),
        users_table.c.email.label("user_email"),
    ).select_from(
        shariah_admin_applications_table.outerjoin(
            users_table,
            shariah_admin_applications_table.c.user_id == users_table.c.user_id,
        )
    )


def _serialize_good_deed(row: dict) -> GoodDeedOut:
    amount_value = row.get("amount")
    amount = float(amount_value) if amount_value is not None else None
    return GoodDeedOut(
        id=int(row.get("id") or 0),
        user_id=int(row.get("user_id") or 0),
        user_full_name=row.get("user_full_name"),
        user_phone=row.get("user_phone"),
        user_email=row.get("user_email"),
        title=str(row.get("title") or ""),
        description=str(row.get("description") or ""),
        city=str(row.get("city") or ""),
        country=str(row.get("country") or ""),
        help_type=str(row.get("help_type") or ""),
        amount=amount,
        comment=row.get("comment"),
        status=str(row.get("status") or ""),
        approved_category=row.get("approved_category"),
        review_comment=row.get("review_comment"),
        reviewed_by_admin_id=row.get("reviewed_by_admin_id"),
        clarification_text=row.get("clarification_text"),
        clarification_attachment=_decode_json_object(row.get("clarification_attachment")),
        history=_decode_json_list(row.get("history")),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
        approved_at=row.get("approved_at"),
        completed_at=row.get("completed_at"),
    )


def _serialize_needy(row: dict) -> GoodDeedNeedyOut:
    return GoodDeedNeedyOut(
        id=int(row.get("id") or 0),
        created_by_user_id=int(row.get("created_by_user_id") or 0),
        user_full_name=row.get("user_full_name"),
        user_phone=row.get("user_phone"),
        user_email=row.get("user_email"),
        person_type=str(row.get("person_type") or ""),
        city=str(row.get("city") or ""),
        country=str(row.get("country") or ""),
        reason=str(row.get("reason") or ""),
        allow_zakat=bool(row.get("allow_zakat")),
        allow_fitr=bool(row.get("allow_fitr")),
        sadaqa_only=bool(row.get("sadaqa_only")),
        comment=row.get("comment"),
        status=str(row.get("status") or ""),
        review_comment=row.get("review_comment"),
        reviewed_by_admin_id=row.get("reviewed_by_admin_id"),
        history=_decode_json_list(row.get("history")),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
        approved_at=row.get("approved_at"),
    )


def _serialize_confirmation(row: dict) -> GoodDeedConfirmationOut:
    return GoodDeedConfirmationOut(
        id=int(row.get("id") or 0),
        good_deed_id=int(row.get("good_deed_id") or 0),
        good_deed_title=row.get("good_deed_title"),
        good_deed_status=row.get("good_deed_status"),
        created_by_user_id=int(row.get("created_by_user_id") or 0),
        user_full_name=row.get("user_full_name"),
        user_phone=row.get("user_phone"),
        user_email=row.get("user_email"),
        text=row.get("text"),
        attachment=_decode_json_object(row.get("attachment")),
        status=str(row.get("status") or ""),
        review_comment=row.get("review_comment"),
        reviewed_by_admin_id=row.get("reviewed_by_admin_id"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
        reviewed_at=row.get("reviewed_at"),
    )


def _serialize_shariah_application(row: dict) -> ShariahAdminApplicationOut:
    return ShariahAdminApplicationOut(
        id=int(row.get("id") or 0),
        user_id=int(row.get("user_id") or 0),
        user_full_name=row.get("user_full_name"),
        user_phone=row.get("user_phone"),
        user_email=row.get("user_email"),
        full_name=str(row.get("full_name") or ""),
        country=str(row.get("country") or ""),
        city=str(row.get("city") or ""),
        education_place=str(row.get("education_place") or ""),
        education_completed=bool(row.get("education_completed")),
        education_details=row.get("education_details"),
        knowledge_areas=_decode_json_list(row.get("knowledge_areas")),
        experience=row.get("experience"),
        responsibility_accepted=bool(row.get("responsibility_accepted")),
        status=str(row.get("status") or ""),
        meeting_type=row.get("meeting_type"),
        meeting_link=row.get("meeting_link"),
        meeting_at=row.get("meeting_at"),
        decision_comment=row.get("decision_comment"),
        decision_by_admin_id=row.get("decision_by_admin_id"),
        assigned_roles=_decode_json_list(row.get("assigned_roles")),
        history=_decode_json_list(row.get("history")),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _notify_user(session: Session, *, user_id: int, text: str, payload: Optional[dict] = None) -> None:
    payload_data = {"text": text}
    if payload:
        payload_data.update(payload)
    session.execute(
        insert(notifications_table).values(
            user_id=int(user_id),
            kind="admin_message",
            payload=_encode_payload(payload_data),
        )
    )


def _ensure_admin_account_for_user(session: Session, *, telegram_id: int) -> tuple[int, str, Optional[str]]:
    existing = session.execute(
        select(admin_accounts_table.c.id, admin_accounts_table.c.username).where(
            admin_accounts_table.c.telegram_id == int(telegram_id)
        )
    ).mappings().one_or_none()
    if existing:
        return int(existing["id"]), str(existing["username"]), None
    base_username = f"tg_{telegram_id}"
    username = base_username
    counter = 1
    while session.execute(
        select(admin_accounts_table.c.id).where(admin_accounts_table.c.username == username)
    ).scalar_one_or_none():
        counter += 1
        username = f"{base_username}_{counter}"
    password = secrets.token_urlsafe(8)
    account_id = session.execute(
        insert(admin_accounts_table)
        .values(
            username=username,
            password_hash=_hash_password(password),
            telegram_id=int(telegram_id),
            is_active=True,
        )
        .returning(admin_accounts_table.c.id)
    ).scalar_one()
    return int(account_id), username, password


@app.get(
    "/admin/good-deeds",
    response_model=List[GoodDeedOut],
    dependencies=[
        Depends(
            require_roles(
                OWNER_ROLE,
                SUPERADMIN_ROLE,
                TZ_GOOD_DEEDS_ROLE,
                SHARIAH_CHIEF_ROLE,
                SHARIAH_OBSERVER_ROLE,
            )
        )
    ],
)
async def admin_list_good_deeds(
    status: Optional[str] = Query(default=None),
    city: Optional[str] = Query(default=None),
    country: Optional[str] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    session: Session = Depends(db_session_dependency),
) -> List[GoodDeedOut]:
    stmt = _good_deeds_select().order_by(good_deeds_table.c.created_at.desc()).limit(limit)
    if status:
        statuses = [s.strip().lower() for s in status.split(",") if s.strip()]
        if statuses:
            stmt = stmt.where(func.lower(good_deeds_table.c.status).in_(statuses))
    if city:
        stmt = stmt.where(func.lower(good_deeds_table.c.city).like(f"%{city.strip()}%"))
    if country:
        stmt = stmt.where(func.lower(good_deeds_table.c.country).like(f"%{country.strip()}%"))
    rows = session.execute(stmt).mappings().all()
    return [_serialize_good_deed(row) for row in rows]


@app.get(
    "/admin/good-deeds/{deed_id}",
    response_model=GoodDeedOut,
    dependencies=[
        Depends(
            require_roles(
                OWNER_ROLE,
                SUPERADMIN_ROLE,
                TZ_GOOD_DEEDS_ROLE,
                SHARIAH_CHIEF_ROLE,
                SHARIAH_OBSERVER_ROLE,
            )
        )
    ],
)
async def admin_get_good_deed(
    deed_id: int,
    session: Session = Depends(db_session_dependency),
) -> GoodDeedOut:
    row = (
        session.execute(_good_deeds_select().where(good_deeds_table.c.id == deed_id))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Good deed not found.")
    return _serialize_good_deed(row)


@app.patch(
    "/admin/good-deeds/{deed_id}/decision",
    response_model=GoodDeedOut,
    dependencies=[
        Depends(
            require_roles(
                OWNER_ROLE,
                SUPERADMIN_ROLE,
                TZ_GOOD_DEEDS_ROLE,
                SHARIAH_CHIEF_ROLE,
            )
        )
    ],
)
async def admin_decide_good_deed(
    deed_id: int,
    payload: GoodDeedDecision = Depends(_parse_good_deed_decision_request),
    session: Session = Depends(db_session_dependency),
    admin: dict = Depends(get_current_admin),
) -> GoodDeedOut:
    status_value = payload.status.strip().lower()
    if status_value not in {"approved", "needs_clarification", "rejected"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status.")
    comment = payload.review_comment.strip()
    if not comment:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Review comment is required.")
    approved_category = payload.approved_category.strip().lower() if payload.approved_category else None
    if status_value == "approved":
        if approved_category not in {"zakat", "fitr", "sadaqa"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Approved category is required.")
    row = session.execute(
        select(
            good_deeds_table.c.user_id,
            good_deeds_table.c.history,
        ).where(good_deeds_table.c.id == deed_id)
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Good deed not found.")
    now = datetime.now(timezone.utc)
    event = {
        "at": now.isoformat(),
        "action": "admin_decision",
        "status": status_value,
        "comment": comment,
        "actor_admin_id": int(admin.get("id") or 0),
    }
    updates: dict[str, Any] = {
        "status": status_value,
        "review_comment": comment,
        "reviewed_by_admin_id": int(admin.get("id") or 0),
        "updated_at": now,
        "history": _append_history(row.get("history"), event),
    }
    if status_value == "approved":
        updates["approved_category"] = approved_category
        updates["approved_at"] = now
    session.execute(
        update(good_deeds_table).where(good_deeds_table.c.id == deed_id).values(**updates)
    )
    if status_value == "approved":
        text = f"Р”РѕР±СЂРѕРµ РґРµР»Рѕ в„–{deed_id} РѕРґРѕР±СЂРµРЅРѕ. РљР°С‚РµРіРѕСЂРёСЏ: {approved_category}. {comment}"
    elif status_value == "needs_clarification":
        text = f"РџРѕ РґРѕР±СЂРѕРјСѓ РґРµР»Сѓ в„–{deed_id} С‚СЂРµР±СѓСЋС‚СЃСЏ СѓС‚РѕС‡РЅРµРЅРёСЏ: {comment}"
    else:
        text = f"Р”РѕР±СЂРѕРµ РґРµР»Рѕ в„–{deed_id} РѕС‚РєР»РѕРЅРµРЅРѕ: {comment}"
    _notify_user(session, user_id=int(row["user_id"]), text=text, payload={"good_deed_id": deed_id})
    updated = (
        session.execute(_good_deeds_select().where(good_deeds_table.c.id == deed_id))
        .mappings()
        .one()
    )
    return _serialize_good_deed(updated)


@app.get(
    "/admin/good-deeds/needy",
    response_model=List[GoodDeedNeedyOut],
    dependencies=[
        Depends(
            require_roles(
                OWNER_ROLE,
                SUPERADMIN_ROLE,
                TZ_GOOD_DEEDS_ROLE,
                SHARIAH_CHIEF_ROLE,
                SHARIAH_OBSERVER_ROLE,
            )
        )
    ],
)
async def admin_list_good_deed_needy(
    status: Optional[str] = Query(default=None),
    city: Optional[str] = Query(default=None),
    country: Optional[str] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    session: Session = Depends(db_session_dependency),
) -> List[GoodDeedNeedyOut]:
    stmt = _good_deed_needy_select().order_by(good_deed_needy_table.c.created_at.desc()).limit(limit)
    if status:
        statuses = [s.strip().lower() for s in status.split(",") if s.strip()]
        if statuses:
            stmt = stmt.where(func.lower(good_deed_needy_table.c.status).in_(statuses))
    if city:
        stmt = stmt.where(func.lower(good_deed_needy_table.c.city).like(f"%{city.strip()}%"))
    if country:
        stmt = stmt.where(func.lower(good_deed_needy_table.c.country).like(f"%{country.strip()}%"))
    rows = session.execute(stmt).mappings().all()
    return [_serialize_needy(row) for row in rows]


@app.get(
    "/admin/good-deeds/needy/{needy_id}",
    response_model=GoodDeedNeedyOut,
    dependencies=[
        Depends(
            require_roles(
                OWNER_ROLE,
                SUPERADMIN_ROLE,
                TZ_GOOD_DEEDS_ROLE,
                SHARIAH_CHIEF_ROLE,
                SHARIAH_OBSERVER_ROLE,
            )
        )
    ],
)
async def admin_get_good_deed_needy(
    needy_id: int,
    session: Session = Depends(db_session_dependency),
) -> GoodDeedNeedyOut:
    row = (
        session.execute(_good_deed_needy_select().where(good_deed_needy_table.c.id == needy_id))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Needy entry not found.")
    return _serialize_needy(row)


@app.patch(
    "/admin/good-deeds/needy/{needy_id}/decision",
    response_model=GoodDeedNeedyOut,
    dependencies=[
        Depends(
            require_roles(
                OWNER_ROLE,
                SUPERADMIN_ROLE,
                TZ_GOOD_DEEDS_ROLE,
                SHARIAH_CHIEF_ROLE,
            )
        )
    ],
)
async def admin_decide_good_deed_needy(
    needy_id: int,
    payload: GoodDeedNeedyDecision = Depends(_parse_needy_decision_request),
    session: Session = Depends(db_session_dependency),
    admin: dict = Depends(get_current_admin),
) -> GoodDeedNeedyOut:
    status_value = payload.status.strip().lower()
    if status_value not in {"approved", "needs_clarification", "rejected"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status.")
    comment = payload.review_comment.strip()
    if not comment:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Review comment is required.")
    row = session.execute(
        select(
            good_deed_needy_table.c.created_by_user_id,
            good_deed_needy_table.c.history,
        ).where(good_deed_needy_table.c.id == needy_id)
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Needy entry not found.")
    now = datetime.now(timezone.utc)
    event = {
        "at": now.isoformat(),
        "action": "admin_decision",
        "status": status_value,
        "comment": comment,
        "actor_admin_id": int(admin.get("id") or 0),
    }
    updates: dict[str, Any] = {
        "status": status_value,
        "review_comment": comment,
        "reviewed_by_admin_id": int(admin.get("id") or 0),
        "updated_at": now,
        "history": _append_history(row.get("history"), event),
    }
    if status_value == "approved":
        updates["approved_at"] = now
    session.execute(
        update(good_deed_needy_table).where(good_deed_needy_table.c.id == needy_id).values(**updates)
    )
    if status_value == "approved":
        text = f"Р—Р°РїРёСЃСЊ РЅСѓР¶РґР°СЋС‰РµРіРѕСЏ в„–{needy_id} РѕРґРѕР±СЂРµРЅР°. {comment}"
    elif status_value == "needs_clarification":
        text = f"РџРѕ Р·Р°РїРёСЃРё РЅСѓР¶РґР°СЋС‰РµРіРѕСЏ в„–{needy_id} С‚СЂРµР±СѓСЋС‚СЃСЏ СѓС‚РѕС‡РЅРµРЅРёСЏ: {comment}"
    else:
        text = f"Р—Р°РїРёСЃСЊ РЅСѓР¶РґР°СЋС‰РµРіРѕСЏ в„–{needy_id} РѕС‚РєР»РѕРЅРµРЅР°: {comment}"
    _notify_user(session, user_id=int(row["created_by_user_id"]), text=text, payload={"needy_id": needy_id})
    updated = (
        session.execute(_good_deed_needy_select().where(good_deed_needy_table.c.id == needy_id))
        .mappings()
        .one()
    )
    return _serialize_needy(updated)


@app.get(
    "/admin/good-deeds/confirmations",
    response_model=List[GoodDeedConfirmationOut],
    dependencies=[
        Depends(
            require_roles(
                OWNER_ROLE,
                SUPERADMIN_ROLE,
                TZ_GOOD_DEEDS_ROLE,
                SHARIAH_CHIEF_ROLE,
                SHARIAH_OBSERVER_ROLE,
            )
        )
    ],
)
async def admin_list_good_deed_confirmations(
    status: Optional[str] = Query(default=None),
    good_deed_id: Optional[int] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    session: Session = Depends(db_session_dependency),
) -> List[GoodDeedConfirmationOut]:
    stmt = _good_deed_confirmations_select().order_by(good_deed_confirmations_table.c.created_at.desc()).limit(limit)
    if status:
        statuses = [s.strip().lower() for s in status.split(",") if s.strip()]
        if statuses:
            stmt = stmt.where(func.lower(good_deed_confirmations_table.c.status).in_(statuses))
    if good_deed_id:
        stmt = stmt.where(good_deed_confirmations_table.c.good_deed_id == good_deed_id)
    rows = session.execute(stmt).mappings().all()
    return [_serialize_confirmation(row) for row in rows]


@app.get(
    "/admin/good-deeds/confirmations/{confirmation_id}",
    response_model=GoodDeedConfirmationOut,
    dependencies=[
        Depends(
            require_roles(
                OWNER_ROLE,
                SUPERADMIN_ROLE,
                TZ_GOOD_DEEDS_ROLE,
                SHARIAH_CHIEF_ROLE,
                SHARIAH_OBSERVER_ROLE,
            )
        )
    ],
)
async def admin_get_good_deed_confirmation(
    confirmation_id: int,
    session: Session = Depends(db_session_dependency),
) -> GoodDeedConfirmationOut:
    row = (
        session.execute(
            _good_deed_confirmations_select().where(
                good_deed_confirmations_table.c.id == confirmation_id
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confirmation not found.")
    return _serialize_confirmation(row)


@app.patch(
    "/admin/good-deeds/confirmations/{confirmation_id}/decision",
    response_model=GoodDeedConfirmationOut,
    dependencies=[
        Depends(
            require_roles(
                OWNER_ROLE,
                SUPERADMIN_ROLE,
                TZ_GOOD_DEEDS_ROLE,
                SHARIAH_CHIEF_ROLE,
            )
        )
    ],
)
async def admin_decide_good_deed_confirmation(
    confirmation_id: int,
    payload: GoodDeedConfirmationDecision = Depends(_parse_confirmation_decision_request),
    session: Session = Depends(db_session_dependency),
    admin: dict = Depends(get_current_admin),
) -> GoodDeedConfirmationOut:
    status_value = payload.status.strip().lower()
    if status_value not in {"approved", "rejected"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status.")
    comment = payload.review_comment.strip()
    if not comment:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Review comment is required.")
    confirmation_row = session.execute(
        select(
            good_deed_confirmations_table.c.good_deed_id,
            good_deed_confirmations_table.c.created_by_user_id,
        ).where(good_deed_confirmations_table.c.id == confirmation_id)
    ).mappings().one_or_none()
    if confirmation_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confirmation not found.")
    now = datetime.now(timezone.utc)
    session.execute(
        update(good_deed_confirmations_table)
        .where(good_deed_confirmations_table.c.id == confirmation_id)
        .values(
            status=status_value,
            review_comment=comment,
            reviewed_by_admin_id=int(admin.get("id") or 0),
            reviewed_at=now,
            updated_at=now,
        )
    )
    deed_row = session.execute(
        select(
            good_deeds_table.c.history,
        ).where(good_deeds_table.c.id == int(confirmation_row["good_deed_id"]))
    ).mappings().one_or_none()
    if deed_row is not None:
        event = {
            "at": now.isoformat(),
            "action": "confirmation_reviewed",
            "status": status_value,
            "comment": comment,
            "actor_admin_id": int(admin.get("id") or 0),
        }
        deed_updates: dict[str, Any] = {
            "updated_at": now,
            "history": _append_history(deed_row.get("history"), event),
        }
        if status_value == "approved":
            deed_updates["status"] = "completed"
            deed_updates["completed_at"] = now
        session.execute(
            update(good_deeds_table)
            .where(good_deeds_table.c.id == int(confirmation_row["good_deed_id"]))
            .values(**deed_updates)
        )
    if status_value == "approved":
        text = f"РџРѕРґС‚РІРµСЂР¶РґРµРЅРёРµ в„–{confirmation_id} РѕРґРѕР±СЂРµРЅРѕ. {comment}"
    else:
        text = f"РџРѕРґС‚РІРµСЂР¶РґРµРЅРёРµ в„–{confirmation_id} РѕС‚РєР»РѕРЅРµРЅРѕ: {comment}"
    _notify_user(
        session,
        user_id=int(confirmation_row["created_by_user_id"]),
        text=text,
        payload={"confirmation_id": confirmation_id},
    )
    updated = (
        session.execute(
            _good_deed_confirmations_select().where(
                good_deed_confirmations_table.c.id == confirmation_id
            )
        )
        .mappings()
        .one()
    )
    return _serialize_confirmation(updated)


@app.get(
    "/admin/good-deeds/{deed_id}/clarification/download",
    dependencies=[
        Depends(
            require_roles(
                OWNER_ROLE,
                SUPERADMIN_ROLE,
                TZ_GOOD_DEEDS_ROLE,
                SHARIAH_CHIEF_ROLE,
                SHARIAH_OBSERVER_ROLE,
            )
        )
    ],
)
async def admin_download_good_deed_clarification(
    deed_id: int,
    session: Session = Depends(db_session_dependency),
) -> StreamingResponse:
    row = session.execute(
        select(good_deeds_table.c.clarification_attachment).where(good_deeds_table.c.id == deed_id)
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Good deed not found.")
    attachment = _decode_json_object(row.get("clarification_attachment"))
    file_id = attachment.get("file_id") if attachment else None
    if not file_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attachment has no file.")
    content, filename = _download_telegram_file(str(file_id))
    media_type = attachment.get("mime_type") if attachment else "application/octet-stream"
    return StreamingResponse(
        iter([content]),
        media_type=media_type or "application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get(
    "/admin/good-deeds/confirmations/{confirmation_id}/download",
    dependencies=[
        Depends(
            require_roles(
                OWNER_ROLE,
                SUPERADMIN_ROLE,
                TZ_GOOD_DEEDS_ROLE,
                SHARIAH_CHIEF_ROLE,
                SHARIAH_OBSERVER_ROLE,
            )
        )
    ],
)
async def admin_download_good_deed_confirmation(
    confirmation_id: int,
    session: Session = Depends(db_session_dependency),
) -> StreamingResponse:
    row = session.execute(
        select(good_deed_confirmations_table.c.attachment).where(
            good_deed_confirmations_table.c.id == confirmation_id
        )
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confirmation not found.")
    attachment = _decode_json_object(row.get("attachment"))
    file_id = attachment.get("file_id") if attachment else None
    if not file_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attachment has no file.")
    content, filename = _download_telegram_file(str(file_id))
    media_type = attachment.get("mime_type") if attachment else "application/octet-stream"
    return StreamingResponse(
        iter([content]),
        media_type=media_type or "application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get(
    "/admin/shariah-applications",
    response_model=List[ShariahAdminApplicationOut],
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, SHARIAH_CHIEF_ROLE))],
)
async def admin_list_shariah_applications(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    session: Session = Depends(db_session_dependency),
) -> List[ShariahAdminApplicationOut]:
    stmt = _shariah_applications_select().order_by(
        shariah_admin_applications_table.c.created_at.desc()
    ).limit(limit)
    if status:
        statuses = [s.strip().lower() for s in status.split(",") if s.strip()]
        if statuses:
            stmt = stmt.where(func.lower(shariah_admin_applications_table.c.status).in_(statuses))
    rows = session.execute(stmt).mappings().all()
    return [_serialize_shariah_application(row) for row in rows]


@app.get(
    "/admin/shariah-applications/{application_id}",
    response_model=ShariahAdminApplicationOut,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, SHARIAH_CHIEF_ROLE))],
)
async def admin_get_shariah_application(
    application_id: int,
    session: Session = Depends(db_session_dependency),
) -> ShariahAdminApplicationOut:
    row = (
        session.execute(
            _shariah_applications_select().where(
                shariah_admin_applications_table.c.id == application_id
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")
    return _serialize_shariah_application(row)


@app.post(
    "/admin/shariah-applications/{application_id}/schedule",
    response_model=ShariahAdminApplicationOut,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, SHARIAH_CHIEF_ROLE))],
)
async def admin_schedule_shariah_application(
    application_id: int,
    payload: ShariahAdminSchedule = Depends(_parse_shariah_schedule_request),
    session: Session = Depends(db_session_dependency),
    admin: dict = Depends(get_current_admin),
) -> ShariahAdminApplicationOut:
    row = session.execute(
        select(
            shariah_admin_applications_table.c.user_id,
            shariah_admin_applications_table.c.history,
        ).where(shariah_admin_applications_table.c.id == application_id)
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")
    meeting_type = payload.meeting_type.strip()
    meeting_link = payload.meeting_link.strip()
    if not meeting_link:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Meeting link is required.")
    now = datetime.now(timezone.utc)
    event = {
        "at": now.isoformat(),
        "action": "meeting_scheduled",
        "status": "meeting_scheduled",
        "actor_admin_id": int(admin.get("id") or 0),
    }
    session.execute(
        update(shariah_admin_applications_table)
        .where(shariah_admin_applications_table.c.id == application_id)
        .values(
            meeting_type=meeting_type,
            meeting_link=meeting_link,
            meeting_at=payload.meeting_at,
            status="meeting_scheduled",
            updated_at=now,
            history=_append_history(row.get("history"), event),
        )
    )
    meeting_at_text = payload.meeting_at.isoformat()
    text = (
        "РќР°Р·РЅР°С‡РµРЅРѕ Р·РЅР°РєРѕРјСЃС‚РІРѕ.\n"
        f"РўРёРї: {meeting_type}\n"
        f"Р’СЂРµРјСЏ: {meeting_at_text}\n"
        f"РЎСЃС‹Р»РєР°: {meeting_link}"
    )
    _notify_user(session, user_id=int(row["user_id"]), text=text, payload={"application_id": application_id})
    updated = (
        session.execute(
            _shariah_applications_select().where(
                shariah_admin_applications_table.c.id == application_id
            )
        )
        .mappings()
        .one()
    )
    return _serialize_shariah_application(updated)


@app.post(
    "/admin/shariah-applications/{application_id}/decision",
    response_model=ShariahAdminApplicationOut,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, SHARIAH_CHIEF_ROLE))],
)
async def admin_decide_shariah_application(
    application_id: int,
    payload: ShariahAdminDecision = Depends(_parse_shariah_decision_request),
    session: Session = Depends(db_session_dependency),
    admin: dict = Depends(get_current_admin),
) -> ShariahAdminApplicationOut:
    status_value = payload.status.strip().lower()
    if status_value not in {"approved", "observer", "rejected"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status.")
    comment = payload.comment.strip()
    if not comment:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Decision comment is required.")
    row = session.execute(
        select(
            shariah_admin_applications_table.c.user_id,
            shariah_admin_applications_table.c.history,
        ).where(shariah_admin_applications_table.c.id == application_id)
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")
    role_slugs = [slug.strip() for slug in (payload.roles or []) if slug and slug.strip()]
    allowed_roles = {
        TZ_COURTS_ROLE,
        TZ_CONTRACTS_ROLE,
        TZ_GOOD_DEEDS_ROLE,
        TZ_EXECUTION_ROLE,
        SHARIAH_CHIEF_ROLE,
    }
    if status_value == "approved":
        if not role_slugs or len(role_slugs) > 2:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Select 1 or 2 roles.")
        if any(role not in allowed_roles for role in role_slugs):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid roles selected.")
    elif status_value == "observer":
        role_slugs = [SHARIAH_OBSERVER_ROLE]
    else:
        role_slugs = []
    now = datetime.now(timezone.utc)
    created_password = None
    created_username = None
    if role_slugs:
        account_id, created_username, created_password = _ensure_admin_account_for_user(
            session, telegram_id=int(row["user_id"])
        )
        _ensure_role_assignment(
            session=session,
            admin_account_id=account_id,
            role_slugs=role_slugs,
            current_roles=set(admin.get("roles") or []),
        )
    event = {
        "at": now.isoformat(),
        "action": "decision",
        "status": status_value,
        "comment": comment,
        "actor_admin_id": int(admin.get("id") or 0),
    }
    updates: dict[str, Any] = {
        "status": status_value,
        "decision_comment": comment,
        "decision_by_admin_id": int(admin.get("id") or 0),
        "updated_at": now,
        "history": _append_history(row.get("history"), event),
    }
    if role_slugs:
        updates["assigned_roles"] = json.dumps(role_slugs, ensure_ascii=False)
    session.execute(
        update(shariah_admin_applications_table)
        .where(shariah_admin_applications_table.c.id == application_id)
        .values(**updates)
    )
    if status_value == "approved":
        roles_text = ", ".join(role_slugs)
        text = f"Р’Р°С€Р° Р·Р°СЏРІРєР° РѕРґРѕР±СЂРµРЅР°. Р РѕР»Рё: {roles_text}. {comment}"
    elif status_value == "observer":
        text = f"Р’С‹ РЅР°Р·РЅР°С‡РµРЅС‹ РЅР°Р±Р»СЋРґР°С‚РµР»РµРј. {comment}"
    else:
        text = f"Р’Р°С€Р° Р·Р°СЏРІРєР° РѕС‚РєР»РѕРЅРµРЅР°: {comment}"
    if created_password and created_username:
        text = (
            f"{text}\n\n"
            f"Р›РѕРіРёРЅ: {created_username}\n"
            f"РџР°СЂРѕР»СЊ: {created_password}"
        )
    _notify_user(session, user_id=int(row["user_id"]), text=text, payload={"application_id": application_id})
    updated = (
        session.execute(
            _shariah_applications_select().where(
                shariah_admin_applications_table.c.id == application_id
            )
        )
        .mappings()
        .one()
    )
    return _serialize_shariah_application(updated)


@app.get(
    "/admin/scholars",
    response_model=List[ScholarOut],
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_WORK_ITEMS_VIEW_ROLE))],
)
async def list_scholars(
    admin: dict = Depends(get_current_admin),
    session: Session = Depends(db_session_dependency),
) -> List[ScholarOut]:
    rows = (
        session.execute(
            select(
                admin_accounts_table.c.id,
                admin_accounts_table.c.username,
                admin_accounts_table.c.telegram_id,
            )
            .select_from(
                admin_accounts_table.join(
                    admin_account_roles_table,
                    admin_account_roles_table.c.admin_account_id == admin_accounts_table.c.id,
                ).join(
                    roles_table,
                    roles_table.c.id == admin_account_roles_table.c.role_id,
                )
            )
            .where(
                roles_table.c.slug == SCHOLAR_ROLE,
                admin_accounts_table.c.is_active.is_(True),
            )
            .order_by(admin_accounts_table.c.username)
        )
        .mappings()
        .all()
    )
    return [
        ScholarOut(
            id=int(row["id"]),
            username=str(row["username"] or ""),
            telegram_id=int(row["telegram_id"]) if row["telegram_id"] is not None else None,
        )
        for row in rows
    ]


def _spec_dir() -> Path:
    # backend/app/main.py -> repo root is two levels up
    return Path(__file__).resolve().parents[2] / "docs" / "ТЗ"


_SPEC_FILES: dict[str, tuple[str, str]] = {
    "nikah": ("NIKAH_RU.md", "👰🤵 Никях"),
    "inheritance": ("INHERITANCE_RU.md", "🪙 Наследство и завещания"),
    "spouse_search": ("SPOUSE_SEARCH_RU.md", "🌿 Знакомство и поиск супруга"),
    "courts": ("INHERITANCE_RU.md", "Суды"),
    "contracts": ("CONTRACTS_TEMPLATE_RU.md", "📄 Договоры"),
    "good_deeds": ("GOOD_DEEDS_RU.md", "👍 Добрые дела"),
    "shariah_control_registration": ("SHARIAH_CONTROL_REGISTRATION_RU.md", "🛡️ Шариатский контроль: Регистрация"),
    "shariah_control_web": ("SHARIAH_CONTROL_WEB_RU.md", "🛡️ Шариатский контроль: Веб-интерфейс"),
}


@app.get(
    "/admin/specs",
    response_model=List[SpecFileOut],
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_WORK_ITEMS_VIEW_ROLE))],
)
async def list_specs() -> List[SpecFileOut]:
    items: list[SpecFileOut] = []
    for key, (filename, title) in _SPEC_FILES.items():
        items.append(SpecFileOut(key=key, filename=filename, title=title))
    return items


@app.get(
    "/admin/specs/{key}",
    response_model=SpecContentOut,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_WORK_ITEMS_VIEW_ROLE))],
)
async def get_spec_content(key: str) -> SpecContentOut:
    normalized = (key or "").strip().lower()
    if normalized not in _SPEC_FILES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spec not found.")
    filename, _title = _SPEC_FILES[normalized]
    path = _spec_dir() / filename
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spec file missing on server.")
    content = path.read_text(encoding="utf-8", errors="replace")
    return SpecContentOut(key=normalized, filename=filename, content=content)
@app.patch(
    "/admin/users/{telegram_user_id}/ban",
    response_model=UserOut,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, DEFAULT_ADMIN_ROLE))],
)
async def set_ban_status(
    telegram_user_id: int,
    payload: BanRequest,
    session: Session = Depends(db_session_dependency),
) -> UserOut:
    updates: Dict[str, object] = {"banned": payload.banned}
    if payload.banned is False:
        # Clearing unban request metadata on unban
        updates["unban_request_text"] = None
        updates["unban_requested_at"] = None
    result = session.execute(
        update(users_table)
        .where(users_table.c.user_id == telegram_user_id)
        .values(**updates)
        .returning(users_table.c.user_id)
    ).scalar_one_or_none()
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    # Enqueue notification for unban
    if payload.banned is False:
        try:
            session.execute(
                insert(notifications_table).values(
                    user_id=telegram_user_id,
                    kind="user_unbanned",
                    payload=None,
                )
            )
        except Exception:
            pass
    out = _fetch_user_out(session, telegram_user_id)
    assert out is not None
    return out

@app.patch(
    "/admin/users/{telegram_user_id}/alive",
    response_model=UserOut,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, DEFAULT_ADMIN_ROLE))],
)
async def set_alive_status(
    telegram_user_id: int,
    payload: AliveRequest,
    session: Session = Depends(db_session_dependency),
) -> UserOut:
    result = session.execute(
        update(users_table)
        .where(users_table.c.user_id == telegram_user_id)
        .values(is_alive=payload.is_alive)
        .returning(users_table.c.user_id)
    ).scalar_one_or_none()
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    out = _fetch_user_out(session, telegram_user_id)
    assert out is not None
    return out



def _normalize_required_text(value: str, field_name: str) -> str:
    normalized = re.sub(r"\s+", " ", (value or "").strip())
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} is required.",
        )
    return normalized


def _normalize_optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = re.sub(r"\s+", " ", value.strip())
    return normalized or None


def _hash_password(raw: str) -> str:
    salted = (raw or "") + settings.jwt_secret_key
    return hashlib.sha256(salted.encode("utf-8")).hexdigest()


def _verify_password(raw: str, hashed: str) -> bool:
    return _hash_password(raw) == (hashed or "")


def _load_admin_account(session: Session, username: str) -> Optional[dict]:
    stmt = select(
        admin_accounts_table.c.id,
        admin_accounts_table.c.username,
        admin_accounts_table.c.password_hash,
        admin_accounts_table.c.telegram_id,
        admin_accounts_table.c.is_active,
    ).where(admin_accounts_table.c.username == username)
    row = session.execute(stmt).mappings().one_or_none()
    return dict(row) if row else None


def _load_admin_roles(session: Session, admin_id: int) -> List[str]:
    rows = session.execute(
        select(roles_table.c.slug)
        .select_from(
            roles_table.join(
                admin_account_roles_table,
                roles_table.c.id == admin_account_roles_table.c.role_id,
            )
        )
        .where(admin_account_roles_table.c.admin_account_id == admin_id)
    ).scalars()
    return [row for row in rows]


def _send_otp_to_telegram(telegram_id: int, text: str) -> None:
    token = settings.otp_bot_token
    if not token or not telegram_id:
        logger.warning("OTP not sent: bot token or telegram_id missing.")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": telegram_id, "text": text},
            timeout=5,
        )
    except Exception:
        logger.exception("Failed to send OTP to telegram_id=%s", telegram_id)


def _normalize_blacklist_phone(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    prefix = "+" if raw.startswith("+") else ""
    digits = re.sub(r"\D+", "", raw)
    if not digits:
        return None
    return prefix + digits if prefix else digits


def _normalize_blacklist_identity(name: str, phone: Optional[str], birthdate: Optional[date], city: Optional[str]) -> tuple[str, Optional[str], Optional[date], Optional[str]]:
    normalized_name = _normalize_required_text(name, "Name")
    normalized_phone = _normalize_blacklist_phone(phone)
    normalized_city = _normalize_optional_text(city)
    return normalized_name, normalized_phone, birthdate, normalized_city


def _blacklist_identity_filters(name: str, phone: Optional[str], birthdate: Optional[date], city: Optional[str]) -> list:
    filters = [blacklist_table.c.name == name]
    filters.append(blacklist_table.c.phone.is_(None) if phone is None else blacklist_table.c.phone == phone)
    filters.append(blacklist_table.c.birthdate.is_(None) if birthdate is None else blacklist_table.c.birthdate == birthdate)
    filters.append(blacklist_table.c.city.is_(None) if city is None else blacklist_table.c.city == city)
    return filters


def _blacklist_select_base():
    complaints_count = (
        select(func.count(blacklist_complaints_table.c.id))
        .where(blacklist_complaints_table.c.blacklist_id == blacklist_table.c.id)
        .correlate(blacklist_table)
        .scalar_subquery()
    )
    appeals_count = (
        select(func.count(blacklist_appeals_table.c.id))
        .where(blacklist_appeals_table.c.blacklist_id == blacklist_table.c.id)
        .correlate(blacklist_table)
        .scalar_subquery()
    )
    return select(
        blacklist_table.c.id,
        blacklist_table.c.date_added,
        blacklist_table.c.name,
        blacklist_table.c.phone,
        blacklist_table.c.birthdate,
        blacklist_table.c.city,
        blacklist_table.c.is_active,
        complaints_count.label("complaints_count"),
        appeals_count.label("appeals_count"),
    )


def _blacklist_entry_from_row(row) -> BlacklistEntryOut:
    data = dict(row)
    return BlacklistEntryOut(**data)


def _load_blacklist_entry_by_identity(
    session: Session,
    *,
    name: str,
    phone: Optional[str],
    birthdate: Optional[date],
    city: Optional[str],
) -> Optional[BlacklistEntryOut]:
    filters = _blacklist_identity_filters(name, phone, birthdate, city)
    stmt = _blacklist_select_base().where(*filters)
    row = session.execute(stmt).mappings().one_or_none()
    if row is None:
        return None
    return _blacklist_entry_from_row(row)


def _load_blacklist_entry(session: Session, blacklist_id: int) -> Optional[BlacklistEntryOut]:
    stmt = _blacklist_select_base().where(blacklist_table.c.id == blacklist_id)
    row = session.execute(stmt).mappings().one_or_none()
    if row is None:
        return None
    return _blacklist_entry_from_row(row)


def _get_or_create_blacklist_entry(
    session: Session,
    *,
    name: str,
    phone: Optional[str],
    birthdate: Optional[date],
    city: Optional[str],
) -> tuple[BlacklistEntryOut, bool]:
    existing = _load_blacklist_entry_by_identity(
        session, name=name, phone=phone, birthdate=birthdate, city=city
    )
    if existing is not None:
        return existing, False
    try:
        new_id = session.execute(
            insert(blacklist_table)
            .values(
                name=name,
                phone=phone,
                birthdate=birthdate,
                city=city,
            )
            .returning(blacklist_table.c.id)
        ).scalar_one()
    except IntegrityError:
        session.rollback()
        retry = _load_blacklist_entry_by_identity(
            session, name=name, phone=phone, birthdate=birthdate, city=city
        )
        if retry is None:
            raise
        return retry, False
    entry = _load_blacklist_entry(session, new_id)
    assert entry is not None
    return entry, True


def _list_blacklist_entries(
    session: Session,
    *,
    filters: Optional[list] = None,
    only_active: bool = False,
) -> List[BlacklistEntryOut]:
    stmt = _blacklist_select_base()
    conditions = []
    if only_active:
        conditions.append(blacklist_table.c.is_active.is_(True))
    if filters:
        conditions.extend(filters)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    stmt = stmt.order_by(
        blacklist_table.c.is_active.desc(),
        blacklist_table.c.date_added.desc(),
    )
    rows = session.execute(stmt).mappings().all()
    return [_blacklist_entry_from_row(row) for row in rows]


def _insert_blacklist_complaint(
    session: Session,
    *,
    blacklist_id: int,
    payload: BlacklistComplaintCreate,
) -> BlacklistComplaintOut:
    added_by = _normalize_required_text(payload.added_by, "Reporter name")
    added_by_phone = _normalize_blacklist_phone(payload.added_by_phone)
    reason = _normalize_required_text(payload.reason, "Reason")
    row = session.execute(
        insert(blacklist_complaints_table)
        .values(
            blacklist_id=blacklist_id,
            added_by=added_by,
            added_by_phone=added_by_phone,
            added_by_id=payload.added_by_id,
            reason=reason,
        )
        .returning(
            blacklist_complaints_table.c.id,
            blacklist_complaints_table.c.blacklist_id,
            blacklist_complaints_table.c.complaint_date,
            blacklist_complaints_table.c.added_by,
            blacklist_complaints_table.c.added_by_phone,
            blacklist_complaints_table.c.added_by_id,
            blacklist_complaints_table.c.reason,
        )
    ).mappings().one()
    return BlacklistComplaintOut(**row, media=[])


def _insert_blacklist_appeal(
    session: Session,
    *,
    blacklist_id: int,
    payload: BlacklistAppealCreate,
) -> BlacklistAppealOut:
    appeal_by = _normalize_required_text(payload.appeal_by, "Appeal author")
    appeal_by_phone = _normalize_blacklist_phone(payload.appeal_by_phone)
    reason = _normalize_required_text(payload.reason, "Reason")
    row = session.execute(
        insert(blacklist_appeals_table)
        .values(
            blacklist_id=blacklist_id,
            is_appeal=payload.is_appeal,
            appeal_by=appeal_by,
            appeal_by_phone=appeal_by_phone,
            appeal_by_id=payload.appeal_by_id,
            reason=reason,
        )
        .returning(
            blacklist_appeals_table.c.id,
            blacklist_appeals_table.c.blacklist_id,
            blacklist_appeals_table.c.appeal_date,
            blacklist_appeals_table.c.is_appeal,
            blacklist_appeals_table.c.appeal_by,
            blacklist_appeals_table.c.appeal_by_phone,
            blacklist_appeals_table.c.appeal_by_id,
            blacklist_appeals_table.c.reason,
        )
    ).mappings().one()
    return BlacklistAppealOut(**row, media=[])


def _blacklist_media_from_row(row) -> BlacklistMediaOut:
    return BlacklistMediaOut(
        id=row["id"],
        filename=row["filename"],
        content_type=row["content_type"],
        size=row["size"],
        uploaded_at=row["uploaded_at"],
    )


def _fetch_complaint_media_map(session: Session, complaint_ids: list[int]) -> dict[int, List[BlacklistMediaOut]]:
    if not complaint_ids:
        return {}
    rows = session.execute(
        select(
            blacklist_complaint_media_table.c.id,
            blacklist_complaint_media_table.c.complaint_id,
            blacklist_complaint_media_table.c.filename,
            blacklist_complaint_media_table.c.content_type,
            blacklist_complaint_media_table.c.size,
            blacklist_complaint_media_table.c.uploaded_at,
        ).where(blacklist_complaint_media_table.c.complaint_id.in_(complaint_ids))
    ).mappings().all()
    media_map: dict[int, List[BlacklistMediaOut]] = {cid: [] for cid in complaint_ids}
    for row in rows:
        media_map.setdefault(row["complaint_id"], []).append(_blacklist_media_from_row(row))
    for items in media_map.values():
        items.sort(key=lambda item: item.uploaded_at)
    return media_map


def _fetch_appeal_media_map(session: Session, appeal_ids: list[int]) -> dict[int, List[BlacklistMediaOut]]:
    if not appeal_ids:
        return {}
    rows = session.execute(
        select(
            blacklist_appeal_media_table.c.id,
            blacklist_appeal_media_table.c.appeal_id,
            blacklist_appeal_media_table.c.filename,
            blacklist_appeal_media_table.c.content_type,
            blacklist_appeal_media_table.c.size,
            blacklist_appeal_media_table.c.uploaded_at,
        ).where(blacklist_appeal_media_table.c.appeal_id.in_(appeal_ids))
    ).mappings().all()
    media_map: dict[int, List[BlacklistMediaOut]] = {aid: [] for aid in appeal_ids}
    for row in rows:
        media_map.setdefault(row["appeal_id"], []).append(_blacklist_media_from_row(row))
    for items in media_map.values():
        items.sort(key=lambda item: item.uploaded_at)
    return media_map


def _validate_media_upload(content_type: Optional[str], size: int) -> None:
    if size <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )
    if size > BLACKLIST_MEDIA_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File is too large. Max {BLACKLIST_MEDIA_MAX_BYTES // (1024 * 1024)} MB.",
        )
    if not content_type or not content_type.lower().startswith(BLACKLIST_ALLOWED_MEDIA_PREFIXES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only image or video files are allowed.",
        )


def _ensure_reporter_allowed(expected_id: Optional[int], provided_id: Optional[int]) -> None:
    if expected_id is None:
        return
    if provided_id is None or int(provided_id) != int(expected_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Reporter mismatch.",
        )


def _create_login_challenge(
    session: Session,
    *,
    admin_account_id: int,
    ttl_seconds: int,
    max_attempts: int,
) -> tuple[str, str, datetime]:
    pending_token = uuid.uuid4().hex
    otp_code = f"{secrets.randbelow(1000000):06d}"
    expires_at = datetime.utcnow().replace(tzinfo=timezone.utc) + timedelta(seconds=ttl_seconds)
    session.execute(
        insert(login_challenges_table).values(
            admin_account_id=admin_account_id,
            pending_token=pending_token,
            otp_code=otp_code,
            expires_at=expires_at,
            attempts_left=max_attempts,
        )
    )
    return pending_token, otp_code, expires_at


def _verify_login_challenge(
    session: Session,
    *,
    pending_token: str,
    code: str,
) -> int:
    challenge = session.execute(
        select(
            login_challenges_table.c.id,
            login_challenges_table.c.admin_account_id,
            login_challenges_table.c.otp_code,
            login_challenges_table.c.expires_at,
            login_challenges_table.c.attempts_left,
        ).where(login_challenges_table.c.pending_token == pending_token)
    ).mappings().one_or_none()
    if challenge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Challenge not found.",
        )
    if challenge["expires_at"] < datetime.utcnow().replace(tzinfo=timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP expired.",
        )
    if challenge["attempts_left"] <= 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="No attempts left.",
        )
    if challenge["otp_code"] != code.strip():
        session.execute(
            update(login_challenges_table)
            .where(login_challenges_table.c.id == challenge["id"])
            .values(attempts_left=challenge["attempts_left"] - 1)
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP code.",
        )
    session.execute(
        delete(login_challenges_table).where(login_challenges_table.c.id == challenge["id"])
    )
    return challenge["admin_account_id"]


def _insert_complaint_media(
    session: Session,
    *,
    complaint_id: int,
    filename: str,
    content_type: str,
    data: bytes,
) -> BlacklistMediaOut:
    row = session.execute(
        insert(blacklist_complaint_media_table)
        .values(
            complaint_id=complaint_id,
            filename=filename,
            content_type=content_type,
            content=data,
            size=len(data),
        )
        .returning(
            blacklist_complaint_media_table.c.id,
            blacklist_complaint_media_table.c.filename,
            blacklist_complaint_media_table.c.content_type,
            blacklist_complaint_media_table.c.size,
            blacklist_complaint_media_table.c.uploaded_at,
        )
    ).mappings().one()
    return _blacklist_media_from_row(row)


def _insert_appeal_media(
    session: Session,
    *,
    appeal_id: int,
    filename: str,
    content_type: str,
    data: bytes,
) -> BlacklistMediaOut:
    row = session.execute(
        insert(blacklist_appeal_media_table)
        .values(
            appeal_id=appeal_id,
            filename=filename,
            content_type=content_type,
            content=data,
            size=len(data),
        )
        .returning(
            blacklist_appeal_media_table.c.id,
            blacklist_appeal_media_table.c.filename,
            blacklist_appeal_media_table.c.content_type,
            blacklist_appeal_media_table.c.size,
            blacklist_appeal_media_table.c.uploaded_at,
        )
    ).mappings().one()
    return _blacklist_media_from_row(row)


def _require_complaint_owner(session: Session, complaint_id: int) -> Optional[int]:
    row = session.execute(
        select(
            blacklist_complaints_table.c.id,
            blacklist_complaints_table.c.added_by_id,
        ).where(blacklist_complaints_table.c.id == complaint_id)
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found.",
        )
    return row["added_by_id"]


def _require_appeal_owner(session: Session, appeal_id: int) -> Optional[int]:
    row = session.execute(
        select(
            blacklist_appeals_table.c.id,
            blacklist_appeals_table.c.appeal_by_id,
        ).where(blacklist_appeals_table.c.id == appeal_id)
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appeal not found.",
        )
    return row["appeal_by_id"]


def _fetch_complaint_media_blob(session: Session, complaint_id: int, media_id: int):
    row = session.execute(
        select(
            blacklist_complaint_media_table.c.filename,
            blacklist_complaint_media_table.c.content,
            blacklist_complaint_media_table.c.content_type,
        ).where(
            and_(
                blacklist_complaint_media_table.c.id == media_id,
                blacklist_complaint_media_table.c.complaint_id == complaint_id,
            )
        )
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media not found.",
        )
    return row


def _fetch_appeal_media_blob(session: Session, appeal_id: int, media_id: int):
    row = session.execute(
        select(
            blacklist_appeal_media_table.c.filename,
            blacklist_appeal_media_table.c.content,
            blacklist_appeal_media_table.c.content_type,
        ).where(
            and_(
                blacklist_appeal_media_table.c.id == media_id,
                blacklist_appeal_media_table.c.appeal_id == appeal_id,
            )
        )
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media not found.",
        )
    return row



@app.get(
    "/admin/blacklist",
    response_model=List[BlacklistEntryOut],
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_BLACKLIST_ROLE))],
)
async def admin_list_blacklist(
    session: Session = Depends(db_session_dependency),
) -> List[BlacklistEntryOut]:
    return _list_blacklist_entries(session=session)


@app.get(
    "/admin/blacklist/{blacklist_id}",
    response_model=BlacklistEntryDetail,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_BLACKLIST_ROLE))],
)
async def admin_get_blacklist_entry(
    blacklist_id: int,
    session: Session = Depends(db_session_dependency),
) -> BlacklistEntryDetail:
    entry = _load_blacklist_entry(session, blacklist_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blacklist record not found.",
        )
    complaints_rows = (
        session.execute(
            select(
                blacklist_complaints_table.c.id,
                blacklist_complaints_table.c.blacklist_id,
                blacklist_complaints_table.c.complaint_date,
                blacklist_complaints_table.c.added_by,
                blacklist_complaints_table.c.added_by_phone,
                blacklist_complaints_table.c.added_by_id,
                blacklist_complaints_table.c.reason,
            )
            .where(blacklist_complaints_table.c.blacklist_id == blacklist_id)
            .order_by(blacklist_complaints_table.c.complaint_date.desc())
        )
        .mappings()
        .all()
    )
    appeals_rows = (
        session.execute(
            select(
                blacklist_appeals_table.c.id,
                blacklist_appeals_table.c.blacklist_id,
                blacklist_appeals_table.c.appeal_date,
                blacklist_appeals_table.c.is_appeal,
                blacklist_appeals_table.c.appeal_by,
                blacklist_appeals_table.c.appeal_by_phone,
                blacklist_appeals_table.c.appeal_by_id,
                blacklist_appeals_table.c.reason,
            )
            .where(blacklist_appeals_table.c.blacklist_id == blacklist_id)
            .order_by(blacklist_appeals_table.c.appeal_date.desc())
        )
        .mappings()
        .all()
    )
    complaints_media = _fetch_complaint_media_map(session, [row["id"] for row in complaints_rows])
    appeals_media = _fetch_appeal_media_map(session, [row["id"] for row in appeals_rows])
    complaints = [
        BlacklistComplaintOut(**row, media=complaints_media.get(row["id"], []))
        for row in complaints_rows
    ]
    appeals = [
        BlacklistAppealOut(**row, media=appeals_media.get(row["id"], []))
        for row in appeals_rows
    ]
    payload = entry.dict()
    payload.update(complaints=complaints, appeals=appeals)
    return BlacklistEntryDetail(**payload)


@app.post(
    "/admin/blacklist/{blacklist_id}/status",
    response_model=BlacklistEntryOut,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_BLACKLIST_ROLE))],
)
async def admin_update_blacklist_status(
    blacklist_id: int,
    payload: BlacklistStatusUpdate,
    session: Session = Depends(db_session_dependency),
) -> BlacklistEntryOut:
    updated = session.execute(
        update(blacklist_table)
        .where(blacklist_table.c.id == blacklist_id)
        .values(is_active=payload.is_active)
        .returning(blacklist_table.c.id)
    ).scalar_one_or_none()
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blacklist record not found.",
        )
    entry = _load_blacklist_entry(session, blacklist_id)
    assert entry is not None
    return entry


@app.get(
    "/admin/blacklist/complaints/{complaint_id}/media/{media_id}",
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_BLACKLIST_ROLE))],
)
async def admin_download_complaint_media(
    complaint_id: int,
    media_id: int,
    session: Session = Depends(db_session_dependency),
) -> StreamingResponse:
    row = _fetch_complaint_media_blob(session, complaint_id, media_id)
    filename = _safe_filename(row["filename"] or "media")
    media_type = row["content_type"] or "application/octet-stream"
    content = row["content"] or b""
    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get(
    "/admin/blacklist/appeals/{appeal_id}/media/{media_id}",
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_BLACKLIST_ROLE))],
)
async def admin_download_appeal_media(
    appeal_id: int,
    media_id: int,
    session: Session = Depends(db_session_dependency),
) -> StreamingResponse:
    row = _fetch_appeal_media_blob(session, appeal_id, media_id)
    filename = _safe_filename(row["filename"] or "media")
    media_type = row["content_type"] or "application/octet-stream"
    content = row["content"] or b""
    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get(
    "/blacklist",
    response_model=List[BlacklistEntryOut],
)
async def public_blacklist(
    session: Session = Depends(db_session_dependency),
) -> List[BlacklistEntryOut]:
    return _list_blacklist_entries(session=session, only_active=True)


@app.get(
    "/blacklist/search",
    response_model=List[BlacklistEntryOut],
)
async def public_search_blacklist(
    name: Optional[str] = Query(None, min_length=1),
    birthdate: Optional[date] = Query(None),
    city: Optional[str] = Query(None),
    session: Session = Depends(db_session_dependency),
) -> List[BlacklistEntryOut]:
    filters: List[Any] = []
    if name:
        filters.append(blacklist_table.c.name.ilike(f"%{name.strip()}%"))
    if birthdate:
        filters.append(blacklist_table.c.birthdate == birthdate)
    if city:
        filters.append(blacklist_table.c.city.ilike(f"%{city.strip()}%"))
    return _list_blacklist_entries(session=session, filters=filters, only_active=True)


@app.post(
    "/blacklist/complaints",
    response_model=BlacklistComplaintResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_blacklist_complaint(
    payload: BlacklistComplaintCreate,
    session: Session = Depends(db_session_dependency),
) -> BlacklistComplaintResponse:
    name, phone, birthdate, city = _normalize_blacklist_identity(
        payload.name,
        payload.phone,
        payload.birthdate,
        payload.city,
    )
    entry, created = _get_or_create_blacklist_entry(
        session,
        name=name,
        phone=phone,
        birthdate=birthdate,
        city=city,
    )
    complaint = _insert_blacklist_complaint(
        session,
        blacklist_id=entry.id,
        payload=payload,
    )
    refreshed = _load_blacklist_entry(session, entry.id)
    assert refreshed is not None
    return BlacklistComplaintResponse(
        created_entry=created,
        blacklist=refreshed,
        complaint=complaint,
    )


@app.post(
    "/blacklist/appeals",
    response_model=BlacklistAppealResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_blacklist_appeal(
    payload: BlacklistAppealCreate,
    session: Session = Depends(db_session_dependency),
) -> BlacklistAppealResponse:
    name, phone, birthdate, city = _normalize_blacklist_identity(
        payload.name,
        payload.phone,
        payload.birthdate,
        payload.city,
    )
    entry = _load_blacklist_entry_by_identity(
        session,
        name=name,
        phone=phone,
        birthdate=birthdate,
        city=city,
    )
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blacklist record not found.",
        )
    appeal = _insert_blacklist_appeal(
        session,
        blacklist_id=entry.id,
        payload=payload,
    )
    refreshed = _load_blacklist_entry(session, entry.id)
    assert refreshed is not None
    return BlacklistAppealResponse(blacklist=refreshed, appeal=appeal)


@app.post(
    "/blacklist/complaints/{complaint_id}/media",
    response_model=BlacklistMediaOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_complaint_media(
    complaint_id: int,
    reporter_id: Optional[int] = Form(None),
    file: UploadFile = File(...),
    session: Session = Depends(db_session_dependency),
) -> BlacklistMediaOut:
    owner_id = _require_complaint_owner(session, complaint_id)
    _ensure_reporter_allowed(owner_id, reporter_id)
    data = await file.read()
    _validate_media_upload(file.content_type, len(data))
    filename = _safe_media_filename(file.filename, prefix="complaint")
    return _insert_complaint_media(
        session,
        complaint_id=complaint_id,
        filename=filename,
        content_type=file.content_type or "application/octet-stream",
        data=data,
    )


@app.post(
    "/blacklist/appeals/{appeal_id}/media",
    response_model=BlacklistMediaOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_appeal_media(
    appeal_id: int,
    reporter_id: Optional[int] = Form(None),
    file: UploadFile = File(...),
    session: Session = Depends(db_session_dependency),
) -> BlacklistMediaOut:
    owner_id = _require_appeal_owner(session, appeal_id)
    _ensure_reporter_allowed(owner_id, reporter_id)
    data = await file.read()
    _validate_media_upload(file.content_type, len(data))
    filename = _safe_media_filename(file.filename, prefix="appeal")
    return _insert_appeal_media(
        session,
        appeal_id=appeal_id,
        filename=filename,
        content_type=file.content_type or "application/octet-stream",
        data=data,
    )


def _normalize_code(code: str) -> str:
    return code.strip().lower()


def _ensure_role_assignment(
    session: Session,
    admin_account_id: int,
    role_slugs: Iterable[str],
    current_roles: set[str],
) -> None:
    """Assign roles by slug with owner/superadmin guard."""
    normalized = {slug.strip() for slug in role_slugs if slug}
    if not normalized:
        return
    slug_to_id = dict(
        session.execute(
            select(roles_table.c.slug, roles_table.c.id).where(
                roles_table.c.slug.in_(normalized)
            )
        ).all()
    )
    for slug in normalized:
        if slug not in slug_to_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role '{slug}' not found.",
            )
        if slug in {OWNER_ROLE, SUPERADMIN_ROLE} and OWNER_ROLE not in current_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only owner can assign this role.",
            )
        role_id = slug_to_id[slug]
        exists_pair = session.execute(
            select(admin_account_roles_table.c.admin_account_id).where(
                and_(
                    admin_account_roles_table.c.admin_account_id == admin_account_id,
                    admin_account_roles_table.c.role_id == role_id,
                )
            )
        ).first()
        if not exists_pair:
            session.execute(
                insert(admin_account_roles_table).values(
                    admin_account_id=admin_account_id,
                    role_id=role_id,
                )
            )


def _set_admin_roles(
    session: Session,
    admin_account_id: int,
    role_slugs: Iterable[str],
    current_roles: set[str],
) -> None:
    normalized = {slug.strip() for slug in role_slugs if slug}
    existing_roles = set(_load_admin_roles(session, admin_account_id))
    if OWNER_ROLE not in current_roles:
        if OWNER_ROLE in normalized or SUPERADMIN_ROLE in normalized:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only owner can assign this role.",
            )
        if OWNER_ROLE in existing_roles or SUPERADMIN_ROLE in existing_roles:
            if normalized != existing_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only owner can modify this account.",
                )
    role_map = dict(
        session.execute(
            select(roles_table.c.slug, roles_table.c.id)
        ).all()
    )
    for slug in normalized:
        if slug not in role_map:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role '{slug}' not found.",
            )
    current_ids = {
        role_map[slug] for slug in existing_roles if slug in role_map
    }
    desired_ids = {role_map[slug] for slug in normalized}
    remove_ids = current_ids - desired_ids
    add_ids = desired_ids - current_ids
    if remove_ids:
        session.execute(
            delete(admin_account_roles_table).where(
                and_(
                    admin_account_roles_table.c.admin_account_id == admin_account_id,
                    admin_account_roles_table.c.role_id.in_(remove_ids),
                )
            )
        )
    for role_id in add_ids:
        session.execute(
            insert(admin_account_roles_table).values(
                admin_account_id=admin_account_id,
                role_id=role_id,
            )
        )
def _require_topic(topic: str) -> str:
    normalized = topic.strip()
    if normalized not in ALL_DOCUMENT_TOPIC_LOOKUP:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found.",
        )
    return normalized


def _safe_filename(name: str) -> str:
    sanitized = name.replace('"', '').replace('\r', '').replace('\n', '').strip()
    return sanitized or "document"

def _safe_media_filename(name: Optional[str], *, prefix: str) -> str:
    candidate = (name or "").strip()
    candidate = re.sub(r"[^\w.\-]+", "_", candidate)[:255]
    if not candidate:
        candidate = f"{prefix}_{uuid.uuid4().hex[:8]}"
    return candidate

def _fetch_document_out(session: Session, document_id: int) -> KnowledgeDocumentOut:
    stmt = (
        select(
            knowledge_documents_table.c.id,
            knowledge_documents_table.c.topic,
            knowledge_documents_table.c.filename,
            knowledge_documents_table.c.size,
            knowledge_documents_table.c.uploaded_at,
            languages_table.c.code.label("language_code"),
        )
        .select_from(
            knowledge_documents_table.join(
                languages_table,
                knowledge_documents_table.c.language_id == languages_table.c.id,
            )
        )
        .where(knowledge_documents_table.c.id == document_id)
    )
    row = session.execute(stmt).mappings().one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    return KnowledgeDocumentOut(**row)
@app.post(
    "/admin/languages",
    response_model=LanguageOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_LANG_ROLE))],
)
async def create_language(
    payload: LanguageCreate,
    session: Session = Depends(db_session_dependency),
) -> LanguageOut:
    code = _normalize_code(payload.code)
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Language code cannot be empty.",
        )
    exists_stmt = select(languages_table.c.id).where(languages_table.c.code == code)
    if session.execute(exists_stmt).scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Language already exists.",
        )
    if payload.is_default:
        session.execute(update(languages_table).values(is_default=False))
    inserted = session.execute(
        insert(languages_table)
        .values(code=code, is_default=payload.is_default)
        .returning(
            languages_table.c.id,
            languages_table.c.code,
            languages_table.c.is_default,
        )
    ).mappings().one()
    # Seed translations for this language using defaults or AI translator when available
    lang_id = inserted["id"]
    default_code = settings.default_language or "en"
    default_texts = DEFAULT_TRANSLATIONS.get(default_code, {})
    # Load RU translations map for emoji/placeholders
    ru_id = session.execute(
        select(languages_table.c.id).where(languages_table.c.code == "ru")
    ).scalar_one_or_none()
    ru_map: Dict[str, Optional[str]] = {}
    if ru_id is not None:
        ru_rows = session.execute(
            select(
                translation_keys_table.c.identifier,
                translations_table.c.value,
            )
            .select_from(
                translations_table.join(
                    translation_keys_table,
                    translations_table.c.key_id == translation_keys_table.c.id,
                )
            )
            .where(translations_table.c.language_id == ru_id)
        ).mappings().all()
        ru_map = {row["identifier"]: row["value"] for row in ru_rows}
    for identifier in DEFAULT_TRANSLATION_KEYS:
        key_id = session.execute(
            select(translation_keys_table.c.id).where(
                translation_keys_table.c.identifier == identifier
            )
        ).scalar_one_or_none()
        if key_id is None:
            key_id = session.execute(
                insert(translation_keys_table)
                .values(identifier=identifier)
                .returning(translation_keys_table.c.id)
            ).scalar_one()
        exists = session.execute(
            select(translations_table.c.id).where(
                and_(
                    translations_table.c.language_id == lang_id,
                    translations_table.c.key_id == key_id,
                )
            )
        ).scalar_one_or_none()
        if exists is None:
            # Choose base text: RU->default->humanized
            base_text = ru_map.get(identifier) or default_texts.get(identifier) or identifier.replace('.', ' ').replace('_', ' ').title()
            value = str(base_text)
            # Prefer AI translator if configured and language is not RU/DEV
            if _ai_translator is not None and code not in ("ru", "dev"):
                icon = _extract_icon_prefix(value)
                placeholders = list(_PLACEHOLDER_RE.findall(value))
                try:
                    translated = _ai_translator.translate(text=value, target_lang=code, placeholders=placeholders, emoji_prefix=icon)
                    if icon and translated and not _extract_icon_prefix(translated):
                        translated = f"{icon} {translated}"
                    value = _ensure_placeholders(value, translated)
                except Exception:
                    # fallback keep value
                    pass
            session.execute(
                insert(translations_table).values(
                    language_id=lang_id,
                    key_id=key_id,
                    value=value,
                )
            )
    return LanguageOut(**inserted)
@app.delete(
    "/admin/languages/{code}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_LANG_ROLE))],
)
async def delete_language(
    code: str,
    session: Session = Depends(db_session_dependency),
) -> None:
    normalized = _normalize_code(code)
    language = session.execute(
        select(
            languages_table.c.id,
            languages_table.c.is_default,
        ).where(languages_table.c.code == normalized)
    ).mappings().one_or_none()
    if language is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Language not found.",
        )
    if language["is_default"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Default language cannot be removed.",
        )
    session.execute(
        delete(translations_table).where(translations_table.c.language_id == language["id"])
    )
    session.execute(
        delete(languages_table).where(languages_table.c.id == language["id"])
    )
@app.get(
    "/admin/translations",
    response_model=List[TranslationRow],
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_LANG_ROLE))],
)
async def list_translations(
    language: str = Query(..., description="Language code"),
    session: Session = Depends(db_session_dependency),
) -> List[TranslationRow]:
    normalized = _normalize_code(language)
    if normalized == "dev":
        rows = session.execute(
            select(translation_keys_table.c.identifier).order_by(translation_keys_table.c.identifier)
        ).mappings().all()
        return [TranslationRow(identifier=row["identifier"], value=row["identifier"]) for row in rows]
    language_row = session.execute(
        select(languages_table.c.id).where(languages_table.c.code == normalized)
    ).scalar_one_or_none()
    if language_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Language not found.",
        )
    stmt = (
        select(
            translation_keys_table.c.identifier,
            translations_table.c.value,
        )
        .select_from(
            translation_keys_table.outerjoin(
                translations_table,
                and_(
                    translations_table.c.key_id == translation_keys_table.c.id,
                    translations_table.c.language_id == language_row,
                ),
            )
        )
        .order_by(translation_keys_table.c.identifier)
    )
    rows = session.execute(stmt).mappings().all()
    translation_map = {
        row["identifier"]: row["value"]
        for row in rows
    }
    identifiers = sorted(
        set(DEFAULT_TRANSLATION_KEYS).union(translation_map.keys())
    )
    return [
        TranslationRow(identifier=identifier, value=translation_map.get(identifier))
        for identifier in identifiers
    ]


class TranslationAIRequest(BaseModel):
    language: str
    identifier: str


async def _parse_translation_ai_request(
    request: Request,
    payload: Any = Body(default=None),
) -> TranslationAIRequest:
    data: Any = payload
    if data is None:
        try:
            data = await request.json()
        except Exception:
            data = {}
    if isinstance(data, dict) and isinstance(data.get("payload"), dict):
        data = data["payload"]
    if isinstance(data, list):
        if data and isinstance(data[0], dict):
            data = data[0]
        else:
            data = {}
    try:
        return TranslationAIRequest.model_validate(data or {})
    except Exception as exc:
        from pydantic import ValidationError

        if isinstance(exc, ValidationError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.errors(),
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@app.post(
    "/admin/translations/ai",
    response_model=TranslationRow,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_LANG_ROLE))],
)
async def ai_translate(
    payload: TranslationAIRequest = Depends(_parse_translation_ai_request),
    session: Session = Depends(db_session_dependency),
) -> TranslationRow:
    if _ai_translator is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI translator is not configured")
    language_code = _normalize_code(payload.language)
    if language_code == "dev":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="DEV language is not translatable")
    identifier = (payload.identifier or "").strip()
    if not identifier:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Identifier cannot be empty")

    # Resolve language id
    language_row = session.execute(
        select(languages_table.c.id).where(languages_table.c.code == language_code)
    ).scalar_one_or_none()
    if language_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Language not found")

    # Ensure key exists
    key_row = session.execute(
        select(translation_keys_table.c.id).where(
            translation_keys_table.c.identifier == identifier
        )
    ).scalar_one_or_none()
    if key_row is None:
        key_row = session.execute(
            insert(translation_keys_table)
            .values(identifier=identifier)
            .returning(translation_keys_table.c.id)
        ).scalar_one()

    # Base text to translate: prefer RU from DB, else default language, else humanized
    ru_id = session.execute(
        select(languages_table.c.id).where(languages_table.c.code == "ru")
    ).scalar_one_or_none()
    base_text = None
    if ru_id is not None:
        base_text = session.execute(
            select(translations_table.c.value).where(
                and_(translations_table.c.language_id == ru_id, translations_table.c.key_id == key_row)
            )
        ).scalar_one_or_none()
    if not base_text:
        default_code = settings.default_language or "en"
        base_text = (DEFAULT_TRANSLATIONS.get(default_code, {}) or {}).get(identifier)
    if not base_text:
        base_text = identifier.replace('.', ' ').replace('_', ' ').title()

    icon = _extract_icon_prefix(str(base_text))
    placeholders = list(_PLACEHOLDER_RE.findall(str(base_text)))
    translated = await asyncio.to_thread(_ai_translator.translate, text=str(base_text), target_lang=language_code, placeholders=placeholders, emoji_prefix=icon)
    if icon and translated and not _extract_icon_prefix(translated):
        translated = f"{icon} {translated}"
    translated = _ensure_placeholders(str(base_text), translated)

    # Upsert translation
    existing_tr = session.execute(
        select(translations_table.c.id).where(
            and_(translations_table.c.language_id == language_row, translations_table.c.key_id == key_row)
        )
    ).scalar_one_or_none()
    if existing_tr is None:
        session.execute(
            insert(translations_table).values(language_id=language_row, key_id=key_row, value=translated)
        )
    else:
        session.execute(
            update(translations_table).where(translations_table.c.id == existing_tr).values(value=translated)
        )
    return TranslationRow(identifier=identifier, value=translated)
@app.put(
    "/admin/translations",
    response_model=TranslationRow,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_LANG_ROLE))],
)
async def update_translation(
    payload: TranslationUpdate = Depends(_parse_translation_update),
    session: Session = Depends(db_session_dependency),
) -> TranslationRow:
    language_code = _normalize_code(payload.language)
    identifier = payload.identifier.strip()
    if not identifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Identifier cannot be empty.",
        )
    language_row = session.execute(
        select(languages_table.c.id).where(languages_table.c.code == language_code)
    ).scalar_one_or_none()
    if language_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Language not found.",
        )
    key_row = session.execute(
        select(translation_keys_table.c.id).where(
            translation_keys_table.c.identifier == identifier
        )
    ).scalar_one_or_none()
    if key_row is None:
        key_row = session.execute(
            insert(translation_keys_table)
            .values(identifier=identifier)
            .returning(translation_keys_table.c.id)
        ).scalar_one()
    translation_row = session.execute(
        select(translations_table.c.id).where(
            and_(
                translations_table.c.language_id == language_row,
                translations_table.c.key_id == key_row,
            )
        )
    ).scalar_one_or_none()
    sanitized_value = payload.value if payload.value is not None else ""
    if translation_row is None:
        session.execute(
            insert(translations_table).values(
                language_id=language_row,
                key_id=key_row,
                value=sanitized_value,
            )
        )
    else:
        session.execute(
            update(translations_table)
            .where(
                translations_table.c.id == translation_row,
            )
            .values(value=sanitized_value)
        )
    return TranslationRow(identifier=identifier, value=sanitized_value or None)



@app.get(
    "/admin/link-settings",
    response_model=LinkSettingsResponse,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_LINKS_ROLE))],
)
async def get_link_settings(
    session: Session = Depends(db_session_dependency),
) -> LinkSettingsResponse:
    language_rows = session.execute(
        select(
            languages_table.c.code,
            languages_table.c.is_default,
        ).order_by(languages_table.c.code)
    ).mappings().all()
    if not language_rows:
        return LinkSettingsResponse(languages=[], slots=[], links={})

    default_language_code = next(
        (row["code"] for row in language_rows if row["is_default"]),
        language_rows[0]["code"],
    )

    languages = [
        LinkLanguageOut(
            code=row["code"],
            label=LANGUAGE_LABELS.get(row["code"], row["code"].upper()),
        )
        for row in language_rows
    ]
    codes = [row["code"] for row in language_rows]
    channel_rows = session.execute(
        select(channels_table.c.kind, channels_table.c.lang, channels_table.c.url).where(
            channels_table.c.kind.in_(LINK_SLOT_SLUGS)
        )
    ).mappings().all()
    current_links = {
        (row["kind"], row["lang"]): row["url"]
        for row in channel_rows
    }

    links: Dict[str, Dict[str, Optional[str]]] = {}
    for slot in LINK_SLOTS:
        slug = slot["slug"]
        defaults = DEFAULT_LINKS.get(slug, {})
        per_language: Dict[str, Optional[str]] = {}
        for code in codes:
            value = current_links.get((slug, code))
            if value is None:
                value = defaults.get(code) or defaults.get(default_language_code)
            per_language[code] = value if value else None
        links[slug] = per_language

    slots = [
        LinkSlotOut(slug=slot["slug"], titles=slot["titles"])
        for slot in LINK_SLOTS
    ]
    return LinkSettingsResponse(languages=languages, slots=slots, links=links)


@app.put(
    "/admin/link-settings/{slug}",
    response_model=LinkSlotResolveResponse,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_LINKS_ROLE))],
)
async def update_link_setting(
    slug: str,
    payload: LinkSlotUpdate,
    session: Session = Depends(db_session_dependency),
) -> LinkSlotResolveResponse:
    normalized_slug = slug.strip()
    if normalized_slug not in LINK_SLOT_SLUGS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link slot not found.",
        )

    language_code = _normalize_code(payload.language)
    language_row = session.execute(
        select(
            languages_table.c.code,
            languages_table.c.is_default,
        ).where(languages_table.c.code == language_code)
    ).mappings().one_or_none()
    if language_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Language not found.",
        )

    cleaned_url = (payload.url or "").strip()
    if cleaned_url and not cleaned_url.startswith(("http://", "https://", "tg://")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL must start with http://, https://, or tg://.",
        )

    existing_row_id = session.execute(
        select(channels_table.c.id).where(
            and_(
                channels_table.c.kind == normalized_slug,
                channels_table.c.lang == language_code,
            )
        )
    ).scalar_one_or_none()

    if cleaned_url:
        if existing_row_id is None:
            session.execute(
                insert(channels_table).values(
                    kind=normalized_slug,
                    lang=language_code,
                    url=cleaned_url,
                )
            )
        else:
            session.execute(
                update(channels_table)
                .where(channels_table.c.id == existing_row_id)
                .values(url=cleaned_url)
            )
    elif existing_row_id is not None:
        session.execute(
            delete(channels_table).where(channels_table.c.id == existing_row_id)
        )

    language_rows = session.execute(
        select(
            languages_table.c.code,
            languages_table.c.is_default,
        ).order_by(languages_table.c.code)
    ).mappings().all()
    if not language_rows:
        return LinkSlotResolveResponse(slug=normalized_slug, links={})

    default_language_code = next(
        (row["code"] for row in language_rows if row["is_default"]),
        language_rows[0]["code"],
    )
    codes = [row["code"] for row in language_rows]

    rows = session.execute(
        select(channels_table.c.lang, channels_table.c.url).where(
            and_(
                channels_table.c.kind == normalized_slug,
                channels_table.c.lang.in_(codes),
            )
        )
    ).mappings().all()
    current = {row["lang"]: row["url"] for row in rows}
    defaults = DEFAULT_LINKS.get(normalized_slug, {})

    resolved: Dict[str, Optional[str]] = {}
    for code in codes:
        value = current.get(code)
        if value is None:
            value = defaults.get(code) or defaults.get(default_language_code)
        resolved[code] = value if value else None

    return LinkSlotResolveResponse(slug=normalized_slug, links=resolved)


@app.get(
    "/admin/document-tree",
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_DOCS_ROLE, ADMIN_TEMPLATES_ROLE))],
)
async def get_document_tree() -> Dict[str, List[dict]]:
    return {"categories": DOCUMENT_TREE}


@app.get(
    "/admin/contract-templates/tree",
    response_model=Dict[str, List[ContractTemplateCategoryOut]],
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_TEMPLATES_ROLE))],
)
async def get_contract_template_tree() -> Dict[str, List[ContractTemplateCategoryOut]]:
    return {"categories": CONTRACT_TEMPLATES_TREE}


@app.get(
    "/admin/documents",
    response_model=List[KnowledgeDocumentOut],
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_DOCS_ROLE))],
)
async def list_documents(
    topic: str = Query(..., description="Document topic identifier"),
    session: Session = Depends(db_session_dependency),
) -> List[KnowledgeDocumentOut]:
    normalized_topic = _require_topic(topic)

    stmt = (
        select(
            knowledge_documents_table.c.id,
            knowledge_documents_table.c.topic,
            knowledge_documents_table.c.filename,
            knowledge_documents_table.c.size,
            knowledge_documents_table.c.uploaded_at,
            languages_table.c.code.label("language_code"),
        )
        .select_from(
            knowledge_documents_table.join(
                languages_table,
                knowledge_documents_table.c.language_id == languages_table.c.id,
            )
        )
        .where(knowledge_documents_table.c.topic == normalized_topic)
        .order_by(knowledge_documents_table.c.uploaded_at.desc())
    )
    rows = session.execute(stmt).mappings().all()
    return [KnowledgeDocumentOut(**row) for row in rows]


@app.post(
    "/admin/documents",
    response_model=KnowledgeDocumentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_DOCS_ROLE))],
)
async def upload_document(
    topic: str = Form(...),
    language: str = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(db_session_dependency),
) -> KnowledgeDocumentOut:
    normalized_topic = _require_topic(topic)
    language_code = _normalize_code(language)

    language_row = session.execute(
        select(languages_table.c.id, languages_table.c.code).where(
            languages_table.c.code == language_code
        )
    ).mappings().one_or_none()
    if language_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Language not found.",
        )

    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    now = datetime.now(timezone.utc)
    inserted_id = session.execute(
        insert(knowledge_documents_table)
        .values(
            topic=normalized_topic,
            language_id=language_row["id"],
            filename=file.filename or "document",
            content_type=file.content_type or "application/octet-stream",
            content=data,
            size=len(data),
            uploaded_at=now,
            updated_at=now,
        )
        .returning(knowledge_documents_table.c.id)
    ).scalar_one()

    return _fetch_document_out(session, inserted_id)


@app.put(
    "/admin/documents/{document_id}",
    response_model=KnowledgeDocumentOut,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_DOCS_ROLE))],
)
async def update_document(
    document_id: int,
    topic: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    session: Session = Depends(db_session_dependency),
) -> KnowledgeDocumentOut:
    existing = session.execute(
        select(
            knowledge_documents_table.c.id,
            knowledge_documents_table.c.topic,
            knowledge_documents_table.c.language_id,
        ).where(knowledge_documents_table.c.id == document_id)
    ).mappings().one_or_none()

    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    updates: Dict[str, object] = {}

    if topic is not None:
        updates["topic"] = _require_topic(topic)

    if language is not None:
        language_code = _normalize_code(language)
        language_id = session.execute(
            select(languages_table.c.id).where(languages_table.c.code == language_code)
        ).scalar_one_or_none()
        if language_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Language not found.",
            )
        updates["language_id"] = language_id

    if file is not None:
        data = await file.read()
        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )
        updates["filename"] = file.filename or "document"
        updates["content_type"] = file.content_type or "application/octet-stream"
        updates["content"] = data
        updates["size"] = len(data)

    if updates:
        updates["updated_at"] = datetime.now(timezone.utc)
        session.execute(
            update(knowledge_documents_table)
            .where(knowledge_documents_table.c.id == document_id)
            .values(**updates)
        )

    return _fetch_document_out(session, document_id)


@app.delete(
    "/admin/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_DOCS_ROLE))],
)
async def delete_document(
    document_id: int,
    session: Session = Depends(db_session_dependency),
) -> None:
    result = session.execute(
        delete(knowledge_documents_table).where(knowledge_documents_table.c.id == document_id)
    )
    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )


@app.get(
    "/admin/documents/{document_id}/download",
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_DOCS_ROLE))],
)
async def download_document(
    document_id: int,
    session: Session = Depends(db_session_dependency),
) -> StreamingResponse:
    row = session.execute(
        select(
            knowledge_documents_table.c.filename,
            knowledge_documents_table.c.content,
            knowledge_documents_table.c.content_type,
        ).where(knowledge_documents_table.c.id == document_id)
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    filename = _safe_filename(row["filename"] or "document")
    media_type = row["content_type"] or "application/octet-stream"
    content = row["content"] or b""

    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


# Admin translations maintenance
class TranslationsRepairRequest(BaseModel):
    targets_for_icons: Optional[List[str]] = ["ar", "tr", "en"]
    use_ru_for_missing: bool = True
    ensure_placeholders: bool = True
    use_ai: bool = True


class TranslationsRepairResponse(BaseModel):
    updated: int
    examined: int
    per_language_updated: Dict[str, int]


@app.post(
    "/admin/translations/repair",
    response_model=TranslationsRepairResponse,
    dependencies=[Depends(require_roles(OWNER_ROLE, SUPERADMIN_ROLE, ADMIN_LANG_ROLE))],
)
async def repair_translations(
    payload: TranslationsRepairRequest,
    session: Session = Depends(db_session_dependency),
) -> TranslationsRepairResponse:
    updated, examined, per_lang = _repair_translations_internal(
        session=session,
        targets_for_icons=payload.targets_for_icons,
        use_ru_for_missing=payload.use_ru_for_missing,
        ensure_placeholders=payload.ensure_placeholders,
        translator=(_ai_translator if payload.use_ai else None),
        prefer_ai=payload.use_ai,
    )
    return TranslationsRepairResponse(
        updated=updated, examined=examined, per_language_updated=per_lang
    )





















