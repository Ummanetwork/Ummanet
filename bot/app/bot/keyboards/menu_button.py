import logging

from aiogram.types import BotCommand

from app.services.i18n.localization import get_text

logger = logging.getLogger(__name__)


def get_main_menu_commands(lang_code: str) -> list[BotCommand]:
    return [
        BotCommand(command="start", description=get_text("command.start.description", lang_code)),
        BotCommand(command="lang", description=get_text("command.lang.description", lang_code)),
        BotCommand(command="help", description=get_text("command.help.description", lang_code)),
    ]
