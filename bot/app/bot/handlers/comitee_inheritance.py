from __future__ import annotations

import logging
import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.bot.states.comitee import (
    InheritanceAskFlow,
    InheritanceCalcFlow,
    InheritanceGuardianFlow,
    InheritanceWasiyaFlow,
)
from app.infrastructure.database.db import DB
from app.infrastructure.database.models.user import UserModel
from app.services.inheritance.calculator import (
    INHERITANCE_MAX_RELATIVES,
    InheritanceInput,
    format_money,
    inheritance_currency_hint,
    parse_count,
    parse_money,
    parse_money_allow_zero,
    render_inheritance_calculation,
)
from app.services.i18n.localization import get_text
from app.services.scholar_requests.service import (
    MAX_ATTACHMENTS,
    ScholarAttachment,
    ScholarRequestDraft,
    build_forward_text,
    build_request_payload,
    build_request_summary,
    forward_request_to_group,
    persist_request_to_documents,
)
from app.services.work_items.service import create_work_item

from .comitee_common import edit_or_send_callback, is_cancel_command, user_language
from .comitee_menu import INLINE_MENU_BY_KEY, build_inline_keyboard
from .comitee_questions import set_pending_question

logger = logging.getLogger(__name__)

router = Router(name="comitee.inheritance")

inheritance_last_calc: Dict[int, Dict[str, Any]] = {}
inheritance_guardian_last_draft: Dict[int, Dict[str, Any]] = {}
inheritance_scholar_attachments: Dict[int, List[ScholarAttachment]] = {}


def _inheritance_action_keyboard(lang_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💾 Сохранить расчёт", callback_data="inherit_save_calc")],
            [InlineKeyboardButton(text="📄 Получить документ", callback_data="inherit_doc_shares")],
            [
                InlineKeyboardButton(
                    text=get_text("button.ask.scholars", lang_code),
                    callback_data="inherit_calc_ask",
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("button.back", lang_code),
                    callback_data="menu:menu.inheritance",
                )
            ],
        ]
    )


def _inheritance_cancel_keyboard(lang_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="inherit_cancel")],
            [
                InlineKeyboardButton(
                    text=get_text("button.back", lang_code),
                    callback_data="menu:menu.inheritance",
                )
            ],
        ]
    )


@router.callback_query(F.data == "inherit_cancel")
async def handle_inheritance_cancel(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await state.clear()
    menu = INLINE_MENU_BY_KEY["menu.inheritance"]
    await edit_or_send_callback(
        callback,
        get_text(menu.title_key, lang_code),
        reply_markup=build_inline_keyboard(menu, lang_code),
    )


@router.callback_query(F.data == "inherit_calc")
async def handle_inheritance_calc_start(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await state.clear()
    await state.set_state(InheritanceCalcFlow.waiting_for_mode)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚰️ Умер человек (я рассчитываю его наследство)",
                    callback_data="inherit_mode:deceased",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🙋‍♂️ Я готовлю своё завещание",
                    callback_data="inherit_mode:self",
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("button.back", lang_code),
                    callback_data="menu:menu.inheritance",
                )
            ],
        ]
    )
    await edit_or_send_callback(callback, "Кто вы относительно наследства?", reply_markup=keyboard)


@router.callback_query(F.data.startswith("inherit_mode:"))
async def handle_inheritance_mode_selected(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    mode = (callback.data or "").split(":", 1)[-1].strip().lower()
    if mode not in {"deceased", "self"}:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    await callback.answer()
    await state.update_data(inherit_mode=mode)
    await state.set_state(InheritanceCalcFlow.waiting_for_non_muslim)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="❌ Нет", callback_data="inherit_nonmuslim:no"),
                InlineKeyboardButton(text="⚠️ Да", callback_data="inherit_nonmuslim:yes"),
            ],
            [InlineKeyboardButton(text="🤷 Не знаю", callback_data="inherit_nonmuslim:unknown")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="inherit_cancel")],
        ]
    )
    await edit_or_send_callback(
        callback,
        "Есть ли среди умершего или наследников неверующие?",
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith("inherit_nonmuslim:"))
async def handle_inheritance_nonmuslim_selected(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    value = (callback.data or "").split(":", 1)[-1].strip().lower()
    if value not in {"no", "yes", "unknown"}:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return

    await callback.answer()
    await state.update_data(inherit_nonmuslim=value)
    await state.set_state(InheritanceCalcFlow.waiting_for_deceased_gender)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👨 Мужчина", callback_data="inherit_gender:male"),
                InlineKeyboardButton(text="👩 Женщина", callback_data="inherit_gender:female"),
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="inherit_cancel")],
        ]
    )
    await edit_or_send_callback(callback, "Пол умершего/завещателя:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("inherit_gender:"))
async def handle_inheritance_gender_selected(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    gender = (callback.data or "").split(":", 1)[-1].strip().lower()
    if gender not in {"male", "female"}:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    await callback.answer()
    await state.update_data(inherit_gender=gender)
    await state.set_state(InheritanceCalcFlow.waiting_for_spouse)

    if gender == "male":
        spouse_buttons = [
            [InlineKeyboardButton(text="👩‍🦰 Жена", callback_data="inherit_spouse:wife")],
            [InlineKeyboardButton(text="❌ Нет", callback_data="inherit_spouse:none")],
        ]
    else:
        spouse_buttons = [
            [InlineKeyboardButton(text="👨‍🦰 Муж", callback_data="inherit_spouse:husband")],
            [InlineKeyboardButton(text="❌ Нет", callback_data="inherit_spouse:none")],
        ]

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=spouse_buttons + [[InlineKeyboardButton(text="❌ Отмена", callback_data="inherit_cancel")]]
    )
    await edit_or_send_callback(callback, "Супруг(а) в живых?", reply_markup=keyboard)


@router.callback_query(F.data.startswith("inherit_spouse:"))
async def handle_inheritance_spouse_selected(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    spouse = (callback.data or "").split(":", 1)[-1].strip().lower()
    if spouse not in {"wife", "husband", "none"}:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    await callback.answer()
    await state.update_data(inherit_spouse=spouse)
    await state.set_state(InheritanceCalcFlow.waiting_for_sons)
    await callback.message.answer(
        f"👦 Сыновья: введите число от 0 до {INHERITANCE_MAX_RELATIVES}.\n\nДля отмены отправьте /cancel.",
        reply_markup=_inheritance_cancel_keyboard(lang_code),
    )


@router.message(InheritanceCalcFlow.waiting_for_sons)
async def handle_inheritance_sons(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        menu = INLINE_MENU_BY_KEY["menu.inheritance"]
        await message.answer(get_text(menu.title_key, lang_code), reply_markup=build_inline_keyboard(menu, lang_code))
        return
    value = parse_count(message.text)
    if value is None:
        await message.answer(f"Введите целое число от 0 до {INHERITANCE_MAX_RELATIVES}.")
        return
    await state.update_data(inherit_sons=value)
    await state.set_state(InheritanceCalcFlow.waiting_for_daughters)
    await message.answer(
        f"👧 Дочери: введите число от 0 до {INHERITANCE_MAX_RELATIVES}.\n\nДля отмены отправьте /cancel.",
        reply_markup=_inheritance_cancel_keyboard(lang_code),
    )


@router.message(InheritanceCalcFlow.waiting_for_daughters)
async def handle_inheritance_daughters(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        menu = INLINE_MENU_BY_KEY["menu.inheritance"]
        await message.answer(get_text(menu.title_key, lang_code), reply_markup=build_inline_keyboard(menu, lang_code))
        return
    value = parse_count(message.text)
    if value is None:
        await message.answer(f"Введите целое число от 0 до {INHERITANCE_MAX_RELATIVES}.")
        return
    await state.update_data(inherit_daughters=value)
    await state.set_state(InheritanceCalcFlow.waiting_for_father_alive)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да", callback_data="inherit_father:yes"),
                InlineKeyboardButton(text="Нет", callback_data="inherit_father:no"),
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="inherit_cancel")],
        ]
    )
    await message.answer("Отец жив?", reply_markup=keyboard)


@router.callback_query(F.data.startswith("inherit_father:"))
async def handle_inheritance_father_alive(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    raw = (callback.data or "").split(":", 1)[-1].strip().lower()
    if raw not in {"yes", "no"}:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    await callback.answer()
    await state.update_data(inherit_father_alive=(raw == "yes"))
    await state.set_state(InheritanceCalcFlow.waiting_for_mother_alive)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да", callback_data="inherit_mother:yes"),
                InlineKeyboardButton(text="Нет", callback_data="inherit_mother:no"),
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="inherit_cancel")],
        ]
    )
    await callback.message.answer("Мать жива?", reply_markup=keyboard)


@router.callback_query(F.data.startswith("inherit_mother:"))
async def handle_inheritance_mother_alive(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    raw = (callback.data or "").split(":", 1)[-1].strip().lower()
    if raw not in {"yes", "no"}:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    await callback.answer()
    await state.update_data(inherit_mother_alive=(raw == "yes"))
    await state.set_state(InheritanceCalcFlow.waiting_for_brothers)
    await callback.message.answer(
        f"👬 Родные братья: введите число от 0 до {INHERITANCE_MAX_RELATIVES}.\n\nДля отмены отправьте /cancel.",
        reply_markup=_inheritance_cancel_keyboard(lang_code),
    )


@router.message(InheritanceCalcFlow.waiting_for_brothers)
async def handle_inheritance_brothers(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        menu = INLINE_MENU_BY_KEY["menu.inheritance"]
        await message.answer(get_text(menu.title_key, lang_code), reply_markup=build_inline_keyboard(menu, lang_code))
        return
    value = parse_count(message.text)
    if value is None:
        await message.answer(f"Введите целое число от 0 до {INHERITANCE_MAX_RELATIVES}.")
        return
    await state.update_data(inherit_brothers=value)
    await state.set_state(InheritanceCalcFlow.waiting_for_sisters)
    await message.answer(
        f"👭 Родные сёстры: введите число от 0 до {INHERITANCE_MAX_RELATIVES}.\n\nДля отмены отправьте /cancel.",
        reply_markup=_inheritance_cancel_keyboard(lang_code),
    )


@router.message(InheritanceCalcFlow.waiting_for_sisters)
async def handle_inheritance_sisters(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        menu = INLINE_MENU_BY_KEY["menu.inheritance"]
        await message.answer(get_text(menu.title_key, lang_code), reply_markup=build_inline_keyboard(menu, lang_code))
        return
    value = parse_count(message.text)
    if value is None:
        await message.answer(f"Введите целое число от 0 до {INHERITANCE_MAX_RELATIVES}.")
        return
    await state.update_data(inherit_sisters=value)
    await state.set_state(InheritanceCalcFlow.waiting_for_estate_amount)
    await message.answer(
        "💰 Общая сумма имущества: введите число (можно с символом валюты, например: `500000 ₽`).\n\nДля отмены отправьте /cancel.",
        reply_markup=_inheritance_cancel_keyboard(lang_code),
        parse_mode="Markdown",
    )


@router.message(InheritanceCalcFlow.waiting_for_estate_amount)
async def handle_inheritance_estate_amount(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        menu = INLINE_MENU_BY_KEY["menu.inheritance"]
        await message.answer(get_text(menu.title_key, lang_code), reply_markup=build_inline_keyboard(menu, lang_code))
        return

    amount = parse_money(message.text)
    if amount is None:
        await message.answer("Введите сумму числом, например: `500000 ₽`.", parse_mode="Markdown")
        return

    deceased_gender = (await state.get_data()).get("inherit_gender")
    if deceased_gender not in {"male", "female"}:
        await state.clear()
        await message.answer("Не удалось определить данные расчёта. Попробуйте снова.")
        return

    currency = inheritance_currency_hint(message.text or "")
    await state.update_data(inherit_estate_amount=str(amount), inherit_currency=currency)
    await state.set_state(InheritanceCalcFlow.waiting_for_debts_amount)
    await message.answer(
        "📌 Долги умершего: введите сумму (0 — если нет/неизвестно).\n\nДля отмены отправьте /cancel.",
        reply_markup=_inheritance_cancel_keyboard(lang_code),
    )


@router.message(InheritanceCalcFlow.waiting_for_debts_amount)
async def handle_inheritance_debts_amount(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        menu = INLINE_MENU_BY_KEY["menu.inheritance"]
        await message.answer(get_text(menu.title_key, lang_code), reply_markup=build_inline_keyboard(menu, lang_code))
        return

    debts = parse_money_allow_zero(message.text)
    if debts is None:
        await message.answer(
            "Введите сумму долга числом, например: `0` или `150000`.",
            parse_mode="Markdown",
        )
        return

    data = await state.get_data()
    deceased_gender = data.get("inherit_gender")
    spouse = data.get("inherit_spouse", "none")
    sons = int(data.get("inherit_sons") or 0)
    daughters = int(data.get("inherit_daughters") or 0)
    father_alive = bool(data.get("inherit_father_alive", False))
    mother_alive = bool(data.get("inherit_mother_alive", False))
    brothers = int(data.get("inherit_brothers") or 0)
    sisters = int(data.get("inherit_sisters") or 0)
    estate_raw = data.get("inherit_estate_amount")
    currency = str(data.get("inherit_currency") or "")
    nonmuslim = str(data.get("inherit_nonmuslim") or "unknown")

    if deceased_gender not in {"male", "female"} or not estate_raw:
        await state.clear()
        await message.answer("Не удалось определить данные расчёта. Попробуйте снова.")
        return

    try:
        estate_amount = Decimal(str(estate_raw))
    except Exception:
        await state.clear()
        await message.answer("Не удалось определить сумму имущества. Попробуйте снова.")
        return

    net_amount = estate_amount - debts
    if net_amount <= 0:
        await state.clear()
        await message.answer(
            "После вычета долгов наследственная масса получилась ≤ 0. Уточните суммы или обратитесь к учёному.",
            reply_markup=_inheritance_cancel_keyboard(lang_code),
        )
        return

    extra_lines: list[str] = [
        f"💰 Имущество: {format_money(estate_amount, currency=currency)}",
        f"📌 Долги: {format_money(debts, currency=currency)}",
        f"✅ К распределению: {format_money(net_amount, currency=currency)}",
    ]
    if nonmuslim in {"yes", "unknown"}:
        extra_lines.append(
            "⚠️ Важно: наследство между мусульманином и неверующим не переходит; нужна консультация учёного."
        )

    input_data = InheritanceInput(
        deceased_gender=str(deceased_gender),
        spouse=str(spouse),
        sons=sons,
        daughters=daughters,
        father_alive=father_alive,
        mother_alive=mother_alive,
        brothers=brothers,
        sisters=sisters,
    )
    calc_text = render_inheritance_calculation(
        input_data=input_data,
        estate_amount=net_amount,
        currency=currency,
        extra_lines=extra_lines,
    )

    inheritance_last_calc[message.from_user.id] = {
        "text": calc_text,
        "estate_amount": str(estate_amount),
        "debts": str(debts),
        "net_amount": str(net_amount),
        "currency": currency,
        "nonmuslim": nonmuslim,
    }

    await state.clear()
    await message.answer(calc_text, reply_markup=_inheritance_action_keyboard(lang_code))


@router.callback_query(F.data == "inherit_save_calc")
async def handle_inheritance_save_calc(
    callback: CallbackQuery,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    _ = user_row
    payload = inheritance_last_calc.get(callback.from_user.id)
    if not payload:
        await callback.answer("Нет расчёта для сохранения. Сначала выполните расчёт.", show_alert=True)
        return

    filename = f"inheritance_{callback.from_user.id}_{uuid.uuid4().hex}.txt"
    name = f"Расчёт наследства {date.today().isoformat()}"
    try:
        await db.documents.add_document(
            filename=filename,
            user_id=callback.from_user.id,
            category="Inheritance",
            name=name,
            content=(payload["text"] or "").encode("utf-8"),
            doc_type="Inheritance",
        )
    except Exception:
        logger.exception("Failed to save inheritance calculation")
        await callback.answer("Не удалось сохранить расчёт.", show_alert=True)
        return

    await callback.answer("Расчёт сохранён.", show_alert=False)


@router.callback_query(F.data == "inherit_doc_shares")
async def handle_inheritance_document_shares(
    callback: CallbackQuery,
    user_row: Optional[UserModel],
) -> None:
    _ = user_row
    payload = inheritance_last_calc.get(callback.from_user.id)
    if not payload:
        await callback.answer("Сначала выполните расчёт наследства.", show_alert=True)
        return

    filename = f"inheritance_shares_{date.today().isoformat()}.txt"
    content = (payload["text"] or "").encode("utf-8")
    buffer = BufferedInputFile(content, filename=filename)
    await callback.answer()
    await callback.message.answer_document(
        document=buffer,
        caption="📄 Список наследников и долей (черновик)",
    )


@router.callback_query(F.data == "inherit_calc_ask")
async def handle_inheritance_calc_ask_scholar(
    callback: CallbackQuery,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    payload = inheritance_last_calc.get(callback.from_user.id)
    if not payload:
        await callback.answer("Сначала выполните расчёт наследства.", show_alert=True)
        return

    question = (
        "Прошу проверить расчёт наследства и указать, есть ли ошибки/исключения.\n\n"
        f"{payload.get('text') or ''}"
    ).strip()
    set_pending_question(callback.from_user.id, question)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("button.ask.scholars", lang_code),
                    callback_data=f"ask_{callback.from_user.id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("button.back", lang_code),
                    callback_data="menu:menu.inheritance",
                )
            ],
        ]
    )
    await callback.answer()
    await callback.message.answer("❓ Отправить этот расчёт учёному?", reply_markup=keyboard)


@router.callback_query(F.data == "inherit_document")
async def handle_inheritance_document_menu(
    callback: CallbackQuery,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🖋 Завещание (васият)", callback_data="inherit_wasiya")],
            [
                InlineKeyboardButton(
                    text="🛡 Доверенность хранителю",
                    callback_data="contract_tpl_download:partnership:wakala",
                )
            ],
            [InlineKeyboardButton(text="📑 Список наследников и долей", callback_data="inherit_doc_shares")],
            [InlineKeyboardButton(text=get_text("button.back", lang_code), callback_data="menu:menu.inheritance")],
        ]
    )
    await edit_or_send_callback(callback, "📄 Выберите тип документа:", reply_markup=keyboard)


@router.callback_query(F.data == "inherit_wasiya")
async def handle_inheritance_wasiya_start(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await state.clear()
    await state.set_state(InheritanceWasiyaFlow.waiting_for_estate_amount)
    await callback.message.answer(
        "🪙 Васият: введите общую сумму имущества (для проверки лимита 1/3).\n\nДля отмены отправьте /cancel.",
        reply_markup=_inheritance_cancel_keyboard(lang_code),
    )


@router.message(InheritanceWasiyaFlow.waiting_for_estate_amount)
async def handle_inheritance_wasiya_estate_amount(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        menu = INLINE_MENU_BY_KEY["menu.inheritance"]
        await message.answer(get_text(menu.title_key, lang_code), reply_markup=build_inline_keyboard(menu, lang_code))
        return

    amount = parse_money(message.text)
    if amount is None:
        await message.answer("Введите сумму числом, например: `500000 ₽`.", parse_mode="Markdown")
        return

    currency = inheritance_currency_hint(message.text or "")
    await state.update_data(wasiya_estate=str(amount), wasiya_currency=currency)
    await state.set_state(InheritanceWasiyaFlow.waiting_for_wasiya_amount)
    await message.answer(
        "Введите сумму, которую хотите завещать посторонним (васият).",
        reply_markup=_inheritance_cancel_keyboard(lang_code),
    )


@router.message(InheritanceWasiyaFlow.waiting_for_wasiya_amount)
async def handle_inheritance_wasiya_amount(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        menu = INLINE_MENU_BY_KEY["menu.inheritance"]
        await message.answer(get_text(menu.title_key, lang_code), reply_markup=build_inline_keyboard(menu, lang_code))
        return

    wasiya_amount = parse_money_allow_zero(message.text)
    if wasiya_amount is None:
        await message.answer("Введите сумму числом, например: `0` или `100000`.", parse_mode="Markdown")
        return

    data = await state.get_data()
    estate_raw = data.get("wasiya_estate")
    currency = str(data.get("wasiya_currency") or "")
    if not estate_raw:
        await state.clear()
        await message.answer("Не удалось определить сумму имущества. Попробуйте снова.")
        return

    try:
        estate_amount = Decimal(str(estate_raw))
    except Exception:
        await state.clear()
        await message.answer("Не удалось определить сумму имущества. Попробуйте снова.")
        return

    max_allowed = estate_amount / Decimal(3)
    if wasiya_amount > max_allowed:
        question = (
            "Васият превышает 1/3 имущества. Прошу уточнить, как правильно оформить в этом случае.\n\n"
            f"Имущество: {format_money(estate_amount, currency=currency)}\n"
            f"Васият: {format_money(wasiya_amount, currency=currency)}"
        )
        set_pending_question(message.from_user.id, question)
        await state.clear()
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✏️ Ввести суммы заново", callback_data="inherit_wasiya")],
                [
                    InlineKeyboardButton(
                        text=get_text("button.ask.scholars", lang_code),
                        callback_data=f"ask_{message.from_user.id}",
                    )
                ],
                [InlineKeyboardButton(text=get_text("button.back", lang_code), callback_data="inherit_document")],
            ]
        )
        await message.answer(
            "⚠️ Нельзя завещать более 1/3 имущества посторонним.\n"
            f"Максимум: {format_money(max_allowed, currency=currency)}\n"
            "Хотите исправить сумму или спросить учёного?",
            reply_markup=keyboard,
        )
        return

    await state.clear()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 Скачать шаблон (PDF)", callback_data="contract_tpl_download:gratis:wasiya")],
            [InlineKeyboardButton(text=get_text("button.back", lang_code), callback_data="inherit_document")],
        ]
    )
    await message.answer(
        "✅ Сумма васията не превышает 1/3.\n"
        f"Имущество: {format_money(estate_amount, currency=currency)}\n"
        f"Васият: {format_money(wasiya_amount, currency=currency)}",
        reply_markup=keyboard,
    )


def _render_guardian_summary(data: dict[str, Any]) -> str:
    name = (data.get("guardian_name") or "").strip() or "-"
    reason = (data.get("guardian_reason") or "").strip() or "-"
    scope = (data.get("guardian_scope") or "").strip() or "-"
    contact = (data.get("guardian_contact") or "").strip() or "-"
    return (
        "🛡 Черновик готов. Требуется подтверждение.\n"
        f"Хранитель: {name}\n"
        f"Опека: {scope}\n"
        f"Причина: {reason}\n"
        f"Контакт: {contact}"
    )


def _guardian_confirm_keyboard(lang_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✔️ Подтвердить", callback_data="guardian_confirm")],
            [InlineKeyboardButton(text="✏️ Изменить", callback_data="guardian_edit")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="inherit_cancel")],
        ]
    )


@router.callback_query(F.data == "inherit_guardian")
async def handle_inheritance_guardian_start(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await state.clear()
    await state.set_state(InheritanceGuardianFlow.waiting_for_guardian_name)
    await callback.message.answer(
        "🛡 Назначение хранителя (опекуна)\n"
        "Введите ФИО + @username (если есть).\n\n"
        "Для отмены отправьте /cancel.",
        reply_markup=_inheritance_cancel_keyboard(lang_code),
    )


@router.message(InheritanceGuardianFlow.waiting_for_guardian_name)
async def handle_guardian_name(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        menu = INLINE_MENU_BY_KEY["menu.inheritance"]
        await message.answer(get_text(menu.title_key, lang_code), reply_markup=build_inline_keyboard(menu, lang_code))
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Введите ФИО (и @username, если есть).")
        return
    await state.update_data(guardian_name=text)
    await state.set_state(InheritanceGuardianFlow.waiting_for_reason)
    await message.answer(
        "Причина назначения? (1 фраза)\n\nДля отмены отправьте /cancel.",
        reply_markup=_inheritance_cancel_keyboard(lang_code),
    )


@router.message(InheritanceGuardianFlow.waiting_for_reason)
async def handle_guardian_reason(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        menu = INLINE_MENU_BY_KEY["menu.inheritance"]
        await message.answer(get_text(menu.title_key, lang_code), reply_markup=build_inline_keyboard(menu, lang_code))
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Введите причину (1 фраза).")
        return
    await state.update_data(guardian_reason=text)
    await state.set_state(InheritanceGuardianFlow.waiting_for_scope)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👶 Детьми", callback_data="guardian_scope:children")],
            [InlineKeyboardButton(text="💰 Имуществом", callback_data="guardian_scope:assets")],
            [InlineKeyboardButton(text="🏘 Недвижимостью", callback_data="guardian_scope:realty")],
            [InlineKeyboardButton(text="🔐 Всем указанным", callback_data="guardian_scope:all")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="inherit_cancel")],
        ]
    )
    await message.answer("Опека над:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("guardian_scope:"))
async def handle_guardian_scope(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    raw = (callback.data or "").split(":", 1)[-1].strip().lower()
    scope_map = {
        "children": "Детьми",
        "assets": "Имуществом",
        "realty": "Недвижимостью",
        "all": "Всем указанным",
    }
    if raw not in scope_map:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    await callback.answer()
    await state.update_data(guardian_scope=scope_map[raw])
    await state.set_state(InheritanceGuardianFlow.waiting_for_contact)
    await callback.message.answer(
        "Контакт хранителя (тел / соцсеть):\n\nДля отмены отправьте /cancel.",
        reply_markup=_inheritance_cancel_keyboard(lang_code),
    )


@router.message(InheritanceGuardianFlow.waiting_for_contact)
async def handle_guardian_contact(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        menu = INLINE_MENU_BY_KEY["menu.inheritance"]
        await message.answer(get_text(menu.title_key, lang_code), reply_markup=build_inline_keyboard(menu, lang_code))
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Введите контакт (телефон или ссылку/ник).")
        return
    await state.update_data(guardian_contact=text)
    data = await state.get_data()
    inheritance_guardian_last_draft[message.from_user.id] = dict(data)
    await state.clear()
    await message.answer(_render_guardian_summary(data), reply_markup=_guardian_confirm_keyboard(lang_code))


@router.callback_query(F.data == "guardian_edit")
async def handle_guardian_edit_menu(
    callback: CallbackQuery,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Хранитель", callback_data="guardian_edit_field:name")],
            [InlineKeyboardButton(text="Причина", callback_data="guardian_edit_field:reason")],
            [InlineKeyboardButton(text="Опека", callback_data="guardian_edit_field:scope")],
            [InlineKeyboardButton(text="Контакт", callback_data="guardian_edit_field:contact")],
            [InlineKeyboardButton(text=get_text("button.back", lang_code), callback_data="guardian_review")],
        ]
    )
    await edit_or_send_callback(callback, "✏️ Что изменить?", reply_markup=keyboard)


@router.callback_query(F.data == "guardian_review")
async def handle_guardian_review(
    callback: CallbackQuery,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    draft = inheritance_guardian_last_draft.get(callback.from_user.id) or {}
    await edit_or_send_callback(
        callback,
        _render_guardian_summary(draft),
        reply_markup=_guardian_confirm_keyboard(lang_code),
    )


@router.callback_query(F.data.startswith("guardian_edit_field:"))
async def handle_guardian_edit_field(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    field = (callback.data or "").split(":", 1)[-1].strip().lower()
    draft = inheritance_guardian_last_draft.get(callback.from_user.id) or {}
    await callback.answer()
    await state.clear()
    await state.update_data(**draft)

    if field == "name":
        await state.set_state(InheritanceGuardianFlow.waiting_for_guardian_name)
        await callback.message.answer(
            "Введите ФИО + @username (если есть):",
            reply_markup=_inheritance_cancel_keyboard(lang_code),
        )
    elif field == "reason":
        await state.set_state(InheritanceGuardianFlow.waiting_for_reason)
        await callback.message.answer(
            "Причина назначения? (1 фраза):",
            reply_markup=_inheritance_cancel_keyboard(lang_code),
        )
    elif field == "scope":
        await state.set_state(InheritanceGuardianFlow.waiting_for_scope)
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="👶 Детьми", callback_data="guardian_scope:children")],
                [InlineKeyboardButton(text="💰 Имуществом", callback_data="guardian_scope:assets")],
                [InlineKeyboardButton(text="🏘 Недвижимостью", callback_data="guardian_scope:realty")],
                [InlineKeyboardButton(text="🔐 Всем указанным", callback_data="guardian_scope:all")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="inherit_cancel")],
            ]
        )
        await callback.message.answer("Опека над:", reply_markup=keyboard)
    elif field == "contact":
        await state.set_state(InheritanceGuardianFlow.waiting_for_contact)
        await callback.message.answer(
            "Контакт хранителя (тел / соцсеть):",
            reply_markup=_inheritance_cancel_keyboard(lang_code),
        )
    else:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)


@router.callback_query(F.data == "guardian_confirm")
async def handle_guardian_confirm(
    callback: CallbackQuery,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    draft = inheritance_guardian_last_draft.get(callback.from_user.id)
    if not draft:
        await callback.answer("Черновик не найден.", show_alert=True)
        return

    filename = f"guardian_{callback.from_user.id}_{uuid.uuid4().hex}.txt"
    name = f"Хранитель {date.today().isoformat()}"
    try:
        await db.documents.add_document(
            filename=filename,
            user_id=callback.from_user.id,
            category="Inheritance",
            name=name,
            content=_render_guardian_summary(draft).encode("utf-8"),
            doc_type="Guardian",
        )
    except Exception:
        logger.exception("Failed to save guardian draft")
        await callback.answer("Не удалось сохранить.", show_alert=True)
        return

    await callback.answer("Сохранено.", show_alert=False)
    menu = INLINE_MENU_BY_KEY["menu.inheritance"]
    await edit_or_send_callback(
        callback,
        get_text(menu.title_key, lang_code),
        reply_markup=build_inline_keyboard(menu, lang_code),
    )


@router.callback_query(F.data == "inherit_ask")
async def handle_inheritance_ask_start(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await state.clear()
    await state.set_state(InheritanceAskFlow.waiting_for_request_type)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎥 Запросить видеоконференцию (Zoom/Meet)",
                    callback_data="inherit_ask_type:video",
                )
            ],
            [InlineKeyboardButton(text="💬 Оставить вопрос текстом", callback_data="inherit_ask_type:text")],
            [InlineKeyboardButton(text="📎 Приложить документы", callback_data="inherit_ask_type:docs")],
            [InlineKeyboardButton(text=get_text("button.back", lang_code), callback_data="menu:menu.inheritance")],
        ]
    )
    await callback.message.answer(
        "🤝 Вы можете задать вопрос учёному.\n"
        "Опишите ситуацию подробно.\n"
        "Вам ответит шариатский эксперт или будет назначено видеослушание.",
        reply_markup=keyboard,
    )


def _inherit_ask_done_keyboard(lang_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Готово", callback_data="inherit_ask_docs_done")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="inherit_cancel")],
            [InlineKeyboardButton(text=get_text("button.back", lang_code), callback_data="inherit_ask")],
        ]
    )


def _inherit_ask_confirm_keyboard(lang_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Отправить", callback_data="inherit_ask_submit")],
            [InlineKeyboardButton(text="📎 Приложить документы", callback_data="inherit_ask_attach")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="inherit_ask")],
        ]
    )


@router.callback_query(F.data.startswith("inherit_ask_type:"))
async def handle_inheritance_ask_type(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    choice = (callback.data or "").split(":", 1)[-1].strip().lower()
    if choice not in {"video", "text", "docs"}:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return

    await callback.answer()
    await state.update_data(ask_type=choice)
    if choice == "video":
        await state.set_state(InheritanceAskFlow.waiting_for_video_time)
        await callback.message.answer(
            "🗓 Укажите удобные дни/время и часовой пояс (например: Пн-Ср 19:00-21:00 МСК).",
            reply_markup=_inheritance_cancel_keyboard(lang_code),
        )
    elif choice == "text":
        await state.set_state(InheritanceAskFlow.waiting_for_text_question)
        await callback.message.answer(
            "💬 Опишите ситуацию одним сообщением.",
            reply_markup=_inheritance_cancel_keyboard(lang_code),
        )
    else:
        inheritance_scholar_attachments.pop(callback.from_user.id, None)
        await state.set_state(InheritanceAskFlow.waiting_for_attachments)
        await callback.message.answer(
            "📎 Пришлите документы (PDF/фото). Когда закончите — нажмите «Готово».",
            reply_markup=_inherit_ask_done_keyboard(lang_code),
        )


@router.message(InheritanceAskFlow.waiting_for_text_question)
async def handle_inheritance_ask_text(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        menu = INLINE_MENU_BY_KEY["menu.inheritance"]
        await message.answer(get_text(menu.title_key, lang_code), reply_markup=build_inline_keyboard(menu, lang_code))
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Опишите ситуацию текстом одним сообщением.")
        return

    await state.update_data(ask_text=text, ask_type="text")
    data = await state.get_data()
    attachments = inheritance_scholar_attachments.get(message.from_user.id) or []
    draft = ScholarRequestDraft(request_type="text", data=data, attachments=attachments)
    await message.answer(build_request_summary(draft), reply_markup=_inherit_ask_confirm_keyboard(lang_code))


@router.message(InheritanceAskFlow.waiting_for_video_time)
async def handle_inheritance_ask_video_time(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        menu = INLINE_MENU_BY_KEY["menu.inheritance"]
        await message.answer(get_text(menu.title_key, lang_code), reply_markup=build_inline_keyboard(menu, lang_code))
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Укажите удобные дни/время и часовой пояс текстом.")
        return

    await state.update_data(ask_video_time=text, ask_type="video")
    await state.set_state(InheritanceAskFlow.waiting_for_video_contact)
    await message.answer("Контакт для связи (телефон/ник/ссылка):", reply_markup=_inheritance_cancel_keyboard(lang_code))


@router.message(InheritanceAskFlow.waiting_for_video_contact)
async def handle_inheritance_ask_video_contact(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        menu = INLINE_MENU_BY_KEY["menu.inheritance"]
        await message.answer(get_text(menu.title_key, lang_code), reply_markup=build_inline_keyboard(menu, lang_code))
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Введите контакт для связи.")
        return

    await state.update_data(ask_video_contact=text, ask_type="video")
    await state.set_state(InheritanceAskFlow.waiting_for_video_description)
    await message.answer("Коротко опишите ситуацию (1–3 абзаца):", reply_markup=_inheritance_cancel_keyboard(lang_code))


@router.message(InheritanceAskFlow.waiting_for_video_description)
async def handle_inheritance_ask_video_description(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        menu = INLINE_MENU_BY_KEY["menu.inheritance"]
        await message.answer(get_text(menu.title_key, lang_code), reply_markup=build_inline_keyboard(menu, lang_code))
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Опишите ситуацию текстом.")
        return

    await state.update_data(ask_video_description=text, ask_type="video")
    data = await state.get_data()
    attachments = inheritance_scholar_attachments.get(message.from_user.id) or []
    draft = ScholarRequestDraft(request_type="video", data=data, attachments=attachments)
    await message.answer(build_request_summary(draft), reply_markup=_inherit_ask_confirm_keyboard(lang_code))


async def _extract_scholar_attachment(message: Message) -> Optional[ScholarAttachment]:
    photo = message.photo[-1] if message.photo else None
    if photo:
        file_id = photo.file_id
        filename = f"{photo.file_unique_id}.jpg"
        content_type = "image/jpeg"
    elif message.document:
        mime = (message.document.mime_type or "").lower()
        if not (mime.startswith("image/") or mime == "application/pdf"):
            return None
        file_id = message.document.file_id
        filename = message.document.file_name or message.document.file_unique_id or "attachment.bin"
        content_type = mime or "application/octet-stream"
    else:
        return None

    file = await message.bot.get_file(file_id)
    file_stream = await message.bot.download_file(file.file_path)
    content = file_stream.read() if file_stream else b""
    if not content:
        return None
    return ScholarAttachment(content=content, filename=filename, content_type=content_type)


@router.message(InheritanceAskFlow.waiting_for_attachments)
async def handle_inheritance_ask_attachments(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    _ = state
    _ = user_row
    if is_cancel_command(message.text):
        inheritance_scholar_attachments.pop(message.from_user.id, None)
        menu = INLINE_MENU_BY_KEY["menu.inheritance"]
        await message.answer(get_text(menu.title_key, lang_code), reply_markup=build_inline_keyboard(menu, lang_code))
        return

    extracted = await _extract_scholar_attachment(message)
    if extracted is None:
        await message.answer("Прикрепите PDF или фото (как документ или фото).")
        return

    items = inheritance_scholar_attachments.setdefault(message.from_user.id, [])
    if len(items) >= MAX_ATTACHMENTS:
        await message.answer("Максимум 5 файлов. Нажмите «Готово».")
        return

    items.append(extracted)
    await message.answer(f"Добавлено файлов: {len(items)}", reply_markup=_inherit_ask_done_keyboard(lang_code))


@router.callback_query(F.data == "inherit_ask_docs_done")
async def handle_inheritance_ask_docs_done(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await state.update_data(ask_type="docs")
    await state.set_state(InheritanceAskFlow.waiting_for_attachments_description)
    await callback.message.answer(
        "📝 Добавьте описание к документам (одним сообщением).",
        reply_markup=_inheritance_cancel_keyboard(lang_code),
    )


@router.message(InheritanceAskFlow.waiting_for_attachments_description)
async def handle_inheritance_ask_docs_description(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        inheritance_scholar_attachments.pop(message.from_user.id, None)
        menu = INLINE_MENU_BY_KEY["menu.inheritance"]
        await message.answer(get_text(menu.title_key, lang_code), reply_markup=build_inline_keyboard(menu, lang_code))
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Добавьте описание текстом.")
        return

    await state.update_data(ask_docs_description=text, ask_type="docs")
    data = await state.get_data()
    attachments = inheritance_scholar_attachments.get(message.from_user.id) or []
    draft = ScholarRequestDraft(request_type="docs", data=data, attachments=attachments)
    await message.answer(build_request_summary(draft), reply_markup=_inherit_ask_confirm_keyboard(lang_code))


@router.callback_query(F.data == "inherit_ask_attach")
async def handle_inheritance_ask_attach(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await state.set_state(InheritanceAskFlow.waiting_for_attachments)
    await callback.message.answer(
        "📎 Пришлите документы (PDF/фото). Когда закончите — нажмите «Готово».",
        reply_markup=_inherit_ask_done_keyboard(lang_code),
    )


@router.callback_query(F.data == "inherit_ask_submit")
async def handle_inheritance_ask_submit(
    callback: CallbackQuery,
    state: FSMContext,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    data = await state.get_data()
    attachments = inheritance_scholar_attachments.get(callback.from_user.id) or []

    request_id = uuid.uuid4().int % 100000
    request_type = str(data.get("ask_type") or "text").strip().lower()
    if request_type not in {"video", "text", "docs"}:
        request_type = "text"

    draft = ScholarRequestDraft(
        request_type=request_type,  # type: ignore[arg-type]
        data=dict(data),
        attachments=attachments,
    )
    summary = build_request_summary(draft)
    payload = build_request_payload(
        request_id=request_id,
        telegram_user=callback.from_user,
        language=lang_code,
        draft=draft,
    )
    forward_text = build_forward_text(
        request_id=request_id,
        telegram_user=callback.from_user,
        summary=summary,
    )

    try:
        await persist_request_to_documents(
            db,
            request_id=request_id,
            user_id=callback.from_user.id,
            payload=payload,
            attachments=attachments,
        )
    except Exception:
        logger.exception("Failed to persist scholar request")

    forwarded = await forward_request_to_group(
        callback.bot,
        request_id=request_id,
        user_id=callback.from_user.id,
        text=forward_text,
        attachments=attachments,
    )
    await create_work_item(
        db,
        topic="inheritance",
        kind="scholar_request",
        created_by_user_id=callback.from_user.id,
        target_user_id=callback.from_user.id,
        payload={
            "request_id": request_id,
            "request_type": request_type,
            "summary": summary,
        },
    )

    inheritance_scholar_attachments.pop(callback.from_user.id, None)
    await state.clear()
    await callback.message.answer(
        "✅ Заявка отправлена. Ожидайте ответ."
        if forwarded
        else "❌ Не удалось отправить заявку автоматически. Попробуйте позже.",
        reply_markup=build_inline_keyboard(INLINE_MENU_BY_KEY["menu.inheritance"], lang_code),
    )
