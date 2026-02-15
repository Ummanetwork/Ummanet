from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Optional

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.bot.states.comitee import ScholarAnswers
from app.infrastructure.database.db import DB
from app.infrastructure.database.models.user import UserModel
from app.services.ai.fireworks import generate_ai_response
from app.services.i18n.localization import get_text, resolve_language
from config.config import settings

from .comitee_common import scholars_group_id, user_language
from .comitee_menu import MAIN_MENU_KEYS, MenuKeyFilter
from .comitee_questions import get_pending_question, pop_pending_question, set_pending_question

logger = logging.getLogger(__name__)

router = Router(name="comitee.scholars")


async def answer_placeholder(
    callback: CallbackQuery,
    user_row: Optional[UserModel],
    text_key: str,
    *,
    show_alert: bool = True,
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    text = get_text(text_key, lang_code)
    await callback.answer(text, show_alert=show_alert)


def _build_ai_followup_keyboard(lang_code: str, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("button.ask.scholars", lang_code),
                    callback_data=f"ask_{user_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("button.community.support", lang_code),
                    url="https://t.me/+GLVL7Yi7OBszMmE8",
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("button.materials", lang_code),
                    url="https://t.me/Sharia_Men_Chat",
                )
            ],
        ]
    )


async def _deliver_generic_ai_answer(
    *,
    bot: types.Bot,
    chat_id: int,
    waiting_message_id: int,
    question_text: str,
    lang_code: str,
    user_id: int,
) -> None:
    try:
        ai_answer = await generate_ai_response(question_text, lang_code=lang_code)
        prefix = get_text("ai.response.prefix", lang_code)
        footer = get_text("ai.response.footer", lang_code)
        keyboard = _build_ai_followup_keyboard(lang_code, user_id)
        final_text = f"{prefix}\n{ai_answer}\n\n{footer}"
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=waiting_message_id,
                text=final_text,
                reply_markup=keyboard,
            )
        except Exception:
            logger.exception("Failed to edit AI waiting message in scholars flow")
            await bot.send_message(chat_id=chat_id, text=final_text, reply_markup=keyboard)
    except Exception:
        logger.exception("Failed to deliver generic AI answer")


@router.message(ScholarAnswers.answer)
async def handle_scholar_answer(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    lang_code = user_language(user_row, message.from_user)
    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    question_id = data.get("question_id")
    answer_text = (message.text or "").strip()

    if not target_user_id or not answer_text:
        await message.answer(get_text("error.answer.recipient_unknown", lang_code))
        await state.clear()
        return

    try:
        target_user = await db.users.get_user(user_id=target_user_id)
        target_lang = resolve_language(getattr(target_user, "language_code", None))
        await message.bot.send_message(
            chat_id=target_user_id,
            text=get_text(
                "notify.answer.user",
                target_lang,
                question_id=question_id,
                answer_text=answer_text,
            ),
        )
        await message.answer(get_text("answer.sent.confirmation", lang_code))
    except Exception:
        logger.exception("Failed to forward scholar answer")
        await message.answer(get_text("answer.delivery.failed", lang_code))

    await state.clear()


@router.callback_query(F.data.startswith("reply_"))
async def handle_reply_callback(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    parts = (callback.data or "").split("_")
    if len(parts) < 3:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return

    try:
        target_user_id = int(parts[1])
        question_id = int(parts[2])
    except ValueError:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return

    await state.set_state(ScholarAnswers.answer)
    await state.update_data(target_user_id=target_user_id, question_id=question_id)
    await callback.answer()
    await callback.message.answer(get_text("question.prompt", lang_code, question_id=question_id))


async def forward_question(
    *,
    question: str,
    user_id: int,
    question_id: int,
    bot: types.Bot,
) -> bool:
    group_id = scholars_group_id()
    if not group_id:
        logger.warning("SCHOLARS_GROUP_ID is not configured; question not forwarded")
        return False

    group_lang = resolve_language(getattr(getattr(settings, "i18n", {}), "default_locale", None))
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("button.answer.user", group_lang),
                    callback_data=f"reply_{user_id}_{question_id}",
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
        await bot.send_message(
            chat_id=group_id,
            text=get_text(
                "notify.question.forward",
                group_lang,
                question_id=question_id,
                user_id=user_id,
                question=question,
            ),
            reply_markup=keyboard,
        )
        return True
    except Exception:
        logger.exception("Failed to forward question to scholars group")
        return False


@router.callback_query(F.data.startswith("ask_"))
async def handle_ask_scholar(
    callback: CallbackQuery,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    user_id = callback.from_user.id
    question = get_pending_question(user_id)
    if not question:
        await callback.answer(get_text("question.empty", lang_code), show_alert=True)
        return

    question_id = uuid.uuid4().int % 100000
    success = await forward_question(
        question=question,
        user_id=user_id,
        question_id=question_id,
        bot=callback.message.bot,
    )
    if success:
        await callback.answer(get_text("question.sent", lang_code), show_alert=False)
        pop_pending_question(user_id)
    else:
        await callback.answer(get_text("question.failed", lang_code), show_alert=True)


@router.message(~MenuKeyFilter(MAIN_MENU_KEYS))
async def handle_generic_message(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    if await state.get_state():
        return
    if message.text and message.text.startswith("/"):
        return

    question_text = (message.text or "").strip()
    if not question_text:
        return

    lang_code = user_language(user_row, message.from_user)
    set_pending_question(message.from_user.id, question_text)
    waiting_message = await message.answer(get_text("ai.response.waiting", lang_code))
    asyncio.create_task(
        _deliver_generic_ai_answer(
            bot=message.bot,
            chat_id=message.chat.id,
            waiting_message_id=waiting_message.message_id,
            question_text=question_text,
            lang_code=lang_code,
            user_id=message.from_user.id,
        )
    )
