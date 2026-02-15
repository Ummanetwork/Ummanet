import logging

from aiogram.types import BotCommand

from app.services.i18n.localization import get_text

logger = logging.getLogger(__name__)
_DESCRIPTION_LIMIT = 256


def _safe_description(key: str, lang_code: str) -> str:
    text = (get_text(key, lang_code) or "").strip()
    if len(text) <= _DESCRIPTION_LIMIT:
        return text
    # Telegram API constraint: command description length must not exceed 256.
    if _DESCRIPTION_LIMIT >= 3:
        truncated = text[: _DESCRIPTION_LIMIT - 3].rstrip() + "..."
    else:
        truncated = text[:_DESCRIPTION_LIMIT]
    logger.warning(
        "Command description too long for key=%s lang=%s (len=%s); truncating",
        key,
        lang_code,
        len(text),
    )
    return truncated


def get_main_menu_commands(lang_code: str) -> list[BotCommand]:
    return [
        BotCommand(command="start", description=_safe_description("command.start.description", lang_code)),
        BotCommand(command="lang", description=_safe_description("command.lang.description", lang_code)),
        BotCommand(command="help", description=_safe_description("command.help.description", lang_code)),
    ]
