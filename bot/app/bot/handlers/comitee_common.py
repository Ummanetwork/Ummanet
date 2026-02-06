from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional

from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardMarkup

from app.infrastructure.database.models.user import UserModel
from app.services.backend import BackendDocumentsClient
from app.services.i18n.localization import get_text, resolve_language
from config.config import settings

logger = logging.getLogger(__name__)


def user_language(user_row: Optional[UserModel], telegram_user: types.User) -> str:
    return resolve_language(
        getattr(user_row, "language_code", None),
        getattr(telegram_user, "language_code", None),
    )


async def edit_or_send_callback(
    callback: CallbackQuery,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup,
) -> None:
    try:
        await callback.message.edit_text(
            text,
            reply_markup=reply_markup,
        )
    except Exception:
        logger.exception("Failed to edit message, sending new one")
        await callback.message.answer(
            text,
            reply_markup=reply_markup,
        )


def is_cancel_command(text: Optional[str]) -> bool:
    normalized = (text or "").strip().lower()
    return normalized in {"cancel", "/cancel", "отмена", "\\cancel", "stop"}


def get_backend_client(bot: types.Bot) -> Optional[BackendDocumentsClient]:
    return getattr(bot, "backend_documents_client", None)


def admin_ids() -> list[int]:
    raw_ids = getattr(settings, "ADMIN_IDS", [])
    if not isinstance(raw_ids, (list, tuple, set)):
        raw_ids = str(raw_ids).replace(";", ",").split(",") if raw_ids else []
    result: list[int] = []
    for item in raw_ids:
        try:
            result.append(int(str(item).strip()))
        except Exception:
            continue
    return result


def scholars_group_id() -> int:
    try:
        value = getattr(settings.bot, "SCHOLARS_GROUP_ID", None)
        if value is None:
            value = getattr(settings.bot, "scholars_group_id", 0)
        return int(value or 0)
    except (AttributeError, TypeError, ValueError):
        return 0


async def safe_state_clear(state: FSMContext) -> None:
    try:
        await state.clear()
    except Exception:
        logger.debug("Failed to clear FSM state", exc_info=True)


def today_iso() -> str:
    return date.today().isoformat()


async def send_documents(
    message: types.Message,
    documents: Any,
    *,
    lang_code: str,
    empty_text: str,
) -> None:
    sent_any = False
    for doc in documents or []:
        try:
            content = doc.get("content")
            name = doc.get("name") or get_text("docs.default_name", lang_code)
        except AttributeError:
            continue
        if not content:
            continue
        sent_any = True
        try:
            buffer = BufferedInputFile(bytes(content), filename=f"{name}.pdf")
            await message.answer_document(
                document=buffer,
                caption=f"📄 {name}",
            )
        except Exception:
            logger.exception("Failed to send document '%s'", name)
            await message.answer(get_text("error.document.send", lang_code, name=name))
    if not sent_any:
        await message.answer(empty_text)
