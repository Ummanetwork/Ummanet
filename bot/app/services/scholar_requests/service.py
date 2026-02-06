from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any, Literal, Protocol, Sequence

from app.services.i18n.localization import get_text, resolve_language

ScholarRequestType = Literal["video", "text", "docs"]
MAX_ATTACHMENTS = 5


class TelegramUserLike(Protocol):
    id: int
    username: str | None
    full_name: str


@dataclass(frozen=True, slots=True)
class ScholarAttachment:
    content: bytes
    filename: str
    content_type: str


@dataclass(frozen=True, slots=True)
class ScholarRequestDraft:
    request_type: ScholarRequestType
    data: dict[str, Any]
    attachments: Sequence[ScholarAttachment]


def build_request_summary(draft: ScholarRequestDraft) -> str:
    request_type = draft.request_type
    data = draft.data or {}
    if request_type == "video":
        title = "🎥 Запрос видеоконференции"
        details = [
            f"Время: {data.get('ask_video_time') or '—'}",
            f"Контакт: {data.get('ask_video_contact') or '—'}",
            f"Описание: {data.get('ask_video_description') or '—'}",
        ]
    elif request_type == "docs":
        title = "📎 Документы"
        details = [f"Описание: {data.get('ask_docs_description') or '—'}"]
    else:
        title = "💬 Вопрос текстом"
        details = [f"Текст: {data.get('ask_text') or '—'}"]
    details.append(f"Вложения: {len(draft.attachments)}")
    return "\n".join([title, *details]).strip()


def build_request_payload(
    *,
    request_id: int,
    telegram_user: TelegramUserLike,
    language: str,
    draft: ScholarRequestDraft,
) -> dict[str, Any]:
    username = f"@{telegram_user.username}" if telegram_user.username else ""
    return {
        "request_id": request_id,
        "user_id": telegram_user.id,
        "username": username,
        "full_name": telegram_user.full_name,
        "language": language,
        "type": draft.request_type,
        "data": dict(draft.data or {}),
        "attachments": [
            {
                "filename": item.filename,
                "content_type": item.content_type,
                "size": len(item.content),
            }
            for item in draft.attachments
        ],
    }


def build_forward_text(
    *,
    request_id: int,
    telegram_user: TelegramUserLike,
    summary: str,
) -> str:
    username = f"@{telegram_user.username}" if telegram_user.username else ""
    return (
        f"🆕 Заявка учёному #{request_id}\n"
        f"Пользователь: {telegram_user.full_name} {username} (id={telegram_user.id})\n\n"
        f"{summary}"
    )


async def persist_request_to_documents(
    db: Any,
    *,
    request_id: int,
    user_id: int,
    payload: dict[str, Any],
    attachments: Sequence[ScholarAttachment],
) -> None:
    meta_filename = f"scholar_request_{user_id}_{request_id}_{uuid.uuid4().hex}.json"
    await db.documents.add_document(
        filename=meta_filename,
        user_id=user_id,
        category="ScholarRequests",
        name=f"Scholar request #{request_id}",
        content=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        doc_type="ScholarRequest",
    )
    for idx, attachment in enumerate(attachments, start=1):
        safe_name = (attachment.filename or f"attachment_{idx}").strip()[:120]
        doc_filename = f"scholar_request_{user_id}_{request_id}_{idx}_{uuid.uuid4().hex}"
        await db.documents.add_document(
            filename=doc_filename,
            user_id=user_id,
            category="ScholarRequests",
            name=f"#{request_id} {safe_name} ({attachment.content_type})",
            content=attachment.content,
            doc_type="ScholarRequestAttachment",
        )


def _scholars_group_id() -> int:
    from config.config import settings

    try:
        value = getattr(settings.bot, "SCHOLARS_GROUP_ID", None)
        if value is None:
            value = getattr(settings.bot, "scholars_group_id", 0)
        return int(value or 0)
    except (AttributeError, TypeError, ValueError):
        return 0


async def forward_request_to_group(
    bot: Any,
    *,
    request_id: int,
    user_id: int,
    text: str,
    attachments: Sequence[ScholarAttachment],
) -> bool:
    from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup
    from config.config import settings

    group_id = _scholars_group_id()
    if not group_id:
        return False

    group_lang = resolve_language(getattr(getattr(settings, "i18n", {}), "default_locale", None))
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("button.answer.user", group_lang),
                    callback_data=f"reply_{user_id}_{request_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("button.profile.open", group_lang),
                    url=f"tg://user?id={user_id}",
                )
            ],
        ]
    )

    try:
        await bot.send_message(chat_id=group_id, text=text, reply_markup=keyboard)
        for item in attachments:
            buffer = BufferedInputFile(item.content, filename=item.filename or f"attachment_{request_id}")
            if item.content_type.startswith("image/"):
                await bot.send_photo(chat_id=group_id, photo=buffer)
            else:
                await bot.send_document(chat_id=group_id, document=buffer)
        return True
    except Exception:
        return False
