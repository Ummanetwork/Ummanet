from typing import List

from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.kbd import ManagedRadio

from app.bot.dialogs.flows.settings.keyboards import get_lang_buttons
from app.bot.enums.roles import UserRole
from app.infrastructure.database.models.user import UserModel
from app.services.i18n.localization import get_text, resolve_language
from config.config import settings


def _current_language(dialog_manager: DialogManager) -> str:
    user_row: UserModel | None = dialog_manager.middleware_data.get("user_row")
    return resolve_language(getattr(user_row, "language_code", None))


def _normalize_locales(locales: List[str]) -> List[str]:
    seen: List[str] = []
    for code in locales:
        normalized = (code or "").strip().lower()
        if not normalized:
            continue
        if normalized not in seen:
            seen.append(normalized)
    return seen


def build_locales(dialog_manager: DialogManager) -> list[str]:
    locales_raw: list[str] = dialog_manager.middleware_data.get("bot_locales") or []
    if not locales_raw:
        locales_raw = list(getattr(getattr(settings, "i18n", {}), "locales", []) or [])
    locales = _normalize_locales(locales_raw)

    user_row: UserModel | None = dialog_manager.middleware_data.get("user_row")
    viewer_lang = _current_language(dialog_manager)
    current_lang = viewer_lang
    if user_row is not None:
        current_lang = resolve_language(getattr(user_row, "language_code", None))

    # Always keep Russian available as a safe fallback.
    if "ru" not in locales:
        locales.append("ru")
    if current_lang not in locales:
        locales.append(current_lang)

    user_role = getattr(user_row, "role", UserRole.USER)
    is_privileged = user_role in {UserRole.ADMIN, UserRole.OWNER}

    if is_privileged:
        if "dev" not in locales:
            locales.append("dev")
    else:
        if current_lang == "dev":
            if "dev" not in locales:
                locales.append("dev")
        else:
            locales = [code for code in locales if code != "dev"]

    if not locales:
        locales = [viewer_lang]

    return locales


async def get_set_lang(dialog_manager: DialogManager, **kwargs):
    locales = build_locales(dialog_manager)

    user_row: UserModel | None = dialog_manager.middleware_data.get("user_row")
    viewer_lang = _current_language(dialog_manager)
    current_lang = viewer_lang
    if user_row is not None:
        current_lang = resolve_language(getattr(user_row, "language_code", None))

    radio_lang: ManagedRadio = dialog_manager.find("radio_lang")
    if locales:
        try:
            checked_index = int(radio_lang.get_checked()) - 1
            checked_locale = locales[checked_index]
        except Exception:
            checked_locale = locales[0]
    else:
        checked_locale = viewer_lang

    return {
        "set_lang": get_text("language.menu.title", viewer_lang),
        "lang_buttons": get_lang_buttons(locales=locales, viewer_lang=viewer_lang),
        "back_button": get_text("language.back", viewer_lang),
        "save_button": get_text("language.save", viewer_lang),
    }
