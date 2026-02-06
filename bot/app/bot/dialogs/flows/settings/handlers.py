import logging

from aiogram import Bot
from aiogram.enums import BotCommandScopeType
from aiogram.types import BotCommandScopeChat, CallbackQuery
from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.kbd import Button, ManagedRadio

from app.bot.dialogs.flows.settings.getters import build_locales
from app.bot.handlers.comitee import show_welcome_menu
from app.bot.keyboards.menu_button import get_main_menu_commands
from app.bot.services.registration import build_registration_keyboard
from app.infrastructure.database.db import DB
from app.infrastructure.database.models.user import UserModel
from app.services.i18n.localization import get_text, resolve_language
from config.config import settings

logger = logging.getLogger(__name__)


def _current_lang(dialog_manager: DialogManager) -> str:
    user_row: UserModel | None = dialog_manager.middleware_data.get("user_row")
    return resolve_language(getattr(user_row, "language_code", None))


def _locales(dialog_manager: DialogManager) -> list[str]:
    return build_locales(dialog_manager)


async def set_radio_lang_default(_, dialog_manager: DialogManager):
    locales = _locales(dialog_manager)
    radio: ManagedRadio = dialog_manager.find("radio_lang")
    current_lang = _current_lang(dialog_manager)
    try:
        index = locales.index(current_lang)
    except ValueError:
        index = 0 if locales else 0
    await radio.set_checked(str(index + 1))


async def update_user_lang(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
):
    locales = _locales(dialog_manager)
    radio_lang: ManagedRadio = dialog_manager.find("radio_lang")
    try:
        checked_locale = locales[int(radio_lang.get_checked()) - 1]
    except Exception:
        checked_locale = locales[0] if locales else resolve_language()

    user_row: UserModel | None = dialog_manager.middleware_data.get("user_row")
    if user_row is not None:
        db: DB = dialog_manager.middleware_data.get("db")
        await db.users.update_user_lang(
            user_id=callback.from_user.id,
            user_lang=checked_locale,
        )
        try:
            dialog_manager.middleware_data["user_row"] = user_row.model_copy(
                update={"language_code": checked_locale}
            )
        except AttributeError:
            pass

    bot: Bot = dialog_manager.middleware_data.get("bot")
    _ = bot
    # Avoid updating Telegram commands to prevent user-facing "Main menu updated"
    # system notifications in clients.

    await callback.answer(get_text("language.saved", checked_locale))
    await dialog_manager.done()
    if user_row is None:
        await bot.send_message(
            chat_id=callback.from_user.id,
            text=get_text("registration.required", checked_locale),
            reply_markup=build_registration_keyboard(),
        )
        return
    version = getattr(settings, "BOT_VERSION", "0.0.0")
    await bot.send_message(
        chat_id=callback.from_user.id,
        text=get_text("bot.version.info", checked_locale, version=version),
    )
    if callback.message:
        await show_welcome_menu(
            callback.message,
            is_new_user=False,
            lang_code=checked_locale,
        )


async def cancel_set_lang(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    await dialog_manager.done()
