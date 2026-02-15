from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from aiogram import F, Router, types
from aiogram.filters import BaseFilter, Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from app.infrastructure.database.models.user import UserModel
from app.infrastructure.database.db import DB
from app.services.i18n.localization import get_text, resolve_language
from config.config import settings
from shared.link_slots import DEFAULT_MEN_CHAT_URL, DEFAULT_WOMEN_CHAT_URL

from .comitee_common import user_language
from .comitee_sharia_control import show_shariah_control_menu

logger = logging.getLogger(__name__)

router = Router(name="comitee.menu")


MAIN_MENU_LAYOUT = [
    ["menu.my_cases", "menu.blacklist"],
    ["menu.knowledge", "menu.committee"],
    ["menu.meetings_chats", "menu.enforcement"],
    ["menu.good_deeds", "menu.zakat"],
]

MAIN_MENU_KEYS = {key for row in MAIN_MENU_LAYOUT for key in row}

_CONFIGURED_LOCALES = getattr(getattr(settings, "i18n", {}), "locales", []) or []
MENU_LANGUAGES = {resolve_language(locale) for locale in _CONFIGURED_LOCALES}
MENU_LANGUAGES.add("ru")


def _bot_option(*names: str) -> Optional[str]:
    bot_cfg = getattr(settings, "bot", None)
    for name in names:
        if bot_cfg and hasattr(bot_cfg, name):
            value = getattr(bot_cfg, name)
            if value:
                return str(value)
    return None


MEN_CHAT_URL = _bot_option("MEN_CHAT_URL", "men_chat_url") or DEFAULT_MEN_CHAT_URL
WOMEN_CHAT_URL = (
    _bot_option("WOMEN_CHAT_URL", "women_chat_url") or DEFAULT_WOMEN_CHAT_URL
)
COURTS_OPENED_CHAT_URL = (
    _bot_option("COURTS_OPENED_CHAT_URL", "courts_opened_chat_url") or MEN_CHAT_URL
)
COURTS_CLOSED_CHAT_URL = (
    _bot_option("COURTS_CLOSED_CHAT_URL", "courts_closed_chat_url") or MEN_CHAT_URL
)
COURTS_IN_PROGRESS_CHAT_URL = (
    _bot_option("COURTS_IN_PROGRESS_CHAT_URL", "courts_in_progress_chat_url") or MEN_CHAT_URL
)


def _normalize_menu_label(value: str) -> str:
    cleaned = "".join(ch for ch in (value or "") if ch.isalnum() or ch.isspace())
    normalized = " ".join(cleaned.split())
    return normalized.strip()


MENU_LABELS_BY_LANGUAGE: dict[str, dict[str, str]] = {}
MENU_KEY_BY_LABEL_BY_LANGUAGE: dict[str, dict[str, str]] = {}
MENU_KEY_BY_NORMALIZED_LABEL_BY_LANGUAGE: Dict[str, Dict[str, str]] = {}
MENU_TEXT_OPTIONS: set[str] = set(MAIN_MENU_KEYS)


def _bootstrap_menu_texts() -> None:
    global MENU_LABELS_BY_LANGUAGE, MENU_KEY_BY_LABEL_BY_LANGUAGE, MENU_KEY_BY_NORMALIZED_LABEL_BY_LANGUAGE, MENU_TEXT_OPTIONS
    MENU_LABELS_BY_LANGUAGE = {
        lang: {key: get_text(key, lang) for key in MAIN_MENU_KEYS} for lang in MENU_LANGUAGES
    }
    MENU_KEY_BY_LABEL_BY_LANGUAGE = {}
    MENU_KEY_BY_NORMALIZED_LABEL_BY_LANGUAGE = {}
    MENU_TEXT_OPTIONS = set(MAIN_MENU_KEYS)
    for lang, labels in MENU_LABELS_BY_LANGUAGE.items():
        direct_map: Dict[str, str] = {}
        normalized_map: Dict[str, str] = {}
        for key, label in labels.items():
            if not label:
                continue
            direct_map[label] = key
            MENU_TEXT_OPTIONS.add(label)
            normalized = _normalize_menu_label(label)
            if normalized and normalized != label:
                normalized_map[normalized] = key
                MENU_TEXT_OPTIONS.add(normalized)
        MENU_KEY_BY_LABEL_BY_LANGUAGE[lang] = direct_map
        MENU_KEY_BY_NORMALIZED_LABEL_BY_LANGUAGE[lang] = normalized_map


_bootstrap_menu_texts()


class MenuKeyFilter(BaseFilter):
    """Match messages whose reply-button text maps to a specific menu key."""

    def __init__(self, *keys: str) -> None:
        if len(keys) == 1 and isinstance(keys[0], (set, list, tuple)):
            keys = tuple(keys[0])
        self._keys = set(keys) if keys else set(MAIN_MENU_KEYS)

    async def __call__(
        self,
        message: Message,
        user_row: Optional[UserModel] = None,
    ) -> Optional[dict]:
        text = (message.text or "").strip()
        if not text:
            return False

        lang_code = user_language(user_row, message.from_user)
        menu_key = resolve_menu_key(text, lang_code)
        if menu_key and menu_key in self._keys:
            return {"menu_key": menu_key}
        return False


def rebuild_menu_texts(locales: Iterable[str] | None = None) -> None:
    """Rebuild menu label caches after i18n runtime translations are loaded."""
    global MENU_LANGUAGES, MENU_LABELS_BY_LANGUAGE, MENU_KEY_BY_LABEL_BY_LANGUAGE, MENU_KEY_BY_NORMALIZED_LABEL_BY_LANGUAGE, MENU_TEXT_OPTIONS
    langs = set(resolve_language(loc or None) for loc in (locales or []))
    langs.add("ru")
    MENU_LANGUAGES = langs
    MENU_LABELS_BY_LANGUAGE = {}
    MENU_KEY_BY_LABEL_BY_LANGUAGE = {}
    MENU_KEY_BY_NORMALIZED_LABEL_BY_LANGUAGE = {}
    MENU_TEXT_OPTIONS = set(MAIN_MENU_KEYS)
    for lang in MENU_LANGUAGES:
        labels = {key: get_text(key, lang) for key in MAIN_MENU_KEYS}
        MENU_LABELS_BY_LANGUAGE[lang] = labels
        direct_map: Dict[str, str] = {}
        normalized_map: Dict[str, str] = {}
        for key, label in labels.items():
            if not label:
                continue
            direct_map[label] = key
            MENU_TEXT_OPTIONS.add(label)
            normalized = _normalize_menu_label(label)
            if normalized:
                normalized_map[normalized] = key
                MENU_TEXT_OPTIONS.add(normalized)
        MENU_KEY_BY_LABEL_BY_LANGUAGE[lang] = direct_map
        MENU_KEY_BY_NORMALIZED_LABEL_BY_LANGUAGE[lang] = normalized_map


@dataclass(frozen=True)
class InlineButton:
    key: str
    callback: Optional[str] = None
    url: Optional[str] = None


@dataclass(frozen=True)
class InlineMenu:
    key: str
    title_key: str
    buttons: List[List[InlineButton]]


INLINE_MENU_DEFINITIONS: Dict[str, InlineMenu] = {
    "menu.my_cases": InlineMenu(
        key="menu.my_cases",
        title_key="menu.my_cases.title",
        buttons=[
            [InlineButton(key="button.my_cases.contracts", callback="menu:menu.contracts")],
            [InlineButton(key="button.my_cases.courts", callback="menu:menu.courts")],
            [InlineButton(key="button.my_cases.inheritance", callback="menu:menu.inheritance")],
            [InlineButton(key="button.my_cases.nikah", callback="menu:menu.nikah")],
            [InlineButton(key="button.back", callback="back_to_main")],
        ],
    ),
    "menu.blacklist": InlineMenu(
        key="menu.blacklist",
        title_key="menu.blacklist.title",
        buttons=[
            [InlineButton(key="button.blacklist.view", callback="blacklist_view")],
            [InlineButton(key="button.blacklist.search", callback="blacklist_search")],
            [InlineButton(key="button.blacklist.report", callback="blacklist_report")],
            [InlineButton(key="button.blacklist.appeal", callback="blacklist_appeal")],
            [InlineButton(key="button.back", callback="back_to_main")],
        ],
    ),
    "menu.knowledge": InlineMenu(
        key="menu.knowledge",
        title_key="menu.knowledge.title",
        buttons=[
            [InlineButton(key="button.knowledge.foundation", callback="menu:menu.knowledge.topics")],
            [InlineButton(key="button.knowledge.holidays", callback="menu:menu.holidays")],
            [InlineButton(key="button.back", callback="back_to_main")],
        ],
    ),
    "menu.knowledge.topics": InlineMenu(
        key="menu.knowledge.topics",
        title_key="menu.knowledge.topics.title",
        buttons=[
            [InlineButton(key="button.docs.tauhid", callback="docs_tauhid")],
            [InlineButton(key="button.docs.faith", callback="docs_faith")],
            [InlineButton(key="button.docs.fiqh", callback="docs_fiqh")],
            [InlineButton(key="button.docs.culture", callback="docs_culture")],
            [InlineButton(key="button.docs.portal", url=MEN_CHAT_URL)],
            [InlineButton(key="button.back", callback="menu:menu.knowledge")],
        ],
    ),
    "menu.contracts": InlineMenu(
        key="menu.contracts",
        title_key="menu.contracts.title",
        buttons=[
            [InlineButton(key="button.contracts.all", callback="all_contracts")],
            [InlineButton(key="button.contracts.find", callback="find_contract")],
            [InlineButton(key="button.contracts.create", callback="create_contract")],
            [InlineButton(key="button.contracts.stats", callback="contracts_stats")],
            [InlineButton(key="button.back", callback="menu:menu.my_cases")],
        ],
    ),
    "menu.courts": InlineMenu(
        key="menu.courts",
        title_key="menu.courts.title",
        buttons=[
            [InlineButton(key="button.courts.file", callback="courts:file")],
            [InlineButton(key="button.courts.opened", callback="courts:opened")],
            [InlineButton(key="button.courts.in_progress", callback="courts:in_progress")],
            [InlineButton(key="button.courts.closed", callback="courts:closed")],
            [InlineButton(key="button.back", callback="menu:menu.my_cases")],
        ],
    ),
    "menu.courts.chats": InlineMenu(
        key="menu.courts.chats",
        title_key="menu.courts.title",
        buttons=[
            [InlineButton(key="button.courts.file", callback="go_to_court")],
            [InlineButton(key="button.courts.opened", url=COURTS_OPENED_CHAT_URL)],
            [InlineButton(key="button.courts.closed", url=COURTS_CLOSED_CHAT_URL)],
            [InlineButton(key="button.courts.in_progress", url=COURTS_IN_PROGRESS_CHAT_URL)],
            [InlineButton(key="button.back", callback="menu:menu.my_cases")],
        ],
    ),
    "menu.courts.statuses": InlineMenu(
        key="menu.courts.statuses",
        title_key="menu.courts.statuses.title",
        buttons=[
            [InlineButton(key="button.courts.opened", callback="opened_cases")],
            [InlineButton(key="button.courts.closed", callback="closed_cases")],
            [InlineButton(key="button.courts.in_progress", callback="in_progress")],
            [InlineButton(key="button.courts.file", callback="go_to_court")],
            [InlineButton(key="button.back", callback="back_to_court")],
        ],
    ),
    "menu.meetings_chats": InlineMenu(
        key="menu.meetings_chats",
        title_key="menu.meetings_chats.title",
        buttons=[
            [InlineButton(key="button.meetings.open", callback="menu:menu.meetings")],
            [InlineButton(key="button.chat.men", url=MEN_CHAT_URL)],
            [InlineButton(key="button.chat.women", url=WOMEN_CHAT_URL)],
            [InlineButton(key="button.back", callback="back_to_main")],
        ],
    ),
    "menu.meetings": InlineMenu(
        key="menu.meetings",
        title_key="menu.meetings.title",
        buttons=[
            [InlineButton(key="button.meetings.idea", callback="meetings:idea")],
            [InlineButton(key="button.meetings.vote", callback="meetings:vote")],
            [InlineButton(key="button.meetings.admin", callback="meetings:admin")],
            [InlineButton(key="button.back", callback="menu:menu.meetings_chats")],
        ],
    ),
    "menu.good_deeds": InlineMenu(
        key="menu.good_deeds",
        title_key="menu.good_deeds.title",
        buttons=[
            [InlineButton(key="button.good_deeds.list", callback="good_deeds:list")],
            [InlineButton(key="button.good_deeds.add", callback="good_deeds:add")],
            [InlineButton(key="button.good_deeds.needy", callback="good_deeds:needy")],
            [InlineButton(key="button.good_deeds.city", callback="good_deeds:city")],
            [InlineButton(key="button.good_deeds.category", callback="good_deeds:category")],
            [InlineButton(key="button.good_deeds.my", callback="good_deeds:my")],
            [InlineButton(key="button.back", callback="back_to_main")],
        ],
    ),
    "menu.inheritance": InlineMenu(
        key="menu.inheritance",
        title_key="menu.inheritance.title",
        buttons=[
            [InlineButton(key="button.inheritance.calc", callback="inherit_calc")],
            [InlineButton(key="button.inheritance.guardian", callback="inherit_guardian")],
            [InlineButton(key="button.inheritance.document", callback="inherit_document")],
            [InlineButton(key="button.inheritance.ask", callback="inherit_ask")],
            [InlineButton(key="button.back", callback="menu:menu.my_cases")],
        ],
    ),
    "menu.holidays": InlineMenu(
        key="menu.holidays",
        title_key="menu.holidays.title",
        buttons=[
            [InlineButton(key="button.holiday.uraza", callback="holiday_uraza")],
            [InlineButton(key="button.holiday.kurban", callback="holiday_kurban")],
            [InlineButton(key="button.holiday.ramadan", callback="holiday_ramadan")],
            [InlineButton(key="button.holiday.hajj", callback="holiday_hajj")],
            [InlineButton(key="button.back", callback="menu:menu.knowledge")],
        ],
    ),
    "menu.nikah": InlineMenu(
        key="menu.nikah",
        title_key="menu.nikah.title",
        buttons=[
            [InlineButton(key="button.nikah.new", callback="nikah_new")],
            [InlineButton(key="button.nikah.my", callback="nikah_my")],
            [InlineButton(key="button.nikah.rules", callback="nikah_rules")],
            [InlineButton(key="button.my_cases.spouse_search", callback="menu:menu.spouse_search")],
            [InlineButton(key="button.nikah.ask", callback="nikah_ask")],
            [InlineButton(key="button.back", callback="menu:menu.my_cases")],
        ],
    ),
    "menu.spouse_search": InlineMenu(
        key="menu.spouse_search",
        title_key="menu.spouse_search.title",
        buttons=[
            [InlineButton(key="button.spouse.profile", callback="spouse_profile")],
            [InlineButton(key="button.spouse.search", callback="spouse_search")],
            [InlineButton(key="button.spouse.requests", callback="spouse_requests")],
            [InlineButton(key="button.spouse.rules", callback="spouse_rules")],
            [InlineButton(key="button.spouse.ask", callback="spouse_ask")],
            [InlineButton(key="button.back", callback="menu:menu.nikah")],
        ],
    ),
    "menu.zakat": InlineMenu(
        key="menu.zakat",
        title_key="menu.zakat.title",
        buttons=[
            [InlineButton(key="button.zakat.account", url=MEN_CHAT_URL)],
            [InlineButton(key="button.zakat.vote", url=MEN_CHAT_URL)],
            [InlineButton(key="button.zakat.info", url=MEN_CHAT_URL)],
            [InlineButton(key="button.back", callback="back_to_main")],
        ],
    ),
    "menu.committee": InlineMenu(
        key="menu.committee",
        title_key="menu.committee.title",
        buttons=[
            [InlineButton(key="button.committee.scholars", url=MEN_CHAT_URL)],
            [InlineButton(key="button.committee.leaders", url=MEN_CHAT_URL)],
            [InlineButton(key="button.committee.elders", url=MEN_CHAT_URL)],
            [InlineButton(key="button.committee.general", url=MEN_CHAT_URL)],
            [InlineButton(key="button.back", callback="back_to_main")],
        ],
    ),
    "menu.enforcement": InlineMenu(
        key="menu.enforcement",
        title_key="menu.enforcement.title",
        buttons=[
            [InlineButton(key="button.enforcement.open", callback="enforcement_open")],
            [InlineButton(key="button.back", callback="back_to_main")],
        ],
    ),
}

INLINE_MENU_BY_KEY = INLINE_MENU_DEFINITIONS


def build_reply_keyboard(lang_code: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_text(key, lang_code)) for key in row]
            for row in MAIN_MENU_LAYOUT
        ],
        resize_keyboard=True,
        input_field_placeholder=get_text("input.placeholder.question", lang_code),
    )


def resolve_menu_key(text: str, lang_code: str) -> Optional[str]:
    label_map = MENU_KEY_BY_LABEL_BY_LANGUAGE.get(lang_code)
    if label_map:
        key = label_map.get(text)
        if key:
            return key

    normalized = _normalize_menu_label(text)
    if normalized:
        normalized_map = MENU_KEY_BY_NORMALIZED_LABEL_BY_LANGUAGE.get(lang_code)
        if normalized_map:
            key = normalized_map.get(normalized)
            if key:
                return key

    for labels in MENU_KEY_BY_LABEL_BY_LANGUAGE.values():
        if text in labels:
            return labels[text]

    if normalized:
        for labels in MENU_KEY_BY_NORMALIZED_LABEL_BY_LANGUAGE.values():
            if normalized in labels:
                return labels[normalized]

    if text in INLINE_MENU_BY_KEY or text in MAIN_MENU_KEYS:
        return text
    return None


def build_inline_keyboard(menu: InlineMenu, lang_code: str) -> InlineKeyboardMarkup:
    keyboard: List[List[InlineKeyboardButton]] = []
    for row in menu.buttons:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=get_text(button.key, lang_code),
                    callback_data=button.callback,
                    url=button.url,
                )
                for button in row
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def show_welcome_menu(
    message: Message,
    *,
    is_new_user: bool,
    lang_code: str,
) -> None:
    full_name = (
        message.from_user.full_name
        or message.from_user.username
        or get_text("user.default_name", lang_code)
    )
    header_key = "welcome.new" if is_new_user else "welcome.back"
    header = get_text(header_key, lang_code, full_name=full_name)
    body = get_text("welcome.body", lang_code)
    await message.answer(
        f"{header}\n\n{body}",
        reply_markup=build_reply_keyboard(lang_code),
    )


@router.message(Command("menu"))
async def command_menu(
    message: Message,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    await show_welcome_menu(message, is_new_user=user_row is None, lang_code=lang_code)


@router.message(MenuKeyFilter(MAIN_MENU_KEYS))
async def handle_main_menu(
    message: Message,
    user_row: Optional[UserModel],
    menu_key: str,
    db: DB,
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if menu_key == "menu.enforcement":
        await show_shariah_control_menu(message, db=db, user_row=user_row)
        return
    menu = INLINE_MENU_BY_KEY.get(menu_key)
    if not menu:
        return

    if menu_key == "menu.inheritance" and lang_code == "ru":
        title_text = (
            "🪙 Наследство и завещания\n"
            "Рассчитайте доли наследников и подготовьте шариатское завещание.\n"
            "Обратите внимание: завещание действительно только если оно не нарушает доли наследников из Корана."
        )
    elif menu_key == "menu.nikah" and lang_code == "ru":
        title_text = (
            "👰🤵 Никях (шариатский брак)\n\n"
            "Я помогу оформить шариатский брак в соответствии с Исламом,\n"
            "с формированием договора и проверками условий.\n\n"
            "Пожалуйста, выберите, что вам нужно:"
        )
    elif menu_key == "menu.spouse_search" and lang_code == "ru":
        title_text = (
            "🌿 Знакомство и поиск супруга\n\n"
            "Заполните анкету и ищите кандидата/кандидатку для никаха.\n"
            "Фото лица запрещены. Общение — только с участием вали/махрама (или куратора)."
        )
    else:
        title_text = get_text(menu.title_key, lang_code)

    await message.answer(
        title_text,
        reply_markup=build_inline_keyboard(menu, lang_code),
        disable_web_page_preview=False,
    )


@router.callback_query(F.data.startswith("menu:"))
async def handle_menu_navigation(
    callback: CallbackQuery,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    menu_key = (callback.data or "").split(":", 1)[-1]
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    if menu_key == "menu.enforcement":
        await show_shariah_control_menu(callback, db=db, user_row=user_row)
        return
    menu = INLINE_MENU_BY_KEY.get(menu_key)
    if not menu:
        return
    if menu_key == "menu.inheritance" and lang_code == "ru":
        title_text = (
            "🪙 Наследство и завещания\n"
            "Рассчитайте доли наследников и подготовьте шариатское завещание.\n"
            "Обратите внимание: завещание действительно только если оно не нарушает доли наследников из Корана."
        )
    elif menu_key == "menu.nikah" and lang_code == "ru":
        title_text = (
            "👰🤵 Никях (шариатский брак)\n\n"
            "Я помогу оформить шариатский брак в соответствии с Исламом,\n"
            "с формированием договора и проверками условий.\n\n"
            "Пожалуйста, выберите, что вам нужно:"
        )
    elif menu_key == "menu.spouse_search" and lang_code == "ru":
        title_text = (
            "🌿 Знакомство и поиск супруга\n\n"
            "Заполните анкету и ищите кандидата/кандидатку для никаха.\n"
            "Фото лица запрещены. Общение — только с участием вали/махрама (или куратора)."
        )
    else:
        title_text = get_text(menu.title_key, lang_code)
    await callback.message.edit_text(
        title_text,
        reply_markup=build_inline_keyboard(menu, lang_code),
        disable_web_page_preview=False,
    )


@router.callback_query(F.data == "back_to_main")
async def handle_back_to_main(
    callback: CallbackQuery,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await callback.message.answer(
        get_text("menu.back.main", lang_code),
        reply_markup=build_reply_keyboard(lang_code),
    )
