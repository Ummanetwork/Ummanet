from __future__ import annotations

import logging
from datetime import date
from typing import Any, Iterable, Optional

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.states.comitee import (
    BlacklistAppealFlow,
    BlacklistComplaintFlow,
    BlacklistSearchFlow,
)
from app.infrastructure.database.models.user import UserModel
from app.services.backend import BackendBlacklistEntry, BackendRequestError
from app.services.i18n.localization import get_text

from .comitee_common import get_backend_client, is_cancel_command, user_language

logger = logging.getLogger(__name__)

router = Router(name="comitee.blacklist")

BLACKLIST_MEDIA_DONE_COMMANDS = {"done", "готово", "готов", "готова", "skip", "пропустить"}
BLACKLIST_MEDIA_MAX_ITEMS = 5
BLACKLIST_MEDIA_MAX_BYTES = 20 * 1024 * 1024
BLACKLIST_MEDIA_ALLOWED_PREFIXES = ("image/", "video/")


def _is_media_done_command(text: Optional[str]) -> bool:
    normalized = (text or "").strip().lower()
    return normalized in BLACKLIST_MEDIA_DONE_COMMANDS


def _optional_input_value(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    cleaned = text.strip()
    if not cleaned:
        return None
    if cleaned.lower() in {"-", "нет", "no", "skip"}:
        return None
    return cleaned


def _parse_birthdate_input(text: Optional[str]) -> tuple[Optional[str], bool]:
    value = _optional_input_value(text)
    if value is None:
        return None, True
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None, False
    return parsed.isoformat(), True


def _resolve_reporter_name(
    user_row: Optional[UserModel],
    from_user: types.User,
) -> str:
    if user_row and user_row.full_name:
        return user_row.full_name
    if from_user.full_name:
        return from_user.full_name
    if from_user.username:
        return f"@{from_user.username}"
    return str(from_user.id)


def _resolve_reporter_phone(user_row: Optional[UserModel]) -> Optional[str]:
    if user_row and user_row.phone_number:
        return user_row.phone_number
    return None


async def _extract_blacklist_media(
    message: Message,
) -> Optional[tuple[bytes, str, str, int]]:
    photo = message.photo[-1] if message.photo else None
    if photo:
        file_id = photo.file_id
        filename = f"{photo.file_unique_id}.jpg"
        content_type = "image/jpeg"
        declared_size = photo.file_size or 0
    elif message.video:
        file_id = message.video.file_id
        filename = message.video.file_name or f"{message.video.file_unique_id}.mp4"
        content_type = message.video.mime_type or "video/mp4"
        declared_size = message.video.file_size or 0
    elif message.document and message.document.mime_type:
        mime = message.document.mime_type.lower()
        if not mime.startswith(BLACKLIST_MEDIA_ALLOWED_PREFIXES):
            return None
        file_id = message.document.file_id
        filename = message.document.file_name or message.document.file_unique_id or "attachment.bin"
        content_type = message.document.mime_type
        declared_size = message.document.file_size or 0
    else:
        return None

    file = await message.bot.get_file(file_id)
    file_stream = await message.bot.download_file(file.file_path)
    data = file_stream.read() if file_stream else b""
    size = len(data) if data else declared_size
    return data, filename, content_type, size


def _format_blacklist_entry(entry: BackendBlacklistEntry, lang_code: str) -> str:
    field_empty = get_text("blacklist.field.empty", lang_code)
    status_key = (
        "blacklist.entry.status.active" if entry.is_active else "blacklist.entry.status.inactive"
    )
    status = get_text(status_key, lang_code)
    city = entry.city or field_empty
    phone = entry.phone or field_empty
    birthdate = entry.birthdate.isoformat() if entry.birthdate else field_empty
    added = entry.date_added.strftime(get_text("blacklist.field.date_format", lang_code))
    return get_text(
        "blacklist.entry.template",
        lang_code,
        name=entry.name,
        status=status,
        city=city,
        phone=phone,
        birthdate=birthdate,
        complaints=entry.complaints_count,
        appeals=entry.appeals_count,
        added=added,
    )


def _render_blacklist_entries(
    entries: Iterable[BackendBlacklistEntry],
    lang_code: str,
    *,
    limit: Optional[int] = None,
) -> str:
    entry_list = list(entries)
    header = get_text("blacklist.view.header", lang_code)
    body_entries = entry_list if limit is None else entry_list[:limit]
    body = "\n\n".join(_format_blacklist_entry(item, lang_code) for item in body_entries)
    if not body:
        return header
    if limit is not None and len(entry_list) > limit:
        remainder = len(entry_list) - limit
        footer = get_text("blacklist.view.more", lang_code, count=remainder)
        return f"{header}\n\n{body}\n\n{footer}"
    return f"{header}\n\n{body}"


async def _update_blacklist_payload(state: FSMContext, **updates: Any) -> dict[str, Any]:
    data = await state.get_data()
    payload = dict(data.get("payload") or {})
    payload.update(updates)
    await state.update_data(payload=payload)
    return payload


async def _get_blacklist_payload(state: FSMContext) -> dict[str, Any]:
    data = await state.get_data()
    return dict(data.get("payload") or {})


async def _start_blacklist_media_flow(
    state: FSMContext,
    *,
    kind: str,
    reference_id: int,
    reporter_id: Optional[int],
) -> None:
    await state.set_state(
        BlacklistComplaintFlow.waiting_for_media
        if kind == "complaint"
        else BlacklistAppealFlow.waiting_for_media
    )
    await state.update_data(
        payload=None,
        media_context={
            "kind": kind,
            "reference_id": reference_id,
            "reporter_id": reporter_id,
            "count": 0,
            "max_items": BLACKLIST_MEDIA_MAX_ITEMS,
        },
    )


async def _handle_blacklist_media_message(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
    *,
    kind: str,
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("blacklist.common.cancelled", lang_code))
        return
    if _is_media_done_command(message.text):
        await state.clear()
        await message.answer(get_text("blacklist.media.completed", lang_code))
        return
    media_payload = await _extract_blacklist_media(message)
    if media_payload is None:
        await message.answer(get_text("blacklist.media.error.type", lang_code))
        return
    data_bytes, filename, content_type, size = media_payload
    if not data_bytes:
        await message.answer(get_text("blacklist.media.error.upload", lang_code))
        return
    if size > BLACKLIST_MEDIA_MAX_BYTES:
        limit_mb = BLACKLIST_MEDIA_MAX_BYTES // (1024 * 1024)
        await message.answer(get_text("blacklist.media.error.size", lang_code, limit=limit_mb))
        return
    client = get_backend_client(message.bot)
    if client is None:
        await state.clear()
        await message.answer(get_text("blacklist.error.backend_unavailable", lang_code))
        return
    data_state = await state.get_data()
    media_context = data_state.get("media_context") or {}
    reference_id = media_context.get("reference_id")
    reporter_id = media_context.get("reporter_id")
    count = int(media_context.get("count", 0))
    max_items = int(media_context.get("max_items", BLACKLIST_MEDIA_MAX_ITEMS))
    if not reference_id:
        await state.clear()
        await message.answer(get_text("blacklist.error.generic", lang_code))
        return
    try:
        if kind == "complaint":
            await client.upload_complaint_media(
                complaint_id=reference_id,
                reporter_id=reporter_id,
                filename=filename,
                content_type=content_type,
                data=data_bytes,
            )
        else:
            await client.upload_appeal_media(
                appeal_id=reference_id,
                reporter_id=reporter_id,
                filename=filename,
                content_type=content_type,
                data=data_bytes,
            )
    except BackendRequestError as exc:
        logger.warning("Failed to upload blacklist media: %s", exc)
        error_key = "blacklist.media.error.upload"
        if exc.status == 400:
            error_key = "blacklist.media.error.type"
        await message.answer(get_text(error_key, lang_code))
        return
    except Exception:
        logger.exception("Failed to upload blacklist media")
        await message.answer(get_text("blacklist.media.error.upload", lang_code))
        return

    count += 1
    media_context["count"] = count
    await state.update_data(media_context=media_context)
    await message.answer(get_text("blacklist.media.received", lang_code, filename=filename))
    if count >= max_items:
        await message.answer(get_text("blacklist.media.limit", lang_code, limit=max_items))
        await state.clear()


@router.callback_query(F.data == "blacklist_view")
async def handle_blacklist_view(
    callback: CallbackQuery,
    user_row: Optional[UserModel],
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    client = get_backend_client(callback.message.bot)
    if client is None:
        await callback.message.answer(get_text("blacklist.error.backend_unavailable", lang_code))
        return
    try:
        entries = await client.fetch_public_blacklist()
    except Exception:
        logger.exception("Failed to load public blacklist")
        await callback.message.answer(get_text("blacklist.error.generic", lang_code))
        return
    if not entries:
        await callback.message.answer(get_text("blacklist.view.empty", lang_code))
        return
    text = _render_blacklist_entries(entries, lang_code, limit=5)
    await callback.message.answer(text)


@router.callback_query(F.data == "blacklist_search")
async def handle_blacklist_search(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    await state.clear()
    await state.set_state(BlacklistSearchFlow.waiting_for_query)
    prompt = get_text("blacklist.search.prompt", lang_code)
    cancel_hint = get_text("blacklist.common.cancel_hint", lang_code)
    await callback.message.answer(f"{prompt}\n\n{cancel_hint}")


@router.message(BlacklistSearchFlow.waiting_for_query)
async def handle_blacklist_search_query(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("blacklist.common.cancelled", lang_code))
        return

    raw_query = _optional_input_value(message.text)
    if not raw_query:
        await message.answer(get_text("blacklist.search.error.empty", lang_code))
        return

    parts = [part.strip() for part in raw_query.split(";")]
    name_value = _optional_input_value(parts[0] if parts else None)
    if not name_value:
        await message.answer(get_text("blacklist.search.error.empty", lang_code))
        return
    city_value = _optional_input_value(parts[1]) if len(parts) > 1 else None
    birthdate_input = parts[2] if len(parts) > 2 else None
    birthdate_str, birthdate_valid = _parse_birthdate_input(birthdate_input)
    if not birthdate_valid:
        await message.answer(get_text("blacklist.search.error.birthdate", lang_code))
        return
    birthdate_value = date.fromisoformat(birthdate_str) if birthdate_str else None

    client = get_backend_client(message.bot)
    if client is None:
        await state.clear()
        await message.answer(get_text("blacklist.error.backend_unavailable", lang_code))
        return

    try:
        results = await client.search_public_blacklist(
            name=name_value,
            birthdate=birthdate_value,
            city=city_value,
        )
    except Exception:
        logger.exception("Failed to search public blacklist")
        await message.answer(get_text("blacklist.error.generic", lang_code))
        return

    await state.clear()
    if not results:
        await message.answer(get_text("blacklist.search.results.empty", lang_code))
        return
    text = _render_blacklist_entries(results, lang_code)
    await message.answer(text)


@router.callback_query(F.data == "blacklist_report")
async def handle_blacklist_report(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    await state.clear()
    await state.set_state(BlacklistComplaintFlow.waiting_for_name)
    await state.update_data(payload={})
    prompt = get_text("blacklist.report.prompt.name", lang_code)
    cancel_hint = get_text("blacklist.common.cancel_hint", lang_code)
    await callback.message.answer(f"{prompt}\n\n{cancel_hint}")


@router.message(BlacklistComplaintFlow.waiting_for_name)
async def handle_blacklist_complaint_name(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("blacklist.common.cancelled", lang_code))
        return
    name_value = _optional_input_value(message.text)
    if not name_value:
        await message.answer(get_text("blacklist.report.error.name", lang_code))
        return
    await _update_blacklist_payload(state, name=name_value)
    await state.set_state(BlacklistComplaintFlow.waiting_for_phone)
    await message.answer(get_text("blacklist.report.prompt.phone", lang_code))


@router.message(BlacklistComplaintFlow.waiting_for_phone)
async def handle_blacklist_complaint_phone(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("blacklist.common.cancelled", lang_code))
        return
    phone_value = _optional_input_value(message.text)
    await _update_blacklist_payload(state, phone=phone_value)
    await state.set_state(BlacklistComplaintFlow.waiting_for_birthdate)
    await message.answer(get_text("blacklist.report.prompt.birthdate", lang_code))


@router.message(BlacklistComplaintFlow.waiting_for_birthdate)
async def handle_blacklist_complaint_birthdate(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("blacklist.common.cancelled", lang_code))
        return
    birthdate_str, is_valid = _parse_birthdate_input(message.text)
    if not is_valid:
        await message.answer(get_text("blacklist.report.error.birthdate", lang_code))
        return
    await _update_blacklist_payload(state, birthdate=birthdate_str)
    await state.set_state(BlacklistComplaintFlow.waiting_for_city)
    await message.answer(get_text("blacklist.report.prompt.city", lang_code))


@router.message(BlacklistComplaintFlow.waiting_for_city)
async def handle_blacklist_complaint_city(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("blacklist.common.cancelled", lang_code))
        return
    city_value = _optional_input_value(message.text)
    await _update_blacklist_payload(state, city=city_value)
    await state.set_state(BlacklistComplaintFlow.waiting_for_reason)
    await message.answer(get_text("blacklist.report.prompt.reason", lang_code))


@router.message(BlacklistComplaintFlow.waiting_for_reason)
async def handle_blacklist_complaint_reason(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("blacklist.common.cancelled", lang_code))
        return
    reason_text = (message.text or "").strip()
    if not reason_text:
        await message.answer(get_text("blacklist.report.error.reason", lang_code))
        return
    await _update_blacklist_payload(state, reason=reason_text)
    payload = await _get_blacklist_payload(state)
    client = get_backend_client(message.bot)
    if client is None:
        await state.clear()
        await message.answer(get_text("blacklist.error.backend_unavailable", lang_code))
        return

    birthdate_str = payload.get("birthdate")
    birthdate_value = date.fromisoformat(birthdate_str) if birthdate_str else None
    try:
        response = await client.submit_blacklist_complaint(
            name=payload["name"],
            phone=payload.get("phone"),
            birthdate=birthdate_value,
            city=payload.get("city"),
            reason=reason_text,
            added_by=_resolve_reporter_name(user_row, message.from_user),
            added_by_phone=_resolve_reporter_phone(user_row),
            added_by_id=user_row.user_id if user_row else message.from_user.id,
        )
    except BackendRequestError as exc:
        logger.warning("Backend rejected blacklist complaint: %s", exc)
        error_key = (
            "blacklist.error.validation" if exc.status == 400 else "blacklist.error.generic"
        )
        await message.answer(get_text(error_key, lang_code))
        return
    except Exception:
        logger.exception("Failed to submit blacklist complaint")
        await message.answer(get_text("blacklist.error.generic", lang_code))
        return

    status_key = (
        "blacklist.report.success.created"
        if response.created_entry
        else "blacklist.report.success.existing"
    )
    status_text = get_text(status_key, lang_code, name=response.blacklist.name)
    complaint_text = get_text(
        "blacklist.report.success.complaint",
        lang_code,
        complaint_id=response.complaint.id,
    )
    entry_text = _format_blacklist_entry(response.blacklist, lang_code)
    reporter_id = user_row.user_id if user_row else message.from_user.id
    await _start_blacklist_media_flow(
        state,
        kind="complaint",
        reference_id=response.complaint.id,
        reporter_id=reporter_id,
    )
    media_prompt = get_text("blacklist.media.prompt", lang_code, limit=BLACKLIST_MEDIA_MAX_ITEMS)
    await message.answer(f"{status_text}\n{complaint_text}\n\n{entry_text}\n\n{media_prompt}")


@router.message(BlacklistComplaintFlow.waiting_for_media)
async def handle_blacklist_complaint_media(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    await _handle_blacklist_media_message(message, state, user_row, kind="complaint")


@router.callback_query(F.data == "blacklist_appeal")
async def handle_blacklist_appeal(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    await state.clear()
    await state.set_state(BlacklistAppealFlow.waiting_for_name)
    await state.update_data(payload={})
    prompt = get_text("blacklist.appeal.prompt.name", lang_code)
    cancel_hint = get_text("blacklist.common.cancel_hint", lang_code)
    await callback.message.answer(f"{prompt}\n\n{cancel_hint}")


@router.message(BlacklistAppealFlow.waiting_for_name)
async def handle_blacklist_appeal_name(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("blacklist.common.cancelled", lang_code))
        return
    name_value = _optional_input_value(message.text)
    if not name_value:
        await message.answer(get_text("blacklist.appeal.error.name", lang_code))
        return
    await _update_blacklist_payload(state, name=name_value)
    await state.set_state(BlacklistAppealFlow.waiting_for_phone)
    await message.answer(get_text("blacklist.appeal.prompt.phone", lang_code))


@router.message(BlacklistAppealFlow.waiting_for_phone)
async def handle_blacklist_appeal_phone(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("blacklist.common.cancelled", lang_code))
        return
    phone_value = _optional_input_value(message.text)
    await _update_blacklist_payload(state, phone=phone_value)
    await state.set_state(BlacklistAppealFlow.waiting_for_birthdate)
    await message.answer(get_text("blacklist.appeal.prompt.birthdate", lang_code))


@router.message(BlacklistAppealFlow.waiting_for_birthdate)
async def handle_blacklist_appeal_birthdate(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("blacklist.common.cancelled", lang_code))
        return
    birthdate_str, is_valid = _parse_birthdate_input(message.text)
    if not is_valid:
        await message.answer(get_text("blacklist.appeal.error.birthdate", lang_code))
        return
    await _update_blacklist_payload(state, birthdate=birthdate_str)
    await state.set_state(BlacklistAppealFlow.waiting_for_city)
    await message.answer(get_text("blacklist.appeal.prompt.city", lang_code))


@router.message(BlacklistAppealFlow.waiting_for_city)
async def handle_blacklist_appeal_city(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("blacklist.common.cancelled", lang_code))
        return
    city_value = _optional_input_value(message.text)
    await _update_blacklist_payload(state, city=city_value)
    await state.set_state(BlacklistAppealFlow.waiting_for_reason)
    await message.answer(get_text("blacklist.appeal.prompt.reason", lang_code))


@router.message(BlacklistAppealFlow.waiting_for_reason)
async def handle_blacklist_appeal_reason(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("blacklist.common.cancelled", lang_code))
        return
    reason_text = (message.text or "").strip()
    if not reason_text:
        await message.answer(get_text("blacklist.appeal.error.reason", lang_code))
        return
    await _update_blacklist_payload(state, reason=reason_text)
    payload = await _get_blacklist_payload(state)
    client = get_backend_client(message.bot)
    if client is None:
        await state.clear()
        await message.answer(get_text("blacklist.error.backend_unavailable", lang_code))
        return
    birthdate_str = payload.get("birthdate")
    birthdate_value = date.fromisoformat(birthdate_str) if birthdate_str else None
    try:
        response = await client.submit_blacklist_appeal(
            name=payload["name"],
            phone=payload.get("phone"),
            birthdate=birthdate_value,
            city=payload.get("city"),
            reason=reason_text,
            appeal_by=_resolve_reporter_name(user_row, message.from_user),
            appeal_by_phone=_resolve_reporter_phone(user_row),
            appeal_by_id=user_row.user_id if user_row else message.from_user.id,
        )
    except BackendRequestError as exc:
        logger.warning("Backend rejected blacklist appeal: %s", exc)
        if exc.status == 404:
            await message.answer(get_text("blacklist.appeal.not_found", lang_code))
        elif exc.status == 400:
            await message.answer(get_text("blacklist.error.validation", lang_code))
        else:
            await message.answer(get_text("blacklist.error.generic", lang_code))
        return
    except Exception:
        logger.exception("Failed to submit blacklist appeal")
        await message.answer(get_text("blacklist.error.generic", lang_code))
        return

    success_text = get_text("blacklist.appeal.success", lang_code, name=response.blacklist.name)
    appeal_info = get_text(
        "blacklist.appeal.success.appeal",
        lang_code,
        appeal_id=response.appeal.id,
    )
    entry_text = _format_blacklist_entry(response.blacklist, lang_code)
    reporter_id = user_row.user_id if user_row else message.from_user.id
    await _start_blacklist_media_flow(
        state,
        kind="appeal",
        reference_id=response.appeal.id,
        reporter_id=reporter_id,
    )
    media_prompt = get_text("blacklist.media.prompt", lang_code, limit=BLACKLIST_MEDIA_MAX_ITEMS)
    await message.answer(f"{success_text}\n{appeal_info}\n\n{entry_text}\n\n{media_prompt}")


@router.message(BlacklistAppealFlow.waiting_for_media)
async def handle_blacklist_appeal_media(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    await _handle_blacklist_media_message(message, state, user_row, kind="appeal")
