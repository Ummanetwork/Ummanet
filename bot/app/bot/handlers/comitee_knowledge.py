from __future__ import annotations

import logging
from typing import Optional

from aiogram import F, Router
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from app.infrastructure.database.db import DB
from app.infrastructure.database.models.user import UserModel
from app.services.ai.fireworks import generate_ai_response
from app.services.i18n.localization import get_text
from config.config import settings

from .comitee_common import edit_or_send_callback, get_backend_client, send_documents, user_language

logger = logging.getLogger(__name__)

router = Router(name="comitee.knowledge")


KNOWLEDGE_TOPICS = {
    "docs_tauhid": ("docs.topic.tauhid", "таухид"),
    "docs_faith": ("docs.topic.faith", "вероучение"),
    "docs_fiqh": ("docs.topic.fiqh", "фикх"),
    "docs_culture": ("docs.topic.culture", "культура"),
}

HOLIDAY_TOPICS = {
    "holiday_uraza": {"text_key": "holiday.uraza", "slug": "uraza"},
    "holiday_kurban": {"text_key": "holiday.kurban", "slug": "kurban"},
    "holiday_ramadan": {"text_key": "holiday.ramadan", "slug": "ramadan"},
    "holiday_hajj": {"text_key": "holiday.hajj", "slug": "hajj"},
}


@router.callback_query(F.data.in_(KNOWLEDGE_TOPICS.keys()))
async def handle_sharia_topic_docs(
    callback: CallbackQuery,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    topic_key, query_ru = KNOWLEDGE_TOPICS[callback.data]
    await callback.answer(
        get_text("docs.searching", lang_code, topic=get_text(topic_key, lang_code))
    )
    documents = await db.documents.search_documents_by_name_in_category(
        category="Шариатские знания",
        pattern=query_ru,
    )
    await send_documents(
        callback.message,
        documents,
        lang_code=lang_code,
        empty_text=get_text("docs.empty", lang_code),
    )


@router.callback_query(F.data.in_(HOLIDAY_TOPICS.keys()))
async def handle_holiday_docs(
    callback: CallbackQuery,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    _ = db  # keep compatibility with middleware injection
    lang_code = user_language(user_row, callback.from_user)
    topic_config = HOLIDAY_TOPICS[callback.data]
    holiday_key = str(topic_config["text_key"])
    topic_slug = str(topic_config["slug"])

    await callback.answer(
        get_text(
            "docs.holiday.searching",
            lang_code,
            holiday=get_text(holiday_key, lang_code),
        )
    )

    backend_client = get_backend_client(callback.bot)
    documents = []
    if backend_client is not None:
        try:
            documents = await backend_client.list_documents(topic_slug)
        except Exception:
            logger.exception("Failed to fetch documents for topic '%s' from backend", topic_slug)

    fallback_language = getattr(settings, "backend_default_language", None)
    primary_document = None
    if backend_client is not None and documents:
        primary_document = backend_client.select_document(
            documents,
            preferred_language=lang_code,
            fallback_language=fallback_language,
        )

    holiday_title = get_text(holiday_key, lang_code)
    description = get_text(f"{holiday_key}.description", lang_code)
    message_text = get_text(
        "holiday.description.template",
        lang_code,
        holiday=holiday_title,
        description=description,
    )

    document_id = getattr(primary_document, "id", None)
    if document_id is None:
        message_text = f"{message_text}\n\n{get_text('holiday.document.missing', lang_code)}"

    keyboard_rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=get_text("button.holiday.ask_ai", lang_code),
                callback_data=f"holiday_ai:{callback.data}",
            )
        ]
    ]
    if document_id is not None:
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text=get_text("button.holiday.download", lang_code),
                    callback_data=f"holiday_doc:{document_id}",
                )
            ]
        )
    keyboard_rows.append(
        [InlineKeyboardButton(text=get_text("button.back", lang_code), callback_data="back_to_main")]
    )

    await edit_or_send_callback(
        callback,
        message_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
    )


@router.callback_query(F.data.startswith("holiday_ai:"))
async def handle_holiday_ai_prompt(
    callback: CallbackQuery,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    try:
        holiday_slug = (callback.data or "").split(":", 1)[1]
    except IndexError:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return

    topic_config = HOLIDAY_TOPICS.get(holiday_slug)
    if topic_config is None:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return

    holiday_key = str(topic_config["text_key"])
    holiday_title = get_text(holiday_key, lang_code)
    question = get_text("holiday.ai.default_question", lang_code, holiday=holiday_title)

    await callback.answer()
    waiting_message = await callback.message.answer(get_text("ai.response.waiting", lang_code))
    ai_answer = await generate_ai_response(question, lang_code=lang_code)
    prefix = get_text("ai.response.prefix", lang_code)
    footer = get_text("ai.response.footer", lang_code)
    final_text = f"{prefix}\n{ai_answer}\n\n{footer}"
    try:
        await waiting_message.edit_text(final_text)
    except Exception:
        logger.exception("Failed to edit AI waiting message")
        await callback.message.answer(final_text)


@router.callback_query(F.data.startswith("holiday_doc:"))
async def handle_holiday_document_download(
    callback: CallbackQuery,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    _ = db
    lang_code = user_language(user_row, callback.from_user)
    try:
        document_id = int((callback.data or "").split(":", 1)[1])
    except (IndexError, ValueError):
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return

    backend_client = get_backend_client(callback.bot)
    if backend_client is None:
        await callback.answer(get_text("holiday.document.missing", lang_code), show_alert=True)
        return

    try:
        content, filename, _content_type = await backend_client.download_document(document_id)
    except Exception:
        logger.exception("Failed to download holiday document %s", document_id)
        await callback.answer(get_text("holiday.document.missing", lang_code), show_alert=True)
        return

    if not content:
        await callback.answer(get_text("holiday.document.missing", lang_code), show_alert=True)
        return

    try:
        buffer = BufferedInputFile(content, filename=filename or f"document_{document_id}.pdf")
        await callback.message.answer_document(
            document=buffer,
            caption=f"📄 {filename or get_text('docs.default_name', lang_code)}",
        )
        await callback.answer()
    except Exception:
        logger.exception("Failed to send holiday document '%s'", filename)
        await callback.answer(
            get_text(
                "error.document.send",
                lang_code,
                name=filename or get_text("docs.default_name", lang_code),
            ),
            show_alert=True,
        )
