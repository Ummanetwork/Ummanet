from __future__ import annotations

import json
import logging
import uuid
from datetime import date
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

from app.bot.states.comitee import NikahAskFlow, NikahNewFlow
from app.infrastructure.database.db import DB
from app.infrastructure.database.models.user import UserModel
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

logger = logging.getLogger(__name__)

router = Router(name="comitee.nikah")

nikah_scholar_attachments: Dict[int, List[ScholarAttachment]] = {}

AGE_MIN = 12
AGE_MAX = 100


def _cancel_kb(lang_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="nikah_cancel")],
            [
                InlineKeyboardButton(
                    text=get_text("button.back", lang_code),
                    callback_data="menu:menu.nikah",
                )
            ],
        ]
    )


def _nikah_menu_kb(lang_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("button.nikah.new", lang_code),
                    callback_data="nikah_new",
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("button.nikah.my", lang_code),
                    callback_data="nikah_my",
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("button.nikah.rules", lang_code),
                    callback_data="nikah_rules",
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("button.nikah.ask", lang_code),
                    callback_data="nikah_ask",
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("button.back", lang_code),
                    callback_data="menu:menu.my_cases",
                )
            ],
        ]
    )


def _nikah_ask_menu_kb(lang_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎥 Запросить видеоконференцию (Zoom/Meet)", callback_data="nikah_ask_type:video")],
            [InlineKeyboardButton(text="💬 Оставить вопрос текстом", callback_data="nikah_ask_type:text")],
            [InlineKeyboardButton(text="📎 Приложить документы", callback_data="nikah_ask_type:docs")],
            [InlineKeyboardButton(text="🕌 Получить фетву", callback_data="nikah_ask_type:fatwa")],
            [InlineKeyboardButton(text=get_text("button.back", lang_code), callback_data="menu:menu.nikah")],
        ]
    )


def _nikah_ask_cancel_kb(lang_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="nikah_cancel")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="nikah_ask")],
        ]
    )


def _nikah_ask_done_keyboard(lang_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Готово", callback_data="nikah_ask_docs_done")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="nikah_cancel")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="nikah_ask")],
        ]
    )


def _nikah_ask_confirm_keyboard(lang_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Отправить", callback_data="nikah_ask_submit")],
            [InlineKeyboardButton(text="📎 Приложить документы", callback_data="nikah_ask_attach")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="nikah_ask")],
        ]
    )


@router.callback_query(F.data == "nikah_cancel")
async def handle_nikah_cancel(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await state.clear()
    nikah_scholar_attachments.pop(callback.from_user.id, None)
    await callback.message.answer(get_text("menu.nikah.title", lang_code), reply_markup=_nikah_menu_kb(lang_code))


@router.callback_query(F.data == "nikah_new")
async def handle_nikah_new_start(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await state.clear()
    await state.set_state(NikahNewFlow.waiting_for_role)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧔 Жених", callback_data="nikah_role:groom")],
            [InlineKeyboardButton(text="👩 Невеста", callback_data="nikah_role:bride")],
            [InlineKeyboardButton(text="🧔‍♂️ Вали (опекун)", callback_data="nikah_role:wali")],
            [InlineKeyboardButton(text="👥 Представитель/другая сторона", callback_data="nikah_role:other")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="nikah_cancel")],
        ]
    )
    await edit_or_send_callback(callback, "Кто вы?", reply_markup=kb)


@router.callback_query(F.data.startswith("nikah_role:"))
async def handle_nikah_role(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    role = (callback.data or "").split(":", 1)[-1].strip().lower()
    if role not in {"groom", "bride", "wali", "other"}:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    await callback.answer()
    await state.update_data(role=role, needs_scholar_review=False)
    await state.set_state(NikahNewFlow.waiting_for_groom_name)
    await callback.message.answer("📌 ФИО жениха:", reply_markup=_cancel_kb(lang_code))


def _parse_age(text: str) -> Optional[int]:
    raw = (text or "").strip()
    if not raw.isdigit():
        return None
    value = int(raw)
    if value < AGE_MIN or value > AGE_MAX:
        return None
    return value


@router.message(NikahNewFlow.waiting_for_groom_name)
async def handle_groom_name(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("menu.nikah.title", lang_code), reply_markup=_nikah_menu_kb(lang_code))
        return
    name = (message.text or "").strip()
    if not name:
        await message.answer("Введите ФИО жениха.")
        return
    await state.update_data(groom_full_name=name)
    await state.set_state(NikahNewFlow.waiting_for_groom_age)
    await message.answer(f"📌 Возраст жениха ({AGE_MIN}–{AGE_MAX}):", reply_markup=_cancel_kb(lang_code))


@router.message(NikahNewFlow.waiting_for_groom_age)
async def handle_groom_age(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("menu.nikah.title", lang_code), reply_markup=_nikah_menu_kb(lang_code))
        return
    age = _parse_age(message.text or "")
    if age is None:
        await message.answer(f"Введите возраст числом ({AGE_MIN}–{AGE_MAX}).")
        return
    await state.update_data(groom_age=age)
    await state.set_state(NikahNewFlow.waiting_for_groom_is_muslim)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да", callback_data="nikah_groom_muslim:yes")],
            [InlineKeyboardButton(text="❌ Нет", callback_data="nikah_groom_muslim:no")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="nikah_cancel")],
        ]
    )
    await message.answer("📌 Жених мусульманин?", reply_markup=kb)


@router.callback_query(F.data.startswith("nikah_groom_muslim:"))
async def handle_groom_is_muslim(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    value = (callback.data or "").split(":", 1)[-1].strip().lower()
    if value not in {"yes", "no"}:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    await callback.answer()
    if value == "no":
        await state.clear()
        await callback.message.answer(
            "⛔ Никях невозможен: жених должен быть мусульманином.\n"
            "❓ Для уточнения частных случаев обратитесь к учёному.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=get_text("button.nikah.ask", lang_code), callback_data="nikah_ask")],
                    [InlineKeyboardButton(text=get_text("button.back", lang_code), callback_data="menu:menu.nikah")],
                ]
            ),
        )
        return
    await state.update_data(groom_is_muslim=True)
    await state.set_state(NikahNewFlow.waiting_for_groom_contact)
    await callback.message.answer("📌 Контакты жениха (тел/username/почта):", reply_markup=_cancel_kb(lang_code))


@router.message(NikahNewFlow.waiting_for_groom_contact)
async def handle_groom_contact(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("menu.nikah.title", lang_code), reply_markup=_nikah_menu_kb(lang_code))
        return
    contact = (message.text or "").strip()
    if not contact:
        await message.answer("Введите контакты жениха.")
        return
    await state.update_data(groom_contact=contact)
    await state.set_state(NikahNewFlow.waiting_for_bride_name)
    await message.answer("📌 ФИО невесты:", reply_markup=_cancel_kb(lang_code))


@router.message(NikahNewFlow.waiting_for_bride_name)
async def handle_bride_name(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("menu.nikah.title", lang_code), reply_markup=_nikah_menu_kb(lang_code))
        return
    name = (message.text or "").strip()
    if not name:
        await message.answer("Введите ФИО невесты.")
        return
    await state.update_data(bride_full_name=name)
    await state.set_state(NikahNewFlow.waiting_for_bride_age)
    await message.answer(f"📌 Возраст невесты ({AGE_MIN}–{AGE_MAX}):", reply_markup=_cancel_kb(lang_code))


@router.message(NikahNewFlow.waiting_for_bride_age)
async def handle_bride_age(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("menu.nikah.title", lang_code), reply_markup=_nikah_menu_kb(lang_code))
        return
    age = _parse_age(message.text or "")
    if age is None:
        await message.answer(f"Введите возраст числом ({AGE_MIN}–{AGE_MAX}).")
        return
    await state.update_data(bride_age=age)
    await state.set_state(NikahNewFlow.waiting_for_bride_is_muslim)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да", callback_data="nikah_bride_muslim:yes")],
            [InlineKeyboardButton(text="⚠️ Нет", callback_data="nikah_bride_muslim:no")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="nikah_cancel")],
        ]
    )
    await message.answer("📌 Невеста мусульманка?", reply_markup=kb)


@router.callback_query(F.data.startswith("nikah_bride_muslim:"))
async def handle_bride_is_muslim(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    value = (callback.data or "").split(":", 1)[-1].strip().lower()
    if value not in {"yes", "no"}:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    await callback.answer()
    if value == "no":
        await state.update_data(bride_is_muslim=False, needs_scholar_review=True)
        await callback.message.answer(
            "⚠️ Невеста не мусульманка: нужны уточнения по условиям (люди Писания и др.). "
            "Рекомендуется консультация учёного.",
        )
    else:
        await state.update_data(bride_is_muslim=True)
    await state.set_state(NikahNewFlow.waiting_for_bride_contact)
    await callback.message.answer("📌 Контакты невесты (тел/username/почта):", reply_markup=_cancel_kb(lang_code))


@router.message(NikahNewFlow.waiting_for_bride_contact)
async def handle_bride_contact(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("menu.nikah.title", lang_code), reply_markup=_nikah_menu_kb(lang_code))
        return
    contact = (message.text or "").strip()
    if not contact:
        await message.answer("Введите контакты невесты.")
        return
    await state.update_data(bride_contact=contact)
    await state.set_state(NikahNewFlow.waiting_for_wali_presence)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data="nikah_wali_present:yes"),
                InlineKeyboardButton(text="❌ Нет", callback_data="nikah_wali_present:no"),
            ],
            [InlineKeyboardButton(text="🤷 Не знаю", callback_data="nikah_wali_present:unknown")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="nikah_cancel")],
        ]
    )
    await message.answer("У невесты есть вали (опекун)?", reply_markup=kb)


@router.callback_query(F.data.startswith("nikah_wali_present:"))
async def handle_wali_present(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    value = (callback.data or "").split(":", 1)[-1].strip().lower()
    if value not in {"yes", "no", "unknown"}:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    await callback.answer()
    if value != "yes":
        await state.clear()
        await callback.message.answer(
            "❗ Без вали никах недействителен.\n"
            "⛔ Договор не будет составлен.\n"
            "💡 Вы можете обратиться к учёным для поиска решения.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=get_text("button.nikah.ask", lang_code), callback_data="nikah_ask")],
                    [InlineKeyboardButton(text=get_text("button.back", lang_code), callback_data="menu:menu.nikah")],
                ]
            ),
        )
        return
    await state.update_data(wali_present=True)
    await state.set_state(NikahNewFlow.waiting_for_wali_name)
    await callback.message.answer("ФИО вали:", reply_markup=_cancel_kb(lang_code))


@router.message(NikahNewFlow.waiting_for_wali_name)
async def handle_wali_name(message: Message, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("menu.nikah.title", lang_code), reply_markup=_nikah_menu_kb(lang_code))
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Введите ФИО вали.")
        return
    await state.update_data(wali_full_name=text)
    await state.set_state(NikahNewFlow.waiting_for_wali_contact)
    await message.answer("Контакты вали:", reply_markup=_cancel_kb(lang_code))


@router.message(NikahNewFlow.waiting_for_wali_contact)
async def handle_wali_contact(message: Message, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("menu.nikah.title", lang_code), reply_markup=_nikah_menu_kb(lang_code))
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Введите контакты вали.")
        return
    await state.update_data(wali_contact=text)
    await state.set_state(NikahNewFlow.waiting_for_wali_relation)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Отец", callback_data="nikah_wali_relation:father")],
            [InlineKeyboardButton(text="Брат", callback_data="nikah_wali_relation:brother")],
            [InlineKeyboardButton(text="Дед", callback_data="nikah_wali_relation:grandfather")],
            [InlineKeyboardButton(text="Дядя", callback_data="nikah_wali_relation:uncle")],
            [InlineKeyboardButton(text="Другое", callback_data="nikah_wali_relation:other")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="nikah_cancel")],
        ]
    )
    await message.answer("Степень родства вали:", reply_markup=kb)


@router.callback_query(F.data.startswith("nikah_wali_relation:"))
async def handle_wali_relation(callback: CallbackQuery, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    rel = (callback.data or "").split(":", 1)[-1].strip().lower()
    rel_map = {
        "father": "отец",
        "brother": "брат",
        "grandfather": "дед",
        "uncle": "дядя",
        "other": "другое",
    }
    if rel not in rel_map:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    await callback.answer()
    await state.update_data(wali_relation=rel_map[rel])
    await state.set_state(NikahNewFlow.waiting_for_wali_is_muslim)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да", callback_data="nikah_wali_muslim:yes")],
            [InlineKeyboardButton(text="❌ Нет", callback_data="nikah_wali_muslim:no")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="nikah_cancel")],
        ]
    )
    await callback.message.answer("Вали мусульманин?", reply_markup=kb)


@router.callback_query(F.data.startswith("nikah_wali_muslim:"))
async def handle_wali_is_muslim(callback: CallbackQuery, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    value = (callback.data or "").split(":", 1)[-1].strip().lower()
    if value not in {"yes", "no"}:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    await callback.answer()
    if value == "no":
        await state.clear()
        await callback.message.answer(
            "⛔ Вали должен быть мусульманином. Обратитесь к учёному.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=get_text("button.nikah.ask", lang_code), callback_data="nikah_ask")],
                    [InlineKeyboardButton(text=get_text("button.back", lang_code), callback_data="menu:menu.nikah")],
                ]
            ),
        )
        return
    await state.update_data(wali_is_muslim=True)
    await state.set_state(NikahNewFlow.waiting_for_wali_approves)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да", callback_data="nikah_wali_approves:yes")],
            [InlineKeyboardButton(text="❌ Нет", callback_data="nikah_wali_approves:no")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="nikah_cancel")],
        ]
    )
    await callback.message.answer("Вали согласен на брак?", reply_markup=kb)


@router.callback_query(F.data.startswith("nikah_wali_approves:"))
async def handle_wali_approves(callback: CallbackQuery, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    value = (callback.data or "").split(":", 1)[-1].strip().lower()
    if value not in {"yes", "no"}:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    await callback.answer()
    if value == "no":
        await state.clear()
        await callback.message.answer(
            "⛔ Без согласия вали договор не составляется. Обратитесь к учёному.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=get_text("button.nikah.ask", lang_code), callback_data="nikah_ask")],
                    [InlineKeyboardButton(text=get_text("button.back", lang_code), callback_data="menu:menu.nikah")],
                ]
            ),
        )
        return
    await state.update_data(wali_approves=True)
    await state.set_state(NikahNewFlow.waiting_for_witness_1_name)
    await callback.message.answer("Введите данные 1-го свидетеля (ФИО):", reply_markup=_cancel_kb(lang_code))


@router.message(NikahNewFlow.waiting_for_witness_1_name)
async def handle_witness1_name(message: Message, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("menu.nikah.title", lang_code), reply_markup=_nikah_menu_kb(lang_code))
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Введите ФИО свидетеля.")
        return
    await state.update_data(witness_1_name=text)
    await state.set_state(NikahNewFlow.waiting_for_witness_1_contact)
    await message.answer("Контакт свидетеля 1:", reply_markup=_cancel_kb(lang_code))


@router.message(NikahNewFlow.waiting_for_witness_1_contact)
async def handle_witness1_contact(message: Message, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("menu.nikah.title", lang_code), reply_markup=_nikah_menu_kb(lang_code))
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Введите контакт свидетеля.")
        return
    await state.update_data(witness_1_contact=text)
    await state.set_state(NikahNewFlow.waiting_for_witness_1_is_muslim)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Мусульманин", callback_data="nikah_witness1_muslim:yes")],
            [InlineKeyboardButton(text="❌ Не мусульманин", callback_data="nikah_witness1_muslim:no")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="nikah_cancel")],
        ]
    )
    await message.answer("Свидетель 1 мусульманин?", reply_markup=kb)


@router.callback_query(F.data.startswith("nikah_witness1_muslim:"))
async def handle_witness1_is_muslim(callback: CallbackQuery, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    value = (callback.data or "").split(":", 1)[-1].strip().lower()
    if value not in {"yes", "no"}:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    await callback.answer()
    if value == "no":
        await state.set_state(NikahNewFlow.waiting_for_witness_1_name)
        await callback.message.answer(
            "❗ Свидетель должен быть мусульманином. Введите другого свидетеля (ФИО):",
            reply_markup=_cancel_kb(lang_code),
        )
        return
    await state.update_data(witness_1_is_muslim=True)
    await state.set_state(NikahNewFlow.waiting_for_witness_2_name)
    await callback.message.answer("Введите данные 2-го свидетеля (ФИО):", reply_markup=_cancel_kb(lang_code))


@router.message(NikahNewFlow.waiting_for_witness_2_name)
async def handle_witness2_name(message: Message, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("menu.nikah.title", lang_code), reply_markup=_nikah_menu_kb(lang_code))
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Введите ФИО свидетеля.")
        return
    await state.update_data(witness_2_name=text)
    await state.set_state(NikahNewFlow.waiting_for_witness_2_contact)
    await message.answer("Контакт свидетеля 2:", reply_markup=_cancel_kb(lang_code))


@router.message(NikahNewFlow.waiting_for_witness_2_contact)
async def handle_witness2_contact(message: Message, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("menu.nikah.title", lang_code), reply_markup=_nikah_menu_kb(lang_code))
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Введите контакт свидетеля.")
        return
    await state.update_data(witness_2_contact=text)
    await state.set_state(NikahNewFlow.waiting_for_witness_2_is_muslim)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Мусульманин", callback_data="nikah_witness2_muslim:yes")],
            [InlineKeyboardButton(text="❌ Не мусульманин", callback_data="nikah_witness2_muslim:no")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="nikah_cancel")],
        ]
    )
    await message.answer("Свидетель 2 мусульманин?", reply_markup=kb)


@router.callback_query(F.data.startswith("nikah_witness2_muslim:"))
async def handle_witness2_is_muslim(callback: CallbackQuery, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    value = (callback.data or "").split(":", 1)[-1].strip().lower()
    if value not in {"yes", "no"}:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    await callback.answer()
    if value == "no":
        await state.set_state(NikahNewFlow.waiting_for_witness_2_name)
        await callback.message.answer(
            "❗ Свидетель должен быть мусульманином. Введите другого свидетеля (ФИО):",
            reply_markup=_cancel_kb(lang_code),
        )
        return
    await state.update_data(witness_2_is_muslim=True)
    await state.set_state(NikahNewFlow.waiting_for_mahr_description)
    await callback.message.answer(
        "💍 Махр (брачный дар)\nВведите сумму или описание вещи/услуги:",
        reply_markup=_cancel_kb(lang_code),
    )


@router.message(NikahNewFlow.waiting_for_mahr_description)
async def handle_mahr_description(message: Message, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("menu.nikah.title", lang_code), reply_markup=_nikah_menu_kb(lang_code))
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Укажите махр (сумма/вещь/услуга).")
        return
    await state.update_data(mahr_description=text)
    await state.set_state(NikahNewFlow.waiting_for_mahr_payment_mode)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Сразу", callback_data="nikah_mahr_pay:now")],
            [InlineKeyboardButton(text="🧾 Частями", callback_data="nikah_mahr_pay:parts")],
            [InlineKeyboardButton(text="⏳ Отсрочено", callback_data="nikah_mahr_pay:deferred")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="nikah_cancel")],
        ]
    )
    await message.answer("Способ уплаты махра:", reply_markup=kb)


@router.callback_query(F.data.startswith("nikah_mahr_pay:"))
async def handle_mahr_payment_mode(callback: CallbackQuery, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    mode = (callback.data or "").split(":", 1)[-1].strip().lower()
    if mode not in {"now", "parts", "deferred"}:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    await callback.answer()
    await state.update_data(mahr_payment_mode=mode)
    if mode == "now":
        await state.update_data(mahr_payment_terms="сразу")
        await state.set_state(NikahNewFlow.waiting_for_obstacle_iddah)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="❌ Нет", callback_data="nikah_obst_iddah:no")],
                [InlineKeyboardButton(text="⚠️ Да", callback_data="nikah_obst_iddah:yes")],
                [InlineKeyboardButton(text="🤷 Не знаю", callback_data="nikah_obst_iddah:unknown")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="nikah_cancel")],
            ]
        )
        await callback.message.answer("Невеста в состоянии идды?", reply_markup=kb)
        return
    await state.set_state(NikahNewFlow.waiting_for_mahr_payment_terms)
    await callback.message.answer(
        "Укажите срок/условие выплаты (для частями/отсрочено):",
        reply_markup=_cancel_kb(lang_code),
    )


@router.message(NikahNewFlow.waiting_for_mahr_payment_terms)
async def handle_mahr_terms(message: Message, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("menu.nikah.title", lang_code), reply_markup=_nikah_menu_kb(lang_code))
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Укажите срок/условие.")
        return
    await state.update_data(mahr_payment_terms=text)
    await state.set_state(NikahNewFlow.waiting_for_obstacle_iddah)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Нет", callback_data="nikah_obst_iddah:no")],
            [InlineKeyboardButton(text="⚠️ Да", callback_data="nikah_obst_iddah:yes")],
            [InlineKeyboardButton(text="🤷 Не знаю", callback_data="nikah_obst_iddah:unknown")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="nikah_cancel")],
        ]
    )
    await message.answer("Невеста в состоянии идды?", reply_markup=kb)


async def _stop_with_scholar_offer(message: Message, *, lang_code: str, text: str) -> None:
    await message.answer(
        f"{text}\n\n❓ Рекомендуется консультация учёного.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=get_text("button.nikah.ask", lang_code), callback_data="nikah_ask")],
                [InlineKeyboardButton(text=get_text("button.back", lang_code), callback_data="menu:menu.nikah")],
            ]
        ),
    )


@router.callback_query(F.data.startswith("nikah_obst_iddah:"))
async def handle_obstacle_iddah(callback: CallbackQuery, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    value = (callback.data or "").split(":", 1)[-1].strip().lower()
    if value not in {"yes", "no", "unknown"}:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    await callback.answer()
    await state.update_data(is_iddah=value)
    if value in {"yes", "unknown"}:
        await state.clear()
        await _stop_with_scholar_offer(
            callback.message,
            lang_code=lang_code,
            text="⛔ Нельзя оформлять никях, если невеста в идде или статус неясен.",
        )
        return
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Нет", callback_data="nikah_obst_mahram:no")],
            [InlineKeyboardButton(text="⛔ Да", callback_data="nikah_obst_mahram:yes")],
            [InlineKeyboardButton(text="🤷 Не знаю", callback_data="nikah_obst_mahram:unknown")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="nikah_cancel")],
        ]
    )
    await state.set_state(NikahNewFlow.waiting_for_obstacle_mahram)
    await callback.message.answer("Есть ли между вами близкое кровное родство (махрам)?", reply_markup=kb)


@router.callback_query(F.data.startswith("nikah_obst_mahram:"))
async def handle_obstacle_mahram(callback: CallbackQuery, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    value = (callback.data or "").split(":", 1)[-1].strip().lower()
    if value not in {"yes", "no", "unknown"}:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    await callback.answer()
    await state.update_data(is_mahram=value)
    if value in {"yes", "unknown"}:
        await state.clear()
        await _stop_with_scholar_offer(
            callback.message,
            lang_code=lang_code,
            text="⛔ Возможен запрет из‑за родства (махрам) или статус неясен.",
        )
        return
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Нет", callback_data="nikah_obst_third:no")],
            [InlineKeyboardButton(text="⛔ Да", callback_data="nikah_obst_third:yes")],
            [InlineKeyboardButton(text="🤷 Не знаю", callback_data="nikah_obst_third:unknown")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="nikah_cancel")],
        ]
    )
    await state.set_state(NikahNewFlow.waiting_for_obstacle_third_marriage)
    await callback.message.answer("Это третий брак между вами (3-й таляк)?", reply_markup=kb)


@router.callback_query(F.data.startswith("nikah_obst_third:"))
async def handle_obstacle_third(callback: CallbackQuery, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    value = (callback.data or "").split(":", 1)[-1].strip().lower()
    if value not in {"yes", "no", "unknown"}:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    await callback.answer()
    await state.update_data(is_third_marriage=value)
    if value in {"yes", "unknown"}:
        await state.clear()
        await _stop_with_scholar_offer(
            callback.message,
            lang_code=lang_code,
            text="⛔ Третий развод/брак между вами — возможен запрет или статус неясен.",
        )
        return
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Нет", callback_data="nikah_obst_prior_without_wali:no")],
            [InlineKeyboardButton(text="⚠️ Да", callback_data="nikah_obst_prior_without_wali:yes")],
            [InlineKeyboardButton(text="🤷 Не знаю", callback_data="nikah_obst_prior_without_wali:unknown")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="nikah_cancel")],
        ]
    )
    await state.set_state(NikahNewFlow.waiting_for_obstacle_prior_without_wali)
    await callback.message.answer("Ранее невеста вступала в никях без разрешения вали?", reply_markup=kb)


@router.callback_query(F.data.startswith("nikah_obst_prior_without_wali:"))
async def handle_obstacle_prior_without_wali(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    value = (callback.data or "").split(":", 1)[-1].strip().lower()
    if value not in {"yes", "no", "unknown"}:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    await callback.answer()
    if value in {"yes", "unknown"}:
        await state.update_data(needs_scholar_review=True)

    data = await state.get_data()
    bride_name = data.get("bride_full_name") or "-"
    mahr = data.get("mahr_description") or "-"
    formula = (
        "🕌 Формула шариатского брака\n\n"
        f"Вали говорит:\n«Я выдал за тебя в брак мою подопечную ({bride_name}), за махр ({mahr})»\n\n"
        "Жених отвечает:\n«Я принял её в жёны по шариату Ислама»"
    )
    warning = "\n\n⚠️ В анкете есть ответы, требующие консультации учёного." if data.get("needs_scholar_review") else ""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✔️ Согласен / Подтверждаю", callback_data="nikah_ijabqabul_confirm")],
            [InlineKeyboardButton(text="❓ Обратиться к учёному", callback_data="nikah_ask")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="nikah_cancel")],
        ]
    )
    await state.set_state(NikahNewFlow.waiting_for_ijabqabul_confirm)
    await callback.message.answer(f"{formula}{warning}\n\nПодтвердите согласие сторон и формулу.", reply_markup=kb)


def _render_contract_text(data: dict[str, Any]) -> str:
    groom = data.get("groom_full_name") or "-"
    groom_contact = data.get("groom_contact") or "-"
    bride = data.get("bride_full_name") or "-"
    bride_contact = data.get("bride_contact") or "-"
    wali = data.get("wali_full_name") or "-"
    wali_rel = data.get("wali_relation") or "-"
    w1 = data.get("witness_1_name") or "-"
    w2 = data.get("witness_2_name") or "-"
    mahr = data.get("mahr_description") or "-"
    mahr_mode = data.get("mahr_payment_mode") or "-"
    mahr_terms = data.get("mahr_payment_terms") or "-"
    ijab = f"«Я выдал за тебя в брак мою подопечную ({bride}), за махр ({mahr})»"
    qabul = "«Я принял её в жёны по шариату Ислама»"
    return (
        "بِسْمِ اللهِ الرَّحْمٰنِ الرَّحِيْمِ\n"
        "Договор шариатского брака (Никях)\n\n"
        f"Жених: {groom}\nКонтакты: {groom_contact}\n\n"
        f"Невеста: {bride}\nКонтакты: {bride_contact}\n\n"
        f"Вали: {wali}\nРодство: {wali_rel}\n\n"
        f"Свидетели: 1) {w1}  2) {w2}\n\n"
        f"Махр: {mahr}\nСпособ уплаты: {mahr_mode}\nУсловия/срок: {mahr_terms}\n\n"
        "Формула иджаб и къабуль:\n"
        f"Иджаб: {ijab}\n"
        f"Къабуль: {qabul}\n\n"
        f"Дата: {date.today().isoformat()}\n\n"
        "Подписи (если распечатано):\n"
        "Жених: ____________\nНевеста: ____________\nВали: ____________\n"
        "Свидетель 1: ____________\nСвидетель 2: ____________\n\n"
        "⚠️ Примечание: данный документ — шариатский договор. Для государственной регистрации по желанию нужен ЗАГС."
    )


@router.callback_query(F.data == "nikah_ijabqabul_confirm")
async def handle_ijabqabul_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    data = await state.get_data()
    contract_text = _render_contract_text(data)

    meta = dict(data)
    meta["status"] = "ready" if not data.get("needs_scholar_review") else "needs_scholar_review"
    meta["created_at"] = date.today().isoformat()
    meta_bytes = json.dumps(meta, ensure_ascii=False, indent=2).encode("utf-8")

    contract_filename = f"nikah_{callback.from_user.id}_{uuid.uuid4().hex}.txt"
    meta_filename = f"nikah_meta_{callback.from_user.id}_{uuid.uuid4().hex}.json"
    name = f"Никах {date.today().isoformat()} ({meta['status']})"
    try:
        await db.documents.add_document(
            filename=contract_filename,
            user_id=callback.from_user.id,
            category="Nikah",
            name=name,
            content=contract_text.encode("utf-8"),
            doc_type="NikahContract",
        )
        await db.documents.add_document(
            filename=meta_filename,
            user_id=callback.from_user.id,
            category="Nikah",
            name=f"Никах meta {date.today().isoformat()}",
            content=meta_bytes,
            doc_type="NikahMeta",
        )
    except Exception:
        logger.exception("Failed to save nikah documents")
        await state.clear()
        await callback.message.answer("❌ Не удалось сохранить договор. Попробуйте позже.")
        return

    if meta.get("status") == "needs_scholar_review":
        await create_work_item(
            db,
            topic="nikah",
            kind="needs_review",
            created_by_user_id=callback.from_user.id,
            target_user_id=callback.from_user.id,
            payload={
                "status": meta.get("status"),
                "contract_filename": contract_filename,
                "meta_filename": meta_filename,
            },
        )

    await state.clear()
    buffer = BufferedInputFile(contract_text.encode("utf-8"), filename="nikah_contract.txt")
    await callback.message.answer_document(document=buffer, caption="📄 Договор шариатского брака (черновик)")
    await callback.message.answer(
        "Готово. Можете скачать договор или обратиться к учёному для проверки.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📄 Мои браки", callback_data="nikah_my")],
                [InlineKeyboardButton(text="❓ Обратиться к учёному", callback_data="nikah_ask")],
                [InlineKeyboardButton(text=get_text("button.back", lang_code), callback_data="menu:menu.nikah")],
            ]
        ),
    )


@router.callback_query(F.data == "nikah_my")
async def handle_nikah_my(
    callback: CallbackQuery,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    docs = await db.documents.get_user_documents_by_type(
        user_id=callback.from_user.id,
        doc_type="NikahContract",
    )
    if not docs:
        await callback.message.answer("Пока нет сохранённых браков.", reply_markup=_nikah_menu_kb(lang_code))
        return
    docs = sorted(docs, key=lambda d: int(d.get("id", 0)), reverse=True)[:10]
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"📌 Никах #{doc.get('id')} — {doc.get('name')}",
                    callback_data=f"nikah_view:{doc.get('id')}",
                )
            ]
            for doc in docs
        ]
        + [[InlineKeyboardButton(text=get_text("button.back", lang_code), callback_data="menu:menu.nikah")]]
    )
    await callback.message.answer("📄 Мои браки:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("nikah_view:"))
async def handle_nikah_view(
    callback: CallbackQuery,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    try:
        document_id = int((callback.data or "").split(":", 1)[-1])
    except ValueError:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    doc = await db.documents.get_document_by_id(document_id=document_id)
    if not doc or int(doc.get("user_id") or 0) != callback.from_user.id:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return

    await callback.answer()
    content = doc.get("content") or b""
    buffer = BufferedInputFile(bytes(content), filename=str(doc.get("filename") or "nikah.txt"))
    await callback.message.answer_document(document=buffer, caption=str(doc.get("name") or "Никах"))
    await callback.message.answer(
        "Действия:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🏛 Отправить учёному", callback_data=f"nikah_send_scholar:{document_id}")],
                [
                    InlineKeyboardButton(
                        text="✏️ Запросить расторжение (хул‘а/таляк)",
                        callback_data=f"nikah_dissolve:{document_id}",
                    )
                ],
                [InlineKeyboardButton(text=get_text("button.back", lang_code), callback_data="nikah_my")],
            ]
        ),
    )


async def _submit_scholar_request(
    *,
    db: DB,
    bot: Any,
    telegram_user: Any,
    lang_code: str,
    request_type: str,
    data: dict[str, Any],
    attachments: List[ScholarAttachment],
) -> bool:
    request_id = uuid.uuid4().int % 100000
    draft = ScholarRequestDraft(
        request_type=request_type,  # type: ignore[arg-type]
        data=dict(data),
        attachments=attachments,
    )
    summary = build_request_summary(draft)
    payload = build_request_payload(
        request_id=request_id,
        telegram_user=telegram_user,
        language=lang_code,
        draft=draft,
    )
    forward_text = build_forward_text(request_id=request_id, telegram_user=telegram_user, summary=summary)
    try:
        await persist_request_to_documents(
            db,
            request_id=request_id,
            user_id=telegram_user.id,
            payload=payload,
            attachments=attachments,
        )
    except Exception:
        logger.exception("Failed to persist nikah scholar request")
    return await forward_request_to_group(
        bot,
        request_id=request_id,
        user_id=telegram_user.id,
        text=forward_text,
        attachments=attachments,
    )


@router.callback_query(F.data.startswith("nikah_send_scholar:"))
async def handle_nikah_send_scholar(
    callback: CallbackQuery,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    try:
        document_id = int((callback.data or "").split(":", 1)[-1])
    except ValueError:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    doc = await db.documents.get_document_by_id(document_id=document_id)
    if not doc or int(doc.get("user_id") or 0) != callback.from_user.id:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return

    text = (doc.get("content") or b"").decode("utf-8", errors="replace")
    question = "Прошу проверить корректность никаха и указать, есть ли нарушения условий.\n\n" + text
    await callback.answer()
    ok = await _submit_scholar_request(
        db=db,
        bot=callback.bot,
        telegram_user=callback.from_user,
        lang_code=lang_code,
        request_type="text",
        data={"ask_text": question, "context": "nikah", "nikah_document_id": document_id},
        attachments=[],
    )
    await callback.message.answer(
        "✅ Заявка отправлена. Ожидайте ответ."
        if ok
        else "❌ Не удалось отправить заявку автоматически. Попробуйте позже.",
        reply_markup=_nikah_menu_kb(lang_code),
    )


@router.callback_query(F.data.startswith("nikah_dissolve:"))
async def handle_nikah_dissolve(
    callback: CallbackQuery,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await callback.message.answer(
        "✏️ Запрос расторжения (хул‘а/таляк) оформляется как вопрос учёному.\n"
        "Опишите ситуацию, и мы передадим специалисту.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=get_text("button.nikah.ask", lang_code), callback_data="nikah_ask")],
                [InlineKeyboardButton(text=get_text("button.back", lang_code), callback_data="menu:menu.nikah")],
            ]
        ),
    )


@router.callback_query(F.data == "nikah_rules")
async def handle_nikah_rules(callback: CallbackQuery, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    text = (
        "🕋 Правила шариата о браке (кратко)\n\n"
        "✅ Условия действительности никаха:\n"
        "- Согласие жениха и невесты\n"
        "- Вали у невесты и его согласие\n"
        "- Махр\n"
        "- 2 свидетеля-мусульманина мужчины\n"
        "- Иджаб и къабуль\n\n"
        "⚠️ Проверки:\n"
        "- Невеста не в идде\n"
        "- Нет запретов по махрам-родству\n"
        "- Нет препятствий по 3-му таляку и т.п.\n\n"
        "Коран: 4:3, 4:24, 4:25."
    )
    await callback.message.answer(text, reply_markup=_nikah_menu_kb(lang_code))


@router.callback_query(F.data == "nikah_ask")
async def handle_nikah_ask_start(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await state.clear()
    nikah_scholar_attachments.pop(callback.from_user.id, None)
    await state.set_state(NikahAskFlow.waiting_for_request_type)
    await callback.message.answer(
        "🤝 Вы можете задать вопрос учёному.\n"
        "Опишите ситуацию подробно.\n"
        "Вам ответит шариатский эксперт или будет назначено видеослушание.",
        reply_markup=_nikah_ask_menu_kb(lang_code),
    )


@router.callback_query(F.data.startswith("nikah_ask_type:"))
async def handle_nikah_ask_type(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    choice = (callback.data or "").split(":", 1)[-1].strip().lower()
    if choice not in {"video", "text", "docs", "fatwa"}:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return

    await callback.answer()
    await state.update_data(ask_type=choice, ask_fatwa=choice == "fatwa")
    if choice == "video":
        await state.set_state(NikahAskFlow.waiting_for_video_time)
        await callback.message.answer(
            "🎥 Укажите удобное время/интервал для видеосвязи (например: Ср–Чт 19:00–21:00 по МСК).",
            reply_markup=_nikah_ask_cancel_kb(lang_code),
        )
    elif choice in {"text", "fatwa"}:
        await state.set_state(NikahAskFlow.waiting_for_text_question)
        await callback.message.answer(
            "💬 Опишите ваш вопрос максимально подробно. Если это запрос на фетву — укажите это в тексте.",
            reply_markup=_nikah_ask_cancel_kb(lang_code),
        )
    else:
        nikah_scholar_attachments.pop(callback.from_user.id, None)
        await state.set_state(NikahAskFlow.waiting_for_attachments)
        await callback.message.answer(
            f"📎 Пришлите документы (PDF/фото). Можно до {MAX_ATTACHMENTS} файлов.\n"
            "Когда закончите — нажмите «✅ Готово».",
            reply_markup=_nikah_ask_done_keyboard(lang_code),
        )


@router.message(NikahAskFlow.waiting_for_text_question)
async def handle_nikah_ask_text_question(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        nikah_scholar_attachments.pop(message.from_user.id, None)
        await message.answer(get_text("menu.nikah.title", lang_code), reply_markup=_nikah_menu_kb(lang_code))
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Пожалуйста, опишите вопрос текстом.")
        return

    data = await state.get_data()
    is_fatwa = bool(data.get("ask_fatwa"))
    if is_fatwa:
        text = f"Запрос фетвы.\n\n{text}"

    await state.update_data(ask_text=text, ask_type="text", context="nikah")
    data = await state.get_data()
    attachments = nikah_scholar_attachments.get(message.from_user.id) or []
    draft = ScholarRequestDraft(request_type="text", data=data, attachments=attachments)
    await message.answer(build_request_summary(draft), reply_markup=_nikah_ask_confirm_keyboard(lang_code))


@router.message(NikahAskFlow.waiting_for_video_time)
async def handle_nikah_ask_video_time(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        nikah_scholar_attachments.pop(message.from_user.id, None)
        await message.answer(get_text("menu.nikah.title", lang_code), reply_markup=_nikah_menu_kb(lang_code))
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Укажите удобное время/интервал.")
        return

    await state.update_data(ask_video_time=text, ask_type="video", context="nikah")
    await state.set_state(NikahAskFlow.waiting_for_video_contact)
    await message.answer(
        "📞 Укажите контакт для связи (телефон/username/почта).",
        reply_markup=_nikah_ask_cancel_kb(lang_code),
    )


@router.message(NikahAskFlow.waiting_for_video_contact)
async def handle_nikah_ask_video_contact(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        nikah_scholar_attachments.pop(message.from_user.id, None)
        await message.answer(get_text("menu.nikah.title", lang_code), reply_markup=_nikah_menu_kb(lang_code))
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Укажите контакт для связи.")
        return

    await state.update_data(ask_video_contact=text, ask_type="video", context="nikah")
    await state.set_state(NikahAskFlow.waiting_for_video_description)
    await message.answer(
        "📝 Коротко опишите ситуацию и цель видеосвязи.",
        reply_markup=_nikah_ask_cancel_kb(lang_code),
    )


@router.message(NikahAskFlow.waiting_for_video_description)
async def handle_nikah_ask_video_description(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        nikah_scholar_attachments.pop(message.from_user.id, None)
        await message.answer(get_text("menu.nikah.title", lang_code), reply_markup=_nikah_menu_kb(lang_code))
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Опишите ситуацию (1–5 предложений).")
        return

    await state.update_data(ask_video_description=text, ask_type="video", context="nikah")
    data = await state.get_data()
    attachments = nikah_scholar_attachments.get(message.from_user.id) or []
    draft = ScholarRequestDraft(request_type="video", data=data, attachments=attachments)
    await message.answer(build_request_summary(draft), reply_markup=_nikah_ask_confirm_keyboard(lang_code))


async def _extract_nikah_scholar_attachment(message: Message) -> Optional[ScholarAttachment]:
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


@router.message(NikahAskFlow.waiting_for_attachments)
async def handle_nikah_ask_attachments(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        nikah_scholar_attachments.pop(message.from_user.id, None)
        await message.answer(get_text("menu.nikah.title", lang_code), reply_markup=_nikah_menu_kb(lang_code))
        return

    extracted = await _extract_nikah_scholar_attachment(message)
    if extracted is None:
        await message.answer("Пришлите PDF или фото (изображение).")
        return

    items = nikah_scholar_attachments.setdefault(message.from_user.id, [])
    if len(items) >= MAX_ATTACHMENTS:
        await message.answer(f"Достигнут лимит {MAX_ATTACHMENTS} файлов. Нажмите «✅ Готово».")
        return

    items.append(extracted)
    await message.answer(f"Добавлено файлов: {len(items)}", reply_markup=_nikah_ask_done_keyboard(lang_code))


@router.callback_query(F.data == "nikah_ask_docs_done")
async def handle_nikah_ask_docs_done(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await state.update_data(ask_type="docs", context="nikah")
    await state.set_state(NikahAskFlow.waiting_for_attachments_description)
    await callback.message.answer(
        "📝 Добавьте короткое описание к документам (в чём вопрос и что приложено).",
        reply_markup=_nikah_ask_cancel_kb(lang_code),
    )


@router.message(NikahAskFlow.waiting_for_attachments_description)
async def handle_nikah_ask_docs_description(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        nikah_scholar_attachments.pop(message.from_user.id, None)
        await message.answer(get_text("menu.nikah.title", lang_code), reply_markup=_nikah_menu_kb(lang_code))
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Пожалуйста, добавьте описание (1–3 предложения).")
        return

    await state.update_data(ask_docs_description=text, ask_type="docs", context="nikah")
    data = await state.get_data()
    attachments = nikah_scholar_attachments.get(message.from_user.id) or []
    draft = ScholarRequestDraft(request_type="docs", data=data, attachments=attachments)
    await message.answer(build_request_summary(draft), reply_markup=_nikah_ask_confirm_keyboard(lang_code))


@router.callback_query(F.data == "nikah_ask_attach")
async def handle_nikah_ask_attach(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    nikah_scholar_attachments.pop(callback.from_user.id, None)
    await state.set_state(NikahAskFlow.waiting_for_attachments)
    await callback.message.answer(
        f"📎 Пришлите документы (PDF/фото). Можно до {MAX_ATTACHMENTS} файлов.\n"
        "Когда закончите — нажмите «✅ Готово».",
        reply_markup=_nikah_ask_done_keyboard(lang_code),
    )


@router.callback_query(F.data == "nikah_ask_submit")
async def handle_nikah_ask_submit(
    callback: CallbackQuery,
    state: FSMContext,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    data = await state.get_data()
    attachments = nikah_scholar_attachments.get(callback.from_user.id) or []

    request_type = str(data.get("ask_type") or "text").strip().lower()
    if request_type == "fatwa":
        request_type = "text"
    if request_type not in {"video", "text", "docs"}:
        request_type = "text"

    ok = await _submit_scholar_request(
        db=db,
        bot=callback.bot,
        telegram_user=callback.from_user,
        lang_code=lang_code,
        request_type=request_type,  # type: ignore[arg-type]
        data=dict(data, context="nikah"),
        attachments=attachments,
    )
    await create_work_item(
        db,
        topic="nikah",
        kind="scholar_request",
        created_by_user_id=callback.from_user.id,
        target_user_id=callback.from_user.id,
        payload={
            "request_type": request_type,
            "data": dict(data),
            "attachments_count": len(attachments),
        },
    )

    nikah_scholar_attachments.pop(callback.from_user.id, None)
    await state.clear()
    await callback.message.answer(
        "✅ Заявка отправлена. Ожидайте ответа учёного."
        if ok
        else "⚠️ Не удалось отправить заявку в группу, но заявка сохранена. Мы свяжемся с вами.",
        reply_markup=_nikah_menu_kb(lang_code),
    )
