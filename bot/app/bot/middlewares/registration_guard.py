from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, Update

from app.bot.services.registration import (
    REGISTRATION_CALLBACK_PREFIX,
    build_registration_keyboard,
)
from app.bot.states import RegistrationSG
from app.bot.dialogs.flows.settings.states import SettingsSG
from app.services.i18n.localization import get_text, resolve_language


class RegistrationGuardMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Update, dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict[str, Any],
    ) -> Any:
        user_row = data.get("user_row")
        if user_row is not None:
            return await handler(event, data)

        state: FSMContext | None = data.get("state")
        current_state: str | None = None
        if state is not None:
            current_state = await state.get_state()

        registration_states = {
            RegistrationSG.waiting_for_name.state,
            RegistrationSG.waiting_for_email.state,
            RegistrationSG.waiting_for_phone.state,
            RegistrationSG.waiting_for_phone_contact.state,
        }

        if current_state in registration_states:
            return await handler(event, data)

        user = data.get("event_from_user")
        lang_code = resolve_language(
            getattr(user, "language_code", None),
            getattr(user, "locale", None),
            getattr(getattr(event, "from_user", None), "language_code", None),
        )

        if isinstance(event, Message):
            text = (event.text or "").strip()
            if text.startswith("/start") or text.startswith("/lang"):
                return await handler(event, data)

            await event.answer(
                get_text("registration.required", lang_code),
                reply_markup=build_registration_keyboard(),
            )
            return None

        if isinstance(event, CallbackQuery):
            callback_data = event.data or ""
            if callback_data.startswith(REGISTRATION_CALLBACK_PREFIX):
                return await handler(event, data)
            if current_state == SettingsSG.lang.state:
                return await handler(event, data)

            await event.answer(
                get_text("registration.required", lang_code),
                show_alert=True,
            )
            return None

        return await handler(event, data)


__all__ = ["RegistrationGuardMiddleware"]
