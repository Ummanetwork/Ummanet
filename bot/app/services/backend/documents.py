from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable, Optional

import aiohttp

logger = logging.getLogger(__name__)


class BackendRequestError(RuntimeError):
    """Raised when the backend returns an error status."""

    def __init__(self, status: int, message: str, body: Optional[str] = None) -> None:
        super().__init__(message)
        self.status = status
        self.body = body or message


def _parse_iso_date(value: Any) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except Exception:
        return None


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


@dataclass(slots=True)
class BackendDocumentInfo:
    """Represents document metadata returned by the backend."""

    id: int
    filename: str
    language_code: str
    size: int


@dataclass(slots=True)
class BackendBlacklistEntry:
    id: int
    name: str
    phone: Optional[str]
    birthdate: Optional[date]
    city: Optional[str]
    is_active: bool
    date_added: datetime
    complaints_count: int
    appeals_count: int

    @classmethod
    def from_payload(cls, data: dict[str, Any]) -> "BackendBlacklistEntry":
        phone_value = data.get("phone")
        city_value = data.get("city")
        return cls(
            id=int(data["id"]),
            name=str(data.get("name") or ""),
            phone=str(phone_value) if phone_value else None,
            birthdate=_parse_iso_date(data.get("birthdate")),
            city=str(city_value) if city_value else None,
            is_active=bool(data.get("is_active", False)),
            date_added=_parse_iso_datetime(data.get("date_added")) or datetime.fromtimestamp(0),
            complaints_count=int(data.get("complaints_count") or 0),
            appeals_count=int(data.get("appeals_count") or 0),
        )


@dataclass(slots=True)
class BackendBlacklistMedia:
    id: int
    filename: str
    content_type: Optional[str]
    size: int
    uploaded_at: datetime

    @classmethod
    def from_payload(cls, data: dict[str, Any]) -> "BackendBlacklistMedia":
        return cls(
            id=int(data["id"]),
            filename=str(data.get("filename") or ""),
            content_type=str(data.get("content_type") or "") or None,
            size=int(data.get("size") or 0),
            uploaded_at=_parse_iso_datetime(data.get("uploaded_at")) or datetime.fromtimestamp(0),
        )


@dataclass(slots=True)
class BackendBlacklistComplaint:
    id: int
    blacklist_id: int
    complaint_date: datetime
    added_by: str
    added_by_phone: Optional[str]
    added_by_id: Optional[int]
    reason: str
    media: list[BackendBlacklistMedia]

    @classmethod
    def from_payload(cls, data: dict[str, Any]) -> "BackendBlacklistComplaint":
        phone_value = data.get("added_by_phone")
        added_by_id = data.get("added_by_id")
        media_items: list[BackendBlacklistMedia] = []
        for item in data.get("media") or []:
            try:
                media_items.append(BackendBlacklistMedia.from_payload(item))
            except Exception:
                logger.exception("Failed to parse blacklist complaint media payload.")
        return cls(
            id=int(data["id"]),
            blacklist_id=int(data["blacklist_id"]),
            complaint_date=_parse_iso_datetime(data.get("complaint_date")) or datetime.fromtimestamp(0),
            added_by=str(data.get("added_by") or ""),
            added_by_phone=str(phone_value) if phone_value else None,
            added_by_id=int(added_by_id) if added_by_id is not None else None,
            reason=str(data.get("reason") or ""),
            media=media_items,
        )


@dataclass(slots=True)
class BackendBlacklistAppeal:
    id: int
    blacklist_id: int
    appeal_date: datetime
    is_appeal: bool
    appeal_by: str
    appeal_by_phone: Optional[str]
    appeal_by_id: Optional[int]
    reason: str
    media: list[BackendBlacklistMedia]

    @classmethod
    def from_payload(cls, data: dict[str, Any]) -> "BackendBlacklistAppeal":
        appeal_by_phone = data.get("appeal_by_phone")
        appeal_by_id = data.get("appeal_by_id")
        media_items: list[BackendBlacklistMedia] = []
        for item in data.get("media") or []:
            try:
                media_items.append(BackendBlacklistMedia.from_payload(item))
            except Exception:
                logger.exception("Failed to parse blacklist appeal media payload.")
        return cls(
            id=int(data["id"]),
            blacklist_id=int(data["blacklist_id"]),
            appeal_date=_parse_iso_datetime(data.get("appeal_date")) or datetime.fromtimestamp(0),
            is_appeal=bool(data.get("is_appeal", True)),
            appeal_by=str(data.get("appeal_by") or ""),
            appeal_by_phone=str(appeal_by_phone) if appeal_by_phone else None,
            appeal_by_id=int(appeal_by_id) if appeal_by_id is not None else None,
            reason=str(data.get("reason") or ""),
            media=media_items,
        )


@dataclass(slots=True)
class BackendBlacklistComplaintResponse:
    created_entry: bool
    blacklist: BackendBlacklistEntry
    complaint: BackendBlacklistComplaint

    @classmethod
    def from_payload(cls, data: dict[str, Any]) -> "BackendBlacklistComplaintResponse":
        blacklist_raw = data.get("blacklist")
        complaint_raw = data.get("complaint")
        if not isinstance(blacklist_raw, dict) or not isinstance(complaint_raw, dict):
            raise ValueError("Invalid blacklist complaint response payload")
        return cls(
            created_entry=bool(data.get("created_entry", False)),
            blacklist=BackendBlacklistEntry.from_payload(blacklist_raw),
            complaint=BackendBlacklistComplaint.from_payload(complaint_raw),
        )


@dataclass(slots=True)
class BackendBlacklistAppealResponse:
    blacklist: BackendBlacklistEntry
    appeal: BackendBlacklistAppeal

    @classmethod
    def from_payload(cls, data: dict[str, Any]) -> "BackendBlacklistAppealResponse":
        blacklist_raw = data.get("blacklist")
        appeal_raw = data.get("appeal")
        if not isinstance(blacklist_raw, dict) or not isinstance(appeal_raw, dict):
            raise ValueError("Invalid blacklist appeal response payload")
        return cls(
            blacklist=BackendBlacklistEntry.from_payload(blacklist_raw),
            appeal=BackendBlacklistAppeal.from_payload(appeal_raw),
        )


class BackendDocumentsClient:
    """Helper for interacting with the backend administrative API."""

    _TOKEN_TTL_SECONDS = 45 * 60  # refresh token every 45 minutes

    def __init__(
        self,
        *,
        base_url: str,
        service_api_key: str,
        request_timeout: float = 15.0,
    ) -> None:
        if not base_url:
            raise ValueError("Backend base URL is required")
        if not (service_api_key or "").strip():
            raise ValueError("Backend service_api_key is required")

        normalized_url = base_url.rstrip("/")
        self._base_url = normalized_url
        self._service_api_key = service_api_key.strip()
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=request_timeout)
        )
        self._token: Optional[str] = None
        self._token_expire_at: float = 0.0
        self._token_lock = asyncio.Lock()

    async def close(self) -> None:
        await self._session.close()

    async def list_documents(self, topic: str) -> list[BackendDocumentInfo]:
        response = await self._request(
            "GET",
            "/admin/documents",
            params={"topic": topic},
        )
        payload = await response.json()
        response.release()
        documents: list[BackendDocumentInfo] = []
        for item in payload:
            try:
                documents.append(
                    BackendDocumentInfo(
                        id=int(item["id"]),
                        filename=str(item.get("filename") or ""),
                        language_code=str(item.get("language_code") or "").lower(),
                        size=int(item.get("size") or 0),
                    )
                )
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Failed to parse backend document: %s", exc)
        return documents

    async def download_document(self, document_id: int) -> tuple[bytes, str, str]:
        response = await self._request(
            "GET",
            f"/admin/documents/{document_id}/download",
        )
        content = await response.read()
        response.release()
        filename_header = response.headers.get("Content-Disposition", "")
        if "filename=" in filename_header:
            filename = filename_header.split("filename=", 1)[1].strip().strip('"')
        else:
            filename = f"document_{document_id}.pdf"
        content_type = response.headers.get("Content-Type", "application/octet-stream")
        return content, filename, content_type

    async def fetch_public_blacklist(self) -> list[BackendBlacklistEntry]:
        response = await self._request("GET", "/blacklist", auth=False)
        payload = await response.json()
        response.release()
        entries: list[BackendBlacklistEntry] = []
        for item in payload:
            try:
                entries.append(BackendBlacklistEntry.from_payload(item))
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Failed to parse blacklist entry: %s", exc)
        return entries

    async def search_public_blacklist(
        self,
        *,
        name: Optional[str] = None,
        birthdate: Optional[date] = None,
        city: Optional[str] = None,
    ) -> list[BackendBlacklistEntry]:
        params: dict[str, str] = {}
        if name:
            params["name"] = name
        if birthdate:
            params["birthdate"] = birthdate.isoformat()
        if city:
            params["city"] = city
        response = await self._request(
            "GET",
            "/blacklist/search",
            params=params or None,
            auth=False,
        )
        payload = await response.json()
        response.release()
        entries: list[BackendBlacklistEntry] = []
        for item in payload:
            try:
                entries.append(BackendBlacklistEntry.from_payload(item))
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Failed to parse blacklist search entry: %s", exc)
        return entries

    async def submit_blacklist_complaint(
        self,
        *,
        name: str,
        phone: Optional[str] = None,
        birthdate: Optional[date] = None,
        city: Optional[str] = None,
        reason: str,
        added_by: str,
        added_by_phone: Optional[str] = None,
        added_by_id: Optional[int] = None,
    ) -> BackendBlacklistComplaintResponse:
        payload: dict[str, Any] = {
            "name": name,
            "phone": phone,
            "birthdate": birthdate.isoformat() if birthdate else None,
            "city": city,
            "reason": reason,
            "added_by": added_by,
            "added_by_phone": added_by_phone,
            "added_by_id": added_by_id,
        }
        response = await self._request(
            "POST",
            "/blacklist/complaints",
            json=payload,
            auth=False,
        )
        data = await response.json()
        response.release()
        return BackendBlacklistComplaintResponse.from_payload(data)

    async def submit_blacklist_appeal(
        self,
        *,
        name: str,
        phone: Optional[str] = None,
        birthdate: Optional[date] = None,
        city: Optional[str] = None,
        reason: str,
        appeal_by: str,
        appeal_by_phone: Optional[str] = None,
        appeal_by_id: Optional[int] = None,
    ) -> BackendBlacklistAppealResponse:
        payload: dict[str, Any] = {
            "name": name,
            "phone": phone,
            "birthdate": birthdate.isoformat() if birthdate else None,
            "city": city,
            "reason": reason,
            "appeal_by": appeal_by,
            "appeal_by_phone": appeal_by_phone,
            "appeal_by_id": appeal_by_id,
        }
        response = await self._request(
            "POST",
            "/blacklist/appeals",
            json=payload,
            auth=False,
        )
        data = await response.json()
        response.release()
        return BackendBlacklistAppealResponse.from_payload(data)

    async def upload_complaint_media(
        self,
        *,
        complaint_id: int,
        reporter_id: Optional[int],
        filename: str,
        content_type: str,
        data: bytes,
    ) -> BackendBlacklistMedia:
        form = aiohttp.FormData()
        form.add_field(
            "file",
            data,
            filename=filename,
            content_type=content_type or "application/octet-stream",
        )
        if reporter_id is not None:
            form.add_field("reporter_id", str(reporter_id))
        response = await self._request(
            "POST",
            f"/blacklist/complaints/{complaint_id}/media",
            data=form,
            auth=False,
        )
        payload = await response.json()
        response.release()
        return BackendBlacklistMedia.from_payload(payload)

    async def upload_appeal_media(
        self,
        *,
        appeal_id: int,
        reporter_id: Optional[int],
        filename: str,
        content_type: str,
        data: bytes,
    ) -> BackendBlacklistMedia:
        form = aiohttp.FormData()
        form.add_field(
            "file",
            data,
            filename=filename,
            content_type=content_type or "application/octet-stream",
        )
        if reporter_id is not None:
            form.add_field("reporter_id", str(reporter_id))
        response = await self._request(
            "POST",
            f"/blacklist/appeals/{appeal_id}/media",
            data=form,
            auth=False,
        )
        payload = await response.json()
        response.release()
        return BackendBlacklistMedia.from_payload(payload)

    async def create_user(
        self,
        *,
        telegram_user_id: int,
        full_name: Optional[str] = None,
        email: Optional[str] = None,
        phone_number: Optional[str] = None,
        language_code: Optional[str] = None,
        role: Optional[str] = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "telegram_user_id": int(telegram_user_id),
            "full_name": full_name,
            "email": email,
            "phone_number": phone_number,
            "language_code": (language_code or "").lower() or None,
            "role": role,
        }
        response = await self._request("POST", "/admin/users", json=payload)
        data = await response.json()
        response.release()
        return data

    async def _ensure_token(self, *, force: bool = False) -> str:
        if force:
            await self._refresh_token()
            return self._token or ""

        if self._token and time.monotonic() < self._token_expire_at:
            return self._token

        async with self._token_lock:
            if self._token and time.monotonic() < self._token_expire_at:
                return self._token
            await self._refresh_token()
            if not self._token:
                raise RuntimeError("Failed to acquire backend access token")
            return self._token

    async def _refresh_token(self) -> None:
        logger.debug("Refreshing backend admin token")
        endpoint = f"{self._base_url}/auth/service-login"
        payload: dict[str, Any] = {"api_key": self._service_api_key, "service": "bot"}
        async with self._session.post(endpoint, json=payload) as response:
            if response.status >= 400:
                text = await response.text()
                raise BackendRequestError(
                    response.status,
                    f"Backend authentication failed with {response.status}: {text}",
                    text,
                )
            data = await response.json()
        token = data.get("access_token")
        if not token:
            raise RuntimeError("Backend authentication response missing access token")
        self._token = token
        self._token_expire_at = time.monotonic() + self._TOKEN_TTL_SECONDS

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        data: Any = None,
        auth: bool = True,
    ) -> aiohttp.ClientResponse:
        url = f"{self._base_url}{path}"
        headers: dict[str, str] = {}
        if auth:
            token = await self._ensure_token()
            headers["Authorization"] = f"Bearer {token}"
        response = await self._session.request(
            method,
            url,
            params=params,
            headers=headers or None,
            json=json,
            data=data,
        )
        if response.status == 401 and auth:
            response.release()
            token = await self._ensure_token(force=True)
            headers["Authorization"] = f"Bearer {token}"
            response = await self._session.request(
                method,
                url,
                params=params,
                headers=headers,
                json=json,
                data=data,
            )
        if response.status >= 400:
            text = await response.text()
            response.release()
            raise BackendRequestError(
                response.status,
                f"Backend request {method} {url} failed with {response.status}: {text}",
                text,
            )
        return response

    @staticmethod
    def select_document(
        documents: Iterable[BackendDocumentInfo],
        *,
        preferred_language: str,
        fallback_language: Optional[str] = None,
    ) -> Optional[BackendDocumentInfo]:
        normalized_pref = (preferred_language or "").lower()
        normalized_fallback = (fallback_language or "").lower() if fallback_language else None

        for doc in documents:
            if doc.language_code == normalized_pref:
                return doc
        if normalized_fallback:
            for doc in documents:
                if doc.language_code == normalized_fallback:
                    return doc
        return next(iter(documents), None)
