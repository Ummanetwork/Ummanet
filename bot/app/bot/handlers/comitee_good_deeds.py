from __future__ import annotations

import json
import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot.handlers.comitee_common import is_cancel_command, user_language
from app.bot.states.comitee import (
    GoodDeedClarifyFlow,
    GoodDeedConfirmationFlow,
    GoodDeedCreateFlow,
    GoodDeedLocationFilterFlow,
    GoodDeedNeedyFlow,
)
from app.infrastructure.database.db import DB
from app.infrastructure.database.models.user import UserModel
from app.infrastructure.database.tables.good_deeds import GoodDeedsTable
from app.services.i18n.localization import get_text

logger = logging.getLogger(__name__)

router = Router(name="comitee.good_deeds")

PUBLIC_STATUSES = ("approved", "in_progress", "completed")
EDITABLE_STATUSES = ("pending", "needs_clarification")

HELP_TYPE_LABELS = {
    "sadaqa": "🤲 Садака",
    "zakat": "💠 Закят",
    "fitr": "🌙 Фитр",
    "general": "💛 Общая помощь",
}
APPROVED_CATEGORY_LABELS = {
    "zakat": "💠 Разрешено для закята",
    "fitr": "🌙 Разрешено для фитра",
    "sadaqa": "🤲 Только садака",
}


def _status_label(status: str) -> str:
    mapping = {
        "pending": "⏳ На проверке",
        "needs_clarification": "✏️ Требует уточнения",
        "approved": "✅ Одобрено",
        "in_progress": "🕊 В процессе",
        "completed": "🏁 Завершено",
        "rejected": "❌ Отклонено",
    }
    return mapping.get(status, status or "-")


def _parse_amount(value: Optional[str]) -> Optional[Decimal]:
    if value is None:
        return None
    text = value.strip().lower()
    if not text or text in {"-", "нет", "no", "n"}:
        return None
    text = text.replace(",", ".")
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _format_history(history: Any) -> str:
    if not history:
        return ""
    if isinstance(history, str):
        try:
            parsed = json.loads(history)
        except Exception:
            parsed = []
    else:
        parsed = history
    if isinstance(parsed, dict):
        items = [parsed]
    elif isinstance(parsed, list):
        items = [item for item in parsed if isinstance(item, dict)]
    else:
        items = []
    lines: list[str] = []
    for item in items:
        at = str(item.get("at") or "").strip() or "-"
        action = str(item.get("action") or "").strip()
        status = str(item.get("status") or "").strip()
        parts = [part for part in (action, status) if part]
        line = f"- {at}"
        if parts:
            line = f"{line}: {' / '.join(parts)}"
        lines.append(line)
    return "\n".join(lines)


def _deed_brief(deed: dict[str, Any]) -> str:
    title = deed.get("title") or "Без названия"
    city = deed.get("city") or "-"
    country = deed.get("country") or "-"
    status = _status_label(str(deed.get("status") or ""))
    return f"{title} — {city}, {country} ({status})"


def _needy_brief(needy: dict[str, Any]) -> str:
    p_type = needy.get("person_type") or "-"
    city = needy.get("city") or "-"
    country = needy.get("country") or "-"
    status = _status_label(str(needy.get("status") or ""))
    return f"{p_type} — {city}, {country} ({status})"


def _build_list_keyboard(items: Iterable[dict[str, Any]], prefix: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for item in items:
        item_id = int(item.get("id") or 0)
        label = item.get("title") or item.get("person_type") or f"#{item_id}"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"📌 {label}",
                    callback_data=f"{prefix}:{item_id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="↩️ Назад", callback_data="menu:menu.good_deeds")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _build_help_type_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=HELP_TYPE_LABELS["sadaqa"], callback_data="good_deeds:type:sadaqa")],
        [InlineKeyboardButton(text=HELP_TYPE_LABELS["zakat"], callback_data="good_deeds:type:zakat")],
        [InlineKeyboardButton(text=HELP_TYPE_LABELS["fitr"], callback_data="good_deeds:type:fitr")],
        [InlineKeyboardButton(text=HELP_TYPE_LABELS["general"], callback_data="good_deeds:type:general")],
    ]
    rows.append([InlineKeyboardButton(text="↩️ Назад", callback_data="menu:menu.good_deeds")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _build_category_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=APPROVED_CATEGORY_LABELS["zakat"], callback_data="good_deeds:cat:zakat")],
        [InlineKeyboardButton(text=APPROVED_CATEGORY_LABELS["fitr"], callback_data="good_deeds:cat:fitr")],
        [InlineKeyboardButton(text=APPROVED_CATEGORY_LABELS["sadaqa"], callback_data="good_deeds:cat:sadaqa")],
    ]
    rows.append([InlineKeyboardButton(text="↩️ Назад", callback_data="menu:menu.good_deeds")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "good_deeds:list")
async def handle_good_deeds_list(
    callback: CallbackQuery,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    deeds = await db.good_deeds.list_public_good_deeds(statuses=PUBLIC_STATUSES, limit=15)
    if not deeds:
        await callback.message.answer(get_text("good_deeds.list.empty", lang_code))
        return
    text = "🟢 Актуальные добрые дела:\n\n" + "\n".join(
        f"{idx + 1}. {_deed_brief(deed)}" for idx, deed in enumerate(deeds)
    )
    await callback.message.answer(text, reply_markup=_build_list_keyboard(deeds, "good_deeds:view"))


@router.callback_query(F.data.startswith("good_deeds:view:"))
async def handle_good_deed_view(
    callback: CallbackQuery,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    try:
        deed_id = int((callback.data or "").split(":")[-1])
    except ValueError:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    deed = await db.good_deeds.get_good_deed_by_id(good_deed_id=deed_id)
    if not deed:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    status = str(deed.get("status") or "")
    approved_category = deed.get("approved_category")
    category_label = (
        APPROVED_CATEGORY_LABELS.get(str(approved_category or ""), str(approved_category or "-"))
        if approved_category
        else "-"
    )
    amount = deed.get("amount")
    if isinstance(amount, Decimal):
        amount_text = f"{amount:.2f}"
    else:
        amount_text = str(amount or "-")
    review_comment = deed.get("review_comment") or "-"
    text = (
        f"🤲 Доброе дело №{deed.get('id')}\n"
        f"Название: {deed.get('title')}\n"
        f"Описание: {deed.get('description')}\n"
        f"Город: {deed.get('city')}\n"
        f"Страна: {deed.get('country')}\n"
        f"Тип помощи: {HELP_TYPE_LABELS.get(str(deed.get('help_type') or ''), deed.get('help_type'))}\n"
        f"Сумма: {amount_text}\n"
        f"Комментарий: {deed.get('comment') or '-'}\n"
        f"Статус: {_status_label(status)}\n"
        f"Категория: {category_label}\n"
        f"Комментарий проверки: {review_comment}"
    )
    history_text = _format_history(deed.get("history"))
    if history_text:
        text = f"{text}\n\n{get_text('good_deeds.history.title', lang_code)}\n{history_text}"
    buttons: list[list[InlineKeyboardButton]] = []
    if status in {"approved", "in_progress"}:
        buttons.append(
            [InlineKeyboardButton(text="✅ Подтвердить помощь", callback_data=f"good_deeds:confirm:{deed_id}")]
        )
    if int(deed.get("user_id") or 0) == callback.from_user.id and status == "needs_clarification":
        buttons.append(
            [InlineKeyboardButton(text="✏️ Уточнить", callback_data=f"good_deeds:clarify:{deed_id}")]
        )
    buttons.append([InlineKeyboardButton(text="↩️ Назад", callback_data="menu:menu.good_deeds")])
    await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data == "good_deeds:my")
async def handle_good_deeds_my(
    callback: CallbackQuery,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    deeds = await db.good_deeds.list_good_deeds_by_user(user_id=callback.from_user.id, limit=20)
    if not deeds:
        await callback.message.answer(get_text("good_deeds.my.empty", lang_code))
        return
    text = "📌 Мои добрые дела:\n\n" + "\n".join(
        f"{idx + 1}. {_deed_brief(deed)}" for idx, deed in enumerate(deeds)
    )
    await callback.message.answer(text, reply_markup=_build_list_keyboard(deeds, "good_deeds:view"))


@router.callback_query(F.data == "good_deeds:city")
async def handle_good_deeds_city_prompt(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    await state.set_state(GoodDeedLocationFilterFlow.waiting_for_query)
    await callback.message.answer(get_text("good_deeds.prompt.location", lang_code))


@router.message(GoodDeedLocationFilterFlow.waiting_for_query)
async def handle_good_deeds_city_search(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("good_deeds.cancelled", lang_code))
        return
    query = (message.text or "").strip()
    await state.clear()
    if not query:
        await message.answer(get_text("good_deeds.prompt.location", lang_code))
        return
    deeds = await db.good_deeds.search_public_good_deeds_by_location(
        statuses=PUBLIC_STATUSES,
        query=query,
        limit=15,
    )
    if not deeds:
        await message.answer(get_text("good_deeds.list.empty", lang_code))
        return
    text = f"📍 Добрые дела по запросу \"{query}\":\n\n" + "\n".join(
        f"{idx + 1}. {_deed_brief(deed)}" for idx, deed in enumerate(deeds)
    )
    await message.answer(text, reply_markup=_build_list_keyboard(deeds, "good_deeds:view"))


@router.callback_query(F.data == "good_deeds:category")
async def handle_good_deeds_category_menu(
    callback: CallbackQuery,
    user_row: Optional[UserModel],
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    await callback.message.answer(
        get_text("good_deeds.prompt.category", lang_code),
        reply_markup=_build_category_keyboard(),
    )


@router.callback_query(F.data.startswith("good_deeds:cat:"))
async def handle_good_deeds_category_list(
    callback: CallbackQuery,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    category = (callback.data or "").split(":")[-1]
    deeds = await db.good_deeds.list_public_good_deeds(
        statuses=PUBLIC_STATUSES,
        approved_category=category,
        limit=15,
    )
    if not deeds:
        await callback.message.answer(get_text("good_deeds.list.empty", lang_code))
        return
    text = f"{APPROVED_CATEGORY_LABELS.get(category, category)}:\n\n" + "\n".join(
        f"{idx + 1}. {_deed_brief(deed)}" for idx, deed in enumerate(deeds)
    )
    await callback.message.answer(text, reply_markup=_build_list_keyboard(deeds, "good_deeds:view"))


@router.callback_query(F.data == "good_deeds:needy")
async def handle_needy_list(
    callback: CallbackQuery,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    needy = await db.good_deeds.list_needy(statuses=("approved",), limit=15)
    if not needy:
        await callback.message.answer(get_text("good_deeds.needy.empty", lang_code))
    else:
        text = "🫶 Нуждающиеся:\n\n" + "\n".join(
            f"{idx + 1}. {_needy_brief(item)}" for idx, item in enumerate(needy)
        )
        keyboard = _build_list_keyboard(needy, "good_deeds:needy:view")
        await callback.message.answer(text, reply_markup=keyboard)
    await callback.message.answer(
        get_text("good_deeds.needy.add.prompt", lang_code),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="➕ Добавить нуждающегося", callback_data="good_deeds:needy:add")],
                [InlineKeyboardButton(text="↩️ Назад", callback_data="menu:menu.good_deeds")],
            ]
        ),
    )


@router.callback_query(F.data.startswith("good_deeds:needy:view:"))
async def handle_needy_view(
    callback: CallbackQuery,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    try:
        needy_id = int((callback.data or "").split(":")[-1])
    except ValueError:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    needy = await db.good_deeds.get_needy_by_id(needy_id=needy_id)
    if not needy:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    allow_zakat = bool(needy.get("allow_zakat"))
    allow_fitr = bool(needy.get("allow_fitr"))
    sadaqa_only = bool(needy.get("sadaqa_only"))
    fits = []
    if allow_zakat:
        fits.append("закят")
    if allow_fitr:
        fits.append("фитр")
    if sadaqa_only or not fits:
        fits.append("только садака")
    text = (
        f"🫶 Нуждающийся №{needy.get('id')}\n"
        f"Тип: {needy.get('person_type')}\n"
        f"Город: {needy.get('city')}\n"
        f"Страна: {needy.get('country')}\n"
        f"Причина: {needy.get('reason')}\n"
        f"Подходит для: {', '.join(fits)}\n"
        f"Комментарий: {needy.get('comment') or '-'}\n"
        f"Статус: {_status_label(str(needy.get('status') or ''))}"
    )
    await callback.message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="↩️ Назад", callback_data="menu:menu.good_deeds")]]
        ),
    )


@router.callback_query(F.data == "good_deeds:add")
async def handle_good_deed_add_start(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    await state.clear()
    await state.set_state(GoodDeedCreateFlow.waiting_for_title)
    await callback.message.answer(get_text("good_deeds.prompt.title", lang_code))


@router.message(GoodDeedCreateFlow.waiting_for_title)
async def handle_good_deed_title(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("good_deeds.cancelled", lang_code))
        return
    title = (message.text or "").strip()
    if not title:
        await message.answer(get_text("good_deeds.prompt.title", lang_code))
        return
    await state.update_data(title=title)
    await state.set_state(GoodDeedCreateFlow.waiting_for_description)
    await message.answer(get_text("good_deeds.prompt.description", lang_code))


@router.message(GoodDeedCreateFlow.waiting_for_description)
async def handle_good_deed_description(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("good_deeds.cancelled", lang_code))
        return
    description = (message.text or "").strip()
    if not description:
        await message.answer(get_text("good_deeds.prompt.description", lang_code))
        return
    await state.update_data(description=description)
    await state.set_state(GoodDeedCreateFlow.waiting_for_city)
    await message.answer(get_text("good_deeds.prompt.city", lang_code))


@router.message(GoodDeedCreateFlow.waiting_for_city)
async def handle_good_deed_city(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("good_deeds.cancelled", lang_code))
        return
    city = (message.text or "").strip()
    if not city:
        await message.answer(get_text("good_deeds.prompt.city", lang_code))
        return
    await state.update_data(city=city)
    await state.set_state(GoodDeedCreateFlow.waiting_for_country)
    await message.answer(get_text("good_deeds.prompt.country", lang_code))


@router.message(GoodDeedCreateFlow.waiting_for_country)
async def handle_good_deed_country(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("good_deeds.cancelled", lang_code))
        return
    country = (message.text or "").strip()
    if not country:
        await message.answer(get_text("good_deeds.prompt.country", lang_code))
        return
    await state.update_data(country=country)
    await state.set_state(GoodDeedCreateFlow.waiting_for_help_type)
    await message.answer(get_text("good_deeds.prompt.type", lang_code), reply_markup=_build_help_type_keyboard())


@router.callback_query(GoodDeedCreateFlow.waiting_for_help_type, F.data.startswith("good_deeds:type:"))
async def handle_good_deed_help_type(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    help_type = (callback.data or "").split(":")[-1]
    if help_type not in HELP_TYPE_LABELS:
        await callback.message.answer(get_text("good_deeds.prompt.type", lang_code))
        return
    await state.update_data(help_type=help_type)
    await state.set_state(GoodDeedCreateFlow.waiting_for_amount)
    await callback.message.answer(get_text("good_deeds.prompt.amount", lang_code))


@router.message(GoodDeedCreateFlow.waiting_for_amount)
async def handle_good_deed_amount(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("good_deeds.cancelled", lang_code))
        return
    amount = _parse_amount(message.text)
    await state.update_data(amount=amount)
    await state.set_state(GoodDeedCreateFlow.waiting_for_comment)
    await message.answer(get_text("good_deeds.prompt.comment", lang_code))


@router.message(GoodDeedCreateFlow.waiting_for_comment)
async def handle_good_deed_comment(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("good_deeds.cancelled", lang_code))
        return
    comment = (message.text or "").strip()
    if comment == "-":
        comment = ""
    await state.update_data(comment=comment)
    data = await state.get_data()
    summary = (
        "Проверьте данные:\n\n"
        f"Название: {data.get('title')}\n"
        f"Описание: {data.get('description')}\n"
        f"Город: {data.get('city')}\n"
        f"Страна: {data.get('country')}\n"
        f"Тип помощи: {HELP_TYPE_LABELS.get(str(data.get('help_type') or ''), data.get('help_type'))}\n"
        f"Сумма: {data.get('amount') or '-'}\n"
        f"Комментарий: {data.get('comment') or '-'}"
    )
    await state.set_state(GoodDeedCreateFlow.waiting_for_confirm)
    await message.answer(
        summary,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Отправить на проверку", callback_data="good_deeds:submit")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="good_deeds:cancel")],
            ]
        ),
    )


@router.callback_query(GoodDeedCreateFlow.waiting_for_confirm, F.data == "good_deeds:cancel")
async def handle_good_deed_cancel(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    await state.clear()
    await callback.message.answer(get_text("good_deeds.cancelled", lang_code))


@router.callback_query(GoodDeedCreateFlow.waiting_for_confirm, F.data == "good_deeds:submit")
async def handle_good_deed_submit(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    data = await state.get_data()
    history_event = {
        "at": GoodDeedsTable.now_ts().isoformat(),
        "action": "created",
        "status": "pending",
        "actor_id": callback.from_user.id,
    }
    deed = await db.good_deeds.create_good_deed(
        user_id=callback.from_user.id,
        title=str(data.get("title") or ""),
        description=str(data.get("description") or ""),
        city=str(data.get("city") or ""),
        country=str(data.get("country") or ""),
        help_type=str(data.get("help_type") or ""),
        amount=data.get("amount"),
        comment=str(data.get("comment") or "") or None,
        status="pending",
        history_event=history_event,
    )
    await state.clear()
    await callback.message.answer(
        get_text("good_deeds.created", lang_code, deed_id=deed.get("id") or ""),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="↩️ Назад", callback_data="menu:menu.good_deeds")]]
        ),
    )


@router.callback_query(F.data == "good_deeds:needy:add")
async def handle_needy_add_start(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    await state.clear()
    await state.set_state(GoodDeedNeedyFlow.waiting_for_person_type)
    await callback.message.answer(
        get_text("good_deeds.needy.prompt.type", lang_code),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🙋 Человек", callback_data="good_deeds:needy:type:person")],
                [InlineKeyboardButton(text="👨‍👩‍👧‍👦 Семья", callback_data="good_deeds:needy:type:family")],
            ]
        ),
    )


@router.callback_query(GoodDeedNeedyFlow.waiting_for_person_type, F.data.startswith("good_deeds:needy:type:"))
async def handle_needy_type(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    person_type = (callback.data or "").split(":")[-1]
    if person_type not in {"person", "family"}:
        await callback.message.answer(get_text("good_deeds.needy.prompt.type", lang_code))
        return
    await state.update_data(person_type="Человек" if person_type == "person" else "Семья")
    await state.set_state(GoodDeedNeedyFlow.waiting_for_city)
    await callback.message.answer(get_text("good_deeds.needy.prompt.city", lang_code))


@router.message(GoodDeedNeedyFlow.waiting_for_city)
async def handle_needy_city(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("good_deeds.cancelled", lang_code))
        return
    city = (message.text or "").strip()
    if not city:
        await message.answer(get_text("good_deeds.needy.prompt.city", lang_code))
        return
    await state.update_data(city=city)
    await state.set_state(GoodDeedNeedyFlow.waiting_for_country)
    await message.answer(get_text("good_deeds.needy.prompt.country", lang_code))


@router.message(GoodDeedNeedyFlow.waiting_for_country)
async def handle_needy_country(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("good_deeds.cancelled", lang_code))
        return
    country = (message.text or "").strip()
    if not country:
        await message.answer(get_text("good_deeds.needy.prompt.country", lang_code))
        return
    await state.update_data(country=country)
    await state.set_state(GoodDeedNeedyFlow.waiting_for_reason)
    await message.answer(get_text("good_deeds.needy.prompt.reason", lang_code))


@router.message(GoodDeedNeedyFlow.waiting_for_reason)
async def handle_needy_reason(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("good_deeds.cancelled", lang_code))
        return
    reason = (message.text or "").strip()
    if not reason:
        await message.answer(get_text("good_deeds.needy.prompt.reason", lang_code))
        return
    await state.update_data(reason=reason)
    await state.set_state(GoodDeedNeedyFlow.waiting_for_zakat)
    await message.answer(
        get_text("good_deeds.needy.prompt.zakat", lang_code),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Да", callback_data="good_deeds:needy:zakat:yes")],
                [InlineKeyboardButton(text="❌ Нет", callback_data="good_deeds:needy:zakat:no")],
            ]
        ),
    )


@router.callback_query(GoodDeedNeedyFlow.waiting_for_zakat, F.data.startswith("good_deeds:needy:zakat:"))
async def handle_needy_zakat(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    value = (callback.data or "").split(":")[-1]
    if value not in {"yes", "no"}:
        await callback.message.answer(get_text("good_deeds.needy.prompt.zakat", lang_code))
        return
    await state.update_data(allow_zakat=value == "yes")
    await state.set_state(GoodDeedNeedyFlow.waiting_for_fitr)
    await callback.message.answer(
        get_text("good_deeds.needy.prompt.fitr", lang_code),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Да", callback_data="good_deeds:needy:fitr:yes")],
                [InlineKeyboardButton(text="❌ Нет", callback_data="good_deeds:needy:fitr:no")],
            ]
        ),
    )


@router.callback_query(GoodDeedNeedyFlow.waiting_for_fitr, F.data.startswith("good_deeds:needy:fitr:"))
async def handle_needy_fitr(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    value = (callback.data or "").split(":")[-1]
    if value not in {"yes", "no"}:
        await callback.message.answer(get_text("good_deeds.needy.prompt.fitr", lang_code))
        return
    await state.update_data(allow_fitr=value == "yes")
    await state.set_state(GoodDeedNeedyFlow.waiting_for_comment)
    await callback.message.answer(get_text("good_deeds.needy.prompt.comment", lang_code))


@router.message(GoodDeedNeedyFlow.waiting_for_comment)
async def handle_needy_comment(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("good_deeds.cancelled", lang_code))
        return
    comment = (message.text or "").strip()
    if comment == "-":
        comment = ""
    await state.update_data(comment=comment)
    data = await state.get_data()
    allow_zakat = bool(data.get("allow_zakat"))
    allow_fitr = bool(data.get("allow_fitr"))
    sadaqa_only = not allow_zakat and not allow_fitr
    await state.update_data(sadaqa_only=sadaqa_only)
    summary = (
        "Проверьте данные:\n\n"
        f"Тип: {data.get('person_type')}\n"
        f"Город: {data.get('city')}\n"
        f"Страна: {data.get('country')}\n"
        f"Причина: {data.get('reason')}\n"
        f"Закят: {'да' if allow_zakat else 'нет'}\n"
        f"Фитр: {'да' if allow_fitr else 'нет'}\n"
        f"Только садака: {'да' if sadaqa_only else 'нет'}\n"
        f"Комментарий: {data.get('comment') or '-'}"
    )
    await state.set_state(GoodDeedNeedyFlow.waiting_for_confirm)
    await message.answer(
        summary,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Отправить на проверку", callback_data="good_deeds:needy:submit")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="good_deeds:cancel")],
            ]
        ),
    )


@router.callback_query(GoodDeedNeedyFlow.waiting_for_confirm, F.data == "good_deeds:needy:submit")
async def handle_needy_submit(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    data = await state.get_data()
    history_event = {
        "at": GoodDeedsTable.now_ts().isoformat(),
        "action": "created",
        "status": "pending",
        "actor_id": callback.from_user.id,
    }
    await db.good_deeds.create_needy(
        created_by_user_id=callback.from_user.id,
        person_type=str(data.get("person_type") or ""),
        city=str(data.get("city") or ""),
        country=str(data.get("country") or ""),
        reason=str(data.get("reason") or ""),
        allow_zakat=bool(data.get("allow_zakat")),
        allow_fitr=bool(data.get("allow_fitr")),
        sadaqa_only=bool(data.get("sadaqa_only")),
        comment=str(data.get("comment") or "") or None,
        status="pending",
        history_event=history_event,
    )
    await state.clear()
    await callback.message.answer(
        get_text("good_deeds.needy.created", lang_code),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="↩️ Назад", callback_data="menu:menu.good_deeds")]]
        ),
    )


@router.callback_query(GoodDeedNeedyFlow.waiting_for_confirm, F.data == "good_deeds:cancel")
async def handle_needy_cancel(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    await state.clear()
    await callback.message.answer(get_text("good_deeds.cancelled", lang_code))


@router.callback_query(F.data.startswith("good_deeds:confirm:"))
async def handle_good_deed_confirm_start(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    try:
        deed_id = int((callback.data or "").split(":")[-1])
    except ValueError:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    deed = await db.good_deeds.get_good_deed_by_id(good_deed_id=deed_id)
    if not deed:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    status = str(deed.get("status") or "")
    if status not in {"approved", "in_progress"}:
        await callback.message.answer(get_text("good_deeds.confirm.not_allowed", lang_code))
        return
    await state.clear()
    await state.set_state(GoodDeedConfirmationFlow.waiting_for_text)
    await state.update_data(good_deed_id=deed_id)
    await callback.message.answer(get_text("good_deeds.confirm.prompt.text", lang_code))


@router.message(GoodDeedConfirmationFlow.waiting_for_text)
async def handle_good_deed_confirm_text(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("good_deeds.cancelled", lang_code))
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer(get_text("good_deeds.confirm.prompt.text", lang_code))
        return
    await state.update_data(text=text)
    await state.set_state(GoodDeedConfirmationFlow.waiting_for_attachment)
    await message.answer(get_text("good_deeds.confirm.prompt.attachment", lang_code))


@router.message(GoodDeedConfirmationFlow.waiting_for_attachment)
async def handle_good_deed_confirm_attachment(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("good_deeds.cancelled", lang_code))
        return
    data = await state.get_data()
    attachment: dict[str, Any] | None = None
    if message.document:
        attachment = GoodDeedsTable.serialize_attachment(
            file_id=message.document.file_id,
            filename=message.document.file_name,
            mime_type=message.document.mime_type,
            link=None,
        )
    elif message.photo:
        photo = message.photo[-1]
        attachment = GoodDeedsTable.serialize_attachment(
            file_id=photo.file_id,
            filename="photo.jpg",
            mime_type="image/jpeg",
            link=None,
        )
    elif message.video:
        attachment = GoodDeedsTable.serialize_attachment(
            file_id=message.video.file_id,
            filename=message.video.file_name or "video.mp4",
            mime_type=message.video.mime_type,
            link=None,
        )
    else:
        text = (message.text or "").strip()
        if text and text.startswith(("http://", "https://")):
            attachment = GoodDeedsTable.serialize_attachment(
                file_id=None,
                filename=None,
                mime_type=None,
                link=text,
            )
        elif text and text != "-":
            attachment = GoodDeedsTable.serialize_attachment(
                file_id=None,
                filename=None,
                mime_type=None,
                link=text,
            )
    good_deed_id = int(data.get("good_deed_id") or 0)
    if good_deed_id <= 0:
        await state.clear()
        await message.answer(get_text("good_deeds.confirm.error", lang_code))
        return
    await db.good_deeds.create_confirmation(
        good_deed_id=good_deed_id,
        created_by_user_id=message.from_user.id,
        text=str(data.get("text") or ""),
        attachment=attachment,
        status="pending",
    )
    await db.good_deeds.update_good_deed_status(
        good_deed_id=good_deed_id,
        status="in_progress",
    )
    await db.good_deeds.append_good_deed_history(
        good_deed_id=good_deed_id,
        event={
            "at": GoodDeedsTable.now_ts().isoformat(),
            "action": "confirmation_submitted",
            "status": "in_progress",
            "actor_id": message.from_user.id,
        },
    )
    await state.clear()
    await message.answer(get_text("good_deeds.confirm.saved", lang_code))


@router.callback_query(F.data.startswith("good_deeds:clarify:"))
async def handle_good_deed_clarify_start(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    try:
        deed_id = int((callback.data or "").split(":")[-1])
    except ValueError:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    deed = await db.good_deeds.get_good_deed_by_id(good_deed_id=deed_id)
    if not deed:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    if int(deed.get("user_id") or 0) != callback.from_user.id:
        await callback.message.answer(get_text("good_deeds.confirm.not_allowed", lang_code))
        return
    await state.clear()
    await state.set_state(GoodDeedClarifyFlow.waiting_for_text)
    await state.update_data(good_deed_id=deed_id)
    await callback.message.answer(get_text("good_deeds.clarify.prompt.text", lang_code))


@router.message(GoodDeedClarifyFlow.waiting_for_text)
async def handle_good_deed_clarify_text(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("good_deeds.cancelled", lang_code))
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer(get_text("good_deeds.clarify.prompt.text", lang_code))
        return
    await state.update_data(text=text)
    await state.set_state(GoodDeedClarifyFlow.waiting_for_attachment)
    await message.answer(get_text("good_deeds.clarify.prompt.attachment", lang_code))


@router.message(GoodDeedClarifyFlow.waiting_for_attachment)
async def handle_good_deed_clarify_attachment(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("good_deeds.cancelled", lang_code))
        return
    data = await state.get_data()
    attachment: dict[str, Any] | None = None
    if message.document:
        attachment = GoodDeedsTable.serialize_attachment(
            file_id=message.document.file_id,
            filename=message.document.file_name,
            mime_type=message.document.mime_type,
            link=None,
        )
    elif message.photo:
        photo = message.photo[-1]
        attachment = GoodDeedsTable.serialize_attachment(
            file_id=photo.file_id,
            filename="photo.jpg",
            mime_type="image/jpeg",
            link=None,
        )
    elif message.video:
        attachment = GoodDeedsTable.serialize_attachment(
            file_id=message.video.file_id,
            filename=message.video.file_name or "video.mp4",
            mime_type=message.video.mime_type,
            link=None,
        )
    else:
        text = (message.text or "").strip()
        if text and text.startswith(("http://", "https://")):
            attachment = GoodDeedsTable.serialize_attachment(
                file_id=None,
                filename=None,
                mime_type=None,
                link=text,
            )
        elif text and text != "-":
            attachment = GoodDeedsTable.serialize_attachment(
                file_id=None,
                filename=None,
                mime_type=None,
                link=text,
            )
    good_deed_id = int(data.get("good_deed_id") or 0)
    if good_deed_id <= 0:
        await state.clear()
        await message.answer(get_text("good_deeds.confirm.error", lang_code))
        return
    await db.good_deeds.update_good_deed_clarification(
        good_deed_id=good_deed_id,
        text=str(data.get("text") or ""),
        attachment=attachment,
    )
    await db.good_deeds.update_good_deed_status(
        good_deed_id=good_deed_id,
        status="pending",
        review_comment=None,
    )
    await db.good_deeds.append_good_deed_history(
        good_deed_id=good_deed_id,
        event={
            "at": GoodDeedsTable.now_ts().isoformat(),
            "action": "clarification_sent",
            "status": "pending",
            "actor_id": message.from_user.id,
        },
    )
    await state.clear()
    await message.answer(get_text("good_deeds.clarify.saved", lang_code))
