from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot.handlers.comitee_common import is_cancel_command, user_language
from app.bot.states.comitee import ShariahAdminApplicationFlow
from app.infrastructure.database.db import DB
from app.infrastructure.database.models.user import UserModel
from app.infrastructure.database.tables.shariah_admin_applications import (
    ShariahAdminApplicationsTable,
)
from app.services.i18n.localization import get_text
from config.config import settings

logger = logging.getLogger(__name__)

router = Router(name="comitee.sharia_control")

ROLE_BUTTONS = {
    "shariah_observer": "рџ‘Ѓ РќР°Р±Р»СЋРґР°С‚РµР»СЊ",
    "tz_courts": "⚖ Контроль судов",
    "tz_contracts": "📜 Контроль договоров",
    "tz_good_deeds": "🤲 Контроль добрых дел",
    "tz_execution": "🧾 Контроль исполнения",
    "shariah_chief": "👑 Главный контролер",
}

EDUCATION_OPTIONS = [
    ("medrese", "🕌 Медресе"),
    ("university", "🎓 Исламский университет"),
    ("private", "📚 Частное обучение"),
    ("self", "📖 Самообразование"),
    ("other", "➕ Другое"),
]

KNOWLEDGE_AREAS = [
    ("fiqh", "⚖ Фикх"),
    ("contracts", "📜 Договоры"),
    ("courts", "🏛 Судебные вопросы"),
    ("zakat", "🤲 Закят / садака"),
    ("execution", "🧾 Исполнение решений"),
    ("observer", "👁 Контроль без решений"),
]


def _top_countries() -> list[str]:
    bot_cfg = getattr(settings, "bot", None)
    raw = getattr(bot_cfg, "SHARIAH_TOP_COUNTRIES", None) if bot_cfg else None
    if isinstance(raw, (list, tuple)):
        return [str(item).strip() for item in raw if str(item).strip()]
    return [
        "Россия",
        "Казахстан",
        "Узбекистан",
        "Кыргызстан",
        "Таджикистан",
        "Турция",
        "Саудовская Аравия",
        "ОАЭ",
        "Египет",
        "Индонезия",
    ]


def _experience_limit() -> int:
    bot_cfg = getattr(settings, "bot", None)
    raw = getattr(bot_cfg, "SHARIAH_EXPERIENCE_MAX", None) if bot_cfg else None
    try:
        return int(raw) if raw else 400
    except (TypeError, ValueError):
        return 400


def _build_countries_keyboard(countries: Iterable[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for country in countries:
        rows.append([InlineKeyboardButton(text=country, callback_data=f"shariah:country:{country}")])
    rows.append([InlineKeyboardButton(text="➕ Другая страна", callback_data="shariah:country:other")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _build_education_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"shariah:edu:{value}")]
        for value, label in EDUCATION_OPTIONS
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _build_areas_keyboard(selected: set[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for value, label in KNOWLEDGE_AREAS:
        prefix = "✅ " if value in selected else ""
        rows.append([InlineKeyboardButton(text=f"{prefix}{label}", callback_data=f"shariah:area:{value}")])
    rows.append([InlineKeyboardButton(text="Готово", callback_data="shariah:areas:done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _application_status_label(status: str) -> str:
    mapping = {
        "pending_intro": "Ожидает знакомства",
        "meeting_scheduled": "Знакомство назначено",
        "approved": "Назначен админом",
        "observer": "Назначен наблюдателем",
        "rejected": "Отказано",
    }
    return mapping.get(status, status or "-")


async def _fetch_admin_roles(db: DB, telegram_id: int) -> list[str]:
    rows = await db.documents.connection.fetchmany(
        sql=(
            """
            SELECT r.slug
            FROM admin_accounts AS a
            JOIN admin_account_roles AS ar ON ar.admin_account_id = a.id
            JOIN roles AS r ON r.id = ar.role_id
            WHERE a.telegram_id = %s AND COALESCE(a.is_active, TRUE) = TRUE
            """
        ),
        params=(telegram_id,),
    )
    return [str(row.get("slug") or "") for row in rows.as_dicts() if row.get("slug")]


async def build_shariah_control_keyboard(
    *,
    db: DB,
    telegram_id: int,
    include_back: bool = True,
) -> InlineKeyboardMarkup:
    roles = set(await _fetch_admin_roles(db, telegram_id))
    rows: list[list[InlineKeyboardButton]] = []
    for slug, label in ROLE_BUTTONS.items():
        if slug in roles:
            rows.append([InlineKeyboardButton(text=label, callback_data=f"shariah:section:{slug}")])
    rows.append([InlineKeyboardButton(text="🔐 Подать заявку в админы", callback_data="shariah:apply")])
    rows.append([InlineKeyboardButton(text="📄 Мой статус", callback_data="shariah:status")])
    if include_back:
        rows.append([InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def show_shariah_control_menu(
    message_or_callback: Message | CallbackQuery,
    *,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message_or_callback.from_user)
    text = get_text("shariah.menu.title", lang_code)
    keyboard = await build_shariah_control_keyboard(
        db=db,
        telegram_id=message_or_callback.from_user.id,
        include_back=True,
    )
    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.answer(text, reply_markup=keyboard)
    else:
        await message_or_callback.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "shariah:status")
async def handle_shariah_status(
    callback: CallbackQuery,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    application = await db.shariah_admin_applications.get_latest_by_user(
        user_id=callback.from_user.id
    )
    if not application:
        await callback.message.answer(get_text("shariah.status.none", lang_code))
        return
    status = _application_status_label(str(application.get("status") or ""))
    await callback.message.answer(
        get_text(
            "shariah.status.current",
            lang_code,
            status=status,
            app_id=application.get("id") or "-",
        )
    )


@router.callback_query(F.data.startswith("shariah:section:"))
async def handle_shariah_section(
    callback: CallbackQuery,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    section = (callback.data or "").split(":")[-1]
    label = ROLE_BUTTONS.get(section)
    if not label:
        await callback.message.answer(get_text("shariah.section.denied", lang_code))
        return
    url = None
    bot_cfg = getattr(settings, "bot", None)
    if bot_cfg:
        url = getattr(bot_cfg, "ADMIN_PANEL_URL", None) or getattr(bot_cfg, "admin_panel_url", None)
    if url:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🌐 Открыть веб-панель", url=str(url))]]
        )
        await callback.message.answer(
            get_text("shariah.section.open", lang_code, section=label),
            reply_markup=keyboard,
        )
    else:
        await callback.message.answer(get_text("shariah.section.no_url", lang_code, section=label))


@router.callback_query(F.data == "shariah:apply")
async def handle_shariah_apply_start(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    existing = await db.shariah_admin_applications.get_latest_by_user(
        user_id=callback.from_user.id
    )
    if existing and str(existing.get("status") or "") in {
        "pending_intro",
        "meeting_scheduled",
        "approved",
        "observer",
    }:
        status = _application_status_label(str(existing.get("status") or ""))
        await callback.message.answer(
            get_text("shariah.apply.exists", lang_code, status=status)
        )
        return
    await state.clear()
    await state.set_state(ShariahAdminApplicationFlow.waiting_for_name)
    await callback.message.answer(get_text("shariah.prompt.name", lang_code))


@router.message(ShariahAdminApplicationFlow.waiting_for_name)
async def handle_shariah_name(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("shariah.cancelled", lang_code))
        return
    name = (message.text or "").strip()
    if not name:
        await message.answer(get_text("shariah.prompt.name", lang_code))
        return
    await state.update_data(full_name=name)
    await state.set_state(ShariahAdminApplicationFlow.waiting_for_country)
    await message.answer(
        get_text("shariah.prompt.country", lang_code),
        reply_markup=_build_countries_keyboard(_top_countries()),
    )


@router.callback_query(ShariahAdminApplicationFlow.waiting_for_country, F.data.startswith("shariah:country:"))
async def handle_shariah_country(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    value = (callback.data or "").split(":", 2)[-1]
    if value == "other":
        await state.set_state(ShariahAdminApplicationFlow.waiting_for_country_custom)
        await callback.message.answer(get_text("shariah.prompt.country.custom", lang_code))
        return
    await state.update_data(country=value)
    await state.set_state(ShariahAdminApplicationFlow.waiting_for_city)
    await callback.message.answer(get_text("shariah.prompt.city", lang_code))


@router.message(ShariahAdminApplicationFlow.waiting_for_country_custom)
async def handle_shariah_country_custom(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("shariah.cancelled", lang_code))
        return
    country = (message.text or "").strip()
    if not country:
        await message.answer(get_text("shariah.prompt.country.custom", lang_code))
        return
    await state.update_data(country=country)
    await state.set_state(ShariahAdminApplicationFlow.waiting_for_city)
    await message.answer(get_text("shariah.prompt.city", lang_code))


@router.message(ShariahAdminApplicationFlow.waiting_for_city)
async def handle_shariah_city(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("shariah.cancelled", lang_code))
        return
    city = (message.text or "").strip()
    if not city:
        await message.answer(get_text("shariah.prompt.city", lang_code))
        return
    await state.update_data(city=city)
    await state.set_state(ShariahAdminApplicationFlow.waiting_for_education_place)
    await message.answer(
        get_text("shariah.prompt.education.place", lang_code),
        reply_markup=_build_education_keyboard(),
    )


@router.callback_query(
    ShariahAdminApplicationFlow.waiting_for_education_place, F.data.startswith("shariah:edu:")
)
async def handle_shariah_education_place(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    value = (callback.data or "").split(":")[-1]
    label_map = {key: label for key, label in EDUCATION_OPTIONS}
    if value not in label_map:
        await callback.message.answer(get_text("shariah.prompt.education.place", lang_code))
        return
    await state.update_data(education_place=label_map[value])
    await state.set_state(ShariahAdminApplicationFlow.waiting_for_education_completed)
    await callback.message.answer(
        get_text("shariah.prompt.education.completed", lang_code),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Да", callback_data="shariah:edu_done:yes")],
                [InlineKeyboardButton(text="❌ Нет", callback_data="shariah:edu_done:no")],
            ]
        ),
    )


@router.callback_query(
    ShariahAdminApplicationFlow.waiting_for_education_completed,
    F.data.startswith("shariah:edu_done:"),
)
async def handle_shariah_education_completed(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    value = (callback.data or "").split(":")[-1]
    if value not in {"yes", "no"}:
        await callback.message.answer(get_text("shariah.prompt.education.completed", lang_code))
        return
    completed = value == "yes"
    await state.update_data(education_completed=completed)
    if completed:
        await state.set_state(ShariahAdminApplicationFlow.waiting_for_education_details)
        await callback.message.answer(get_text("shariah.prompt.education.details", lang_code))
    else:
        await state.update_data(education_details=None)
        await state.set_state(ShariahAdminApplicationFlow.waiting_for_knowledge_areas)
        await callback.message.answer(
            get_text("shariah.prompt.knowledge", lang_code),
            reply_markup=_build_areas_keyboard(set()),
        )


@router.message(ShariahAdminApplicationFlow.waiting_for_education_details)
async def handle_shariah_education_details(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("shariah.cancelled", lang_code))
        return
    details = (message.text or "").strip()
    if not details:
        await message.answer(get_text("shariah.prompt.education.details", lang_code))
        return
    await state.update_data(education_details=details)
    await state.set_state(ShariahAdminApplicationFlow.waiting_for_knowledge_areas)
    await message.answer(
        get_text("shariah.prompt.knowledge", lang_code),
        reply_markup=_build_areas_keyboard(set()),
    )


@router.callback_query(ShariahAdminApplicationFlow.waiting_for_knowledge_areas, F.data.startswith("shariah:area:"))
async def handle_shariah_area_toggle(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    value = (callback.data or "").split(":")[-1]
    data = await state.get_data()
    selected = set(data.get("knowledge_areas") or [])
    if value in selected:
        selected.remove(value)
    else:
        selected.add(value)
    await state.update_data(knowledge_areas=list(selected))
    await callback.message.edit_reply_markup(reply_markup=_build_areas_keyboard(selected))


@router.callback_query(ShariahAdminApplicationFlow.waiting_for_knowledge_areas, F.data == "shariah:areas:done")
async def handle_shariah_areas_done(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    data = await state.get_data()
    selected = list(data.get("knowledge_areas") or [])
    if not selected:
        await callback.message.answer(get_text("shariah.prompt.knowledge", lang_code))
        return
    await state.set_state(ShariahAdminApplicationFlow.waiting_for_experience)
    await callback.message.answer(get_text("shariah.prompt.experience", lang_code, limit=_experience_limit()))


@router.message(ShariahAdminApplicationFlow.waiting_for_experience)
async def handle_shariah_experience(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("shariah.cancelled", lang_code))
        return
    experience = (message.text or "").strip()
    if not experience:
        await message.answer(get_text("shariah.prompt.experience", lang_code, limit=_experience_limit()))
        return
    max_len = _experience_limit()
    if len(experience) > max_len:
        await message.answer(get_text("shariah.prompt.experience.limit", lang_code, limit=max_len))
        return
    await state.update_data(experience=experience)
    await state.set_state(ShariahAdminApplicationFlow.waiting_for_responsibility)
    await message.answer(
        get_text("shariah.prompt.responsibility", lang_code),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🤲 Да, осознаю", callback_data="shariah:resp:yes")],
                [InlineKeyboardButton(text="❌ Нет", callback_data="shariah:resp:no")],
            ]
        ),
    )


@router.callback_query(
    ShariahAdminApplicationFlow.waiting_for_responsibility, F.data.startswith("shariah:resp:")
)
async def handle_shariah_responsibility(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    value = (callback.data or "").split(":")[-1]
    if value not in {"yes", "no"}:
        await callback.message.answer(get_text("shariah.prompt.responsibility", lang_code))
        return
    data = await state.get_data()
    responsibility = value == "yes"
    status = "pending_intro" if responsibility else "rejected"
    history_event = {
        "at": datetime.now(timezone.utc).isoformat(),
        "action": "submitted",
        "status": status,
        "actor_id": callback.from_user.id,
    }
    await db.shariah_admin_applications.create_application(
        user_id=callback.from_user.id,
        full_name=str(data.get("full_name") or ""),
        country=str(data.get("country") or ""),
        city=str(data.get("city") or ""),
        education_place=str(data.get("education_place") or ""),
        education_completed=bool(data.get("education_completed")),
        education_details=str(data.get("education_details") or "") or None,
        knowledge_areas=list(data.get("knowledge_areas") or []),
        experience=str(data.get("experience") or "") or None,
        responsibility_accepted=responsibility,
        status=status,
        history_event=history_event,
    )
    await state.clear()
    if responsibility:
        await callback.message.answer(get_text("shariah.submitted", lang_code))
    else:
        await callback.message.answer(get_text("shariah.auto_rejected", lang_code))
