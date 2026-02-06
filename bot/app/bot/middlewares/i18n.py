import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from fluentogram import TranslatorHub

from app.infrastructure.database.models.user import UserModel
from app.services.i18n.localization import DEFAULT_LANGUAGE, resolve_language
from config.config import settings

logger = logging.getLogger(__name__)


class TranslatorRunnerMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user: User = data.get("event_from_user")

        if user is None:
            return await handler(event, data)

        user_row: UserModel = data.get("user_row")

        if user_row and user_row.language_code:
            user_lang = user_row.language_code
        else:
            user_lang = user.language_code

        hub: TranslatorHub = data.get("translator_hub")
        default_locale = getattr(getattr(settings, "i18n", {}), "default_locale", None)
        resolved_lang = resolve_language(user_lang, default_locale)
        if resolved_lang == "dev":
            resolved_lang = DEFAULT_LANGUAGE
        try:
            translator = hub.get_translator_by_locale(resolved_lang)
        except KeyError:
            translator = hub.get_translator_by_locale(DEFAULT_LANGUAGE)

        data["i18n"] = translator

        return await handler(event, data)
