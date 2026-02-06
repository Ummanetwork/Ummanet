import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import (
    TelegramObject,
    Update,
    User,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from app.infrastructure.database.models.user import UserModel
from aiogram.fsm.context import FSMContext
from app.bot.states import UnbanAppealSG
from app.services.i18n.localization import get_text, resolve_language

logger = logging.getLogger(__name__)


class ShadowBanMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict[str, Any],
    ) -> Any:
        try:
            user_row: UserModel | None = data.get("user_row")
            if user_row is None:
                logger.warning(
                    "Cannot check for shadow ban. The 'user_row' key was not found in the middleware data."
                )
                return await handler(event, data)

            if user_row.banned:
                # Allow unban appeal flow through
                fsm: FSMContext | None = data.get("state")
                current_state: str | None = None
                if fsm is not None:
                    current_state = await fsm.get_state()
                # Allow the state where user types reason
                if current_state == UnbanAppealSG.waiting_for_reason.state:
                    return await handler(event, data)
                # Allow clicking the unban button callback
                if getattr(event, "callback_query", None):
                    cb = event.callback_query
                    if cb and (cb.data or "").startswith("unban:"):
                        return await handler(event, data)
                logger.warning("Shadow-banned user tried to interact: %d", user_row.user_id)
                # Resolve language from stored pref or Telegram locale
                tg_user = (
                    getattr(event, "from_user", None)
                    or (getattr(event, "message", None) and getattr(event.message, "from_user", None))
                )
                lang_code = resolve_language(
                    getattr(user_row, "language_code", None),
                    getattr(tg_user, "language_code", None),
                    None,
                )
                text = get_text("error.user.banned", lang_code)
                # Unban request button
                kb = InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text=get_text("button.unban.request", lang_code), callback_data="unban:request")]]
                )
                # Notify and remove reply keyboard if present
                if getattr(event, "message", None):
                    # Remove reply keyboard first
                    await event.message.answer(text, reply_markup=ReplyKeyboardRemove())
                    # Then send inline button for appeal
                    await event.message.answer(get_text("button.unban.request", lang_code), reply_markup=kb)
                elif getattr(event, "callback_query", None) and getattr(event.callback_query, "message", None):
                    # Clean inline keyboard on the message user interacted with
                    try:
                        await event.callback_query.message.edit_reply_markup(reply_markup=None)
                    except Exception:
                        pass
                    await event.callback_query.message.answer(text, reply_markup=ReplyKeyboardRemove())
                    await event.callback_query.message.answer(get_text("button.unban.request", lang_code), reply_markup=kb)
                    await event.callback_query.answer()
                else:
                    # Fallback: try to answer callback if present
                    if getattr(event, "callback_query", None):
                        await event.callback_query.answer(text, show_alert=True)
                return

            return await handler(event, data)
        except Exception:
            logger.exception("ShadowBanMiddleware failed; passing event through")
            return await handler(event, data)
