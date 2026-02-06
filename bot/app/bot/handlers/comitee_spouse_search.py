from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot.states.comitee import (
    SpouseAskFlow,
    SpouseConversationFlow,
    SpouseProfileFlow,
    SpouseSearchFlow,
    SpouseWaliLinkFlow,
)
from app.infrastructure.database.db import DB
from app.infrastructure.database.models.user import UserModel
from app.services.i18n.localization import get_text
from app.services.scholar_requests.service import (
    MAX_ATTACHMENTS,
    ScholarAttachment,
    ScholarRequestDraft,
    build_request_summary,
)

from .comitee_common import is_cancel_command, user_language
from .comitee_menu import INLINE_MENU_BY_KEY, build_inline_keyboard
from .comitee_nikah import _submit_scholar_request
from app.services.work_items.service import create_work_item

logger = logging.getLogger(__name__)
router = Router(name="comitee.spouse_search")

CATEGORY = "SpouseSearch"
DOC_PROFILE = "SpouseProfile"
DOC_WALI_CODE = "SpouseWaliLinkCode"
DOC_WALI_LINK = "SpouseWaliLink"
DOC_REQUEST = "SpouseRequest"
DOC_EVENT = "SpouseEvent"

spouse_scholar_attachments: Dict[int, List[ScholarAttachment]] = {}

CONTACT_RE = re.compile(r"(@[a-zA-Z0-9_]{4,})|(https?://\\S+)|(t\\.me/\\S+)|(\\+?\\d[\\d\\s()\\-]{7,}\\d)")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _menu_kb(lang_code: str) -> InlineKeyboardMarkup:
    menu = INLINE_MENU_BY_KEY["menu.spouse_search"]
    return build_inline_keyboard(menu, lang_code)


def _cancel_to_menu_kb(lang_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="spouse_cancel")],
            [InlineKeyboardButton(text=get_text("button.back", lang_code), callback_data="menu:menu.spouse_search")],
        ]
    )


def _rules_text() -> str:
    return (
        "🔐 Шариат-защита\n\n"
        "❌ нет приватных чатов мужчины и женщины\n"
        "❌ нет фото лица, видео лица, контента, вызывающего страсть\n"
        "❌ нет скрытых контактов и обмена телефонами/юзернеймами\n"
        "❌ нет переписок без контроля вали/куратора\n"
        "❌ нет «лайков» и механики знакомств ради развлечения\n\n"
        "✅ Схема: запрос → разрешение вали → общение втроём → решение → никах"
    )


async def _load_latest_profile(db: DB, user_id: int) -> Optional[dict[str, Any]]:
    docs = await db.documents.get_user_documents_by_type(user_id=user_id, doc_type=DOC_PROFILE)
    if not docs:
        return None
    docs.sort(key=lambda d: int(d.get("id") or 0), reverse=True)
    try:
        content = (docs[0].get("content") or b"").decode("utf-8", errors="replace")
        return json.loads(content)
    except Exception:
        return None


async def _load_all_profiles(db: DB) -> list[dict[str, Any]]:
    docs = await db.documents.get_documents_by_category(category=CATEGORY)
    items: list[dict[str, Any]] = []
    for doc in docs:
        if (doc.get("type") or "") != DOC_PROFILE:
            continue
        try:
            content = (doc.get("content") or b"").decode("utf-8", errors="replace")
            profile = json.loads(content)
            profile["_document_id"] = doc.get("id")
            items.append(profile)
        except Exception:
            continue
    return items


async def _load_latest_wali_links(db: DB) -> dict[int, int]:
    docs = await db.documents.get_documents_by_category(category=CATEGORY)
    by_bride: dict[int, tuple[int, int]] = {}
    for doc in docs:
        if (doc.get("type") or "") != DOC_WALI_LINK:
            continue
        try:
            payload = json.loads((doc.get("content") or b"").decode("utf-8", errors="replace"))
            bride_user_id = int(payload.get("bride_user_id") or 0)
            wali_user_id = int(payload.get("wali_user_id") or 0)
            if not bride_user_id or not wali_user_id:
                continue
            doc_id = int(doc.get("id") or 0)
            current = by_bride.get(bride_user_id)
            if current is None or doc_id > current[0]:
                by_bride[bride_user_id] = (doc_id, wali_user_id)
        except Exception:
            continue
    return {bride: wali for bride, (_, wali) in by_bride.items()}


async def _find_wali_code_owner(db: DB, code: str) -> Optional[int]:
    code = code.strip()
    docs = await db.documents.get_documents_by_category(category=CATEGORY)
    best: tuple[int, int] | None = None
    for doc in docs:
        if (doc.get("type") or "") != DOC_WALI_CODE:
            continue
        try:
            payload = json.loads((doc.get("content") or b"").decode("utf-8", errors="replace"))
            if str(payload.get("code") or "").strip() != code:
                continue
            bride_user_id = int(payload.get("bride_user_id") or 0)
            if not bride_user_id:
                continue
            doc_id = int(doc.get("id") or 0)
            if best is None or doc_id > best[0]:
                best = (doc_id, bride_user_id)
        except Exception:
            continue
    return best[1] if best else None


async def _get_request_by_id(db: DB, request_id: int) -> Optional[dict[str, Any]]:
    docs = await db.documents.get_documents_by_category(category=CATEGORY)
    best: tuple[int, dict[str, Any]] | None = None
    for doc in docs:
        if (doc.get("type") or "") != DOC_REQUEST:
            continue
        try:
            payload = json.loads((doc.get("content") or b"").decode("utf-8", errors="replace"))
            if int(payload.get("request_id") or 0) != request_id:
                continue
            doc_id = int(doc.get("id") or 0)
            if best is None or doc_id > best[0]:
                best = (doc_id, payload)
        except Exception:
            continue
    return best[1] if best else None


async def _save_event(db: DB, *, user_id: int, name: str, payload: dict[str, Any]) -> None:
    filename = f"spouse_event_{user_id}_{uuid.uuid4().hex}.json"
    await db.documents.add_document(
        filename=filename,
        user_id=user_id,
        category=CATEGORY,
        name=name,
        content=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        doc_type=DOC_EVENT,
    )


def _profile_summary(profile: dict[str, Any]) -> str:
    parts = [
        "🌿 Анкета",
        f"Пол: {profile.get('gender') or '—'}",
        f"Имя: {profile.get('name') or '—'}",
        f"Возраст: {profile.get('age') or '—'}",
        f"Страна/город: {profile.get('location') or '—'}",
        f"Семейное положение: {profile.get('marital_status') or '—'}",
        f"Есть вали/махрам: {profile.get('wali_presence') or '—'}",
        f"Требования: {profile.get('requirements') or '—'}",
        f"Переезд: {profile.get('relocation') or '—'}",
        f"Публикация: {'✅ Да' if profile.get('published') else '⛔ Нет'}",
    ]
    if profile.get("gender") == "Женщина":
        parts.append(f"Контакт вали/махрама (для вас): {profile.get('wali_contact') or '—'}")
        parts.append(f"Вали привязан к боту: {'✅ Да' if profile.get('wali_user_id') else '⛔ Нет'}")
    return "\n".join(parts)


@router.callback_query(F.data == "spouse_cancel")
async def handle_spouse_cancel(callback: CallbackQuery, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await state.clear()
    spouse_scholar_attachments.pop(callback.from_user.id, None)
    await callback.message.answer(get_text("menu.spouse_search.title", lang_code), reply_markup=_menu_kb(lang_code))


@router.callback_query(F.data == "spouse_rules")
async def handle_spouse_rules(callback: CallbackQuery, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await callback.message.answer(_rules_text(), reply_markup=_menu_kb(lang_code))


@router.callback_query(F.data == "spouse_profile")
async def handle_spouse_profile(callback: CallbackQuery, state: FSMContext, db: DB, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await state.clear()
    profile = await _load_latest_profile(db, callback.from_user.id)
    if not profile:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📝 Создать анкету", callback_data="spouse_profile_create")],
                [InlineKeyboardButton(text="🔗 Я вали/махрам (привязать код)", callback_data="spouse_wali_link")],
                [InlineKeyboardButton(text=get_text("button.back", lang_code), callback_data="menu:menu.spouse_search")],
            ]
        )
        await callback.message.answer("Анкета ещё не создана.", reply_markup=kb)
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Изменить анкету", callback_data="spouse_profile_create")],
            [
                InlineKeyboardButton(
                    text="✅ Показать в поиске" if not profile.get("published") else "⛔ Скрыть из поиска",
                    callback_data="spouse_profile_toggle_publish",
                )
            ],
            [InlineKeyboardButton(text="🔗 Я вали/махрам (привязать код)", callback_data="spouse_wali_link")],
            [InlineKeyboardButton(text=get_text("button.back", lang_code), callback_data="menu:menu.spouse_search")],
        ]
    )
    await callback.message.answer(_profile_summary(profile), reply_markup=kb)


@router.callback_query(F.data == "spouse_profile_toggle_publish")
async def handle_spouse_profile_toggle_publish(
    callback: CallbackQuery,
    state: FSMContext,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    _ = state
    profile = await _load_latest_profile(db, callback.from_user.id)
    if not profile:
        await callback.message.answer("Сначала создайте анкету.", reply_markup=_menu_kb(lang_code))
        return
    profile["published"] = not bool(profile.get("published"))
    profile["updated_at"] = _now_iso()
    filename = f"spouse_profile_{callback.from_user.id}_{uuid.uuid4().hex}.json"
    await db.documents.add_document(
        filename=filename,
        user_id=callback.from_user.id,
        category=CATEGORY,
        name="Spouse profile",
        content=json.dumps(profile, ensure_ascii=False, indent=2).encode("utf-8"),
        doc_type=DOC_PROFILE,
    )
    await callback.message.answer("Готово.", reply_markup=_menu_kb(lang_code))


@router.callback_query(F.data == "spouse_profile_create")
async def handle_spouse_profile_create_start(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await state.clear()
    await state.set_state(SpouseProfileFlow.waiting_for_gender)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👳 Мужчина", callback_data="spouse_gender:male")],
            [InlineKeyboardButton(text="🧕 Женщина", callback_data="spouse_gender:female")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="spouse_cancel")],
        ]
    )
    await callback.message.answer("Укажите пол:", reply_markup=kb)


@router.callback_query(F.data.startswith("spouse_gender:"))
async def handle_spouse_profile_gender(callback: CallbackQuery, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    choice = (callback.data or "").split(":", 1)[-1].strip().lower()
    if choice not in {"male", "female"}:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    await callback.answer()
    await state.update_data(gender="Мужчина" if choice == "male" else "Женщина")
    await state.set_state(SpouseProfileFlow.waiting_for_name)
    await callback.message.answer("Введите имя (можно без фамилии):", reply_markup=_cancel_to_menu_kb(lang_code))


@router.message(SpouseProfileFlow.waiting_for_name)
async def handle_spouse_profile_name(message: Message, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("menu.spouse_search.title", lang_code), reply_markup=_menu_kb(lang_code))
        return
    text = (message.text or "").strip()
    if not text or len(text) < 2:
        await message.answer("Введите имя (минимум 2 символа).")
        return
    await state.update_data(name=text)
    await state.set_state(SpouseProfileFlow.waiting_for_age)
    await message.answer("Возраст:", reply_markup=_cancel_to_menu_kb(lang_code))


@router.message(SpouseProfileFlow.waiting_for_age)
async def handle_spouse_profile_age(message: Message, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("menu.spouse_search.title", lang_code), reply_markup=_menu_kb(lang_code))
        return
    try:
        age = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введите возраст числом.")
        return
    if age < 16 or age > 80:
        await message.answer("Введите возраст в диапазоне 16–80.")
        return
    await state.update_data(age=age)
    await state.set_state(SpouseProfileFlow.waiting_for_location)
    await message.answer("Страна/город:", reply_markup=_cancel_to_menu_kb(lang_code))


@router.message(SpouseProfileFlow.waiting_for_location)
async def handle_spouse_profile_location(message: Message, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("menu.spouse_search.title", lang_code), reply_markup=_menu_kb(lang_code))
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Введите страну/город.")
        return
    await state.update_data(location=text)
    await state.set_state(SpouseProfileFlow.waiting_for_marital_status)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Никогда не был(а) в браке", callback_data="spouse_marital:single")],
            [InlineKeyboardButton(text="Разведён(а)", callback_data="spouse_marital:divorced")],
            [InlineKeyboardButton(text="Вдовец/вдова", callback_data="spouse_marital:widowed")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="spouse_cancel")],
        ]
    )
    await message.answer("Семейное положение:", reply_markup=kb)


@router.callback_query(F.data.startswith("spouse_marital:"))
async def handle_spouse_profile_marital(callback: CallbackQuery, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    choice = (callback.data or "").split(":", 1)[-1].strip().lower()
    mapping = {
        "single": "Никогда не был(а) в браке",
        "divorced": "Разведён(а)",
        "widowed": "Вдовец/вдова",
    }
    if choice not in mapping:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    await callback.answer()
    await state.update_data(marital_status=mapping[choice])
    await state.set_state(SpouseProfileFlow.waiting_for_wali_presence)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да", callback_data="spouse_wali_presence:yes")],
            [InlineKeyboardButton(text="❌ Нет", callback_data="spouse_wali_presence:no")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="spouse_cancel")],
        ]
    )
    await callback.message.answer("Есть ли махрам/вали?", reply_markup=kb)


@router.callback_query(F.data.startswith("spouse_wali_presence:"))
async def handle_spouse_profile_wali_presence(callback: CallbackQuery, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    choice = (callback.data or "").split(":", 1)[-1].strip().lower()
    if choice not in {"yes", "no"}:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    await callback.answer()
    await state.update_data(wali_presence="Да" if choice == "yes" else "Нет")
    await state.set_state(SpouseProfileFlow.waiting_for_requirements)
    await callback.message.answer(
        "Основные религиозные требования (намаз, хиджаб, отказ от сигарет и т.д.).\nОдним сообщением:",
        reply_markup=_cancel_to_menu_kb(lang_code),
    )


@router.message(SpouseProfileFlow.waiting_for_requirements)
async def handle_spouse_profile_requirements(message: Message, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("menu.spouse_search.title", lang_code), reply_markup=_menu_kb(lang_code))
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Введите требования текстом.")
        return
    await state.update_data(requirements=text)
    await state.set_state(SpouseProfileFlow.waiting_for_relocation)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да", callback_data="spouse_reloc:yes")],
            [InlineKeyboardButton(text="❌ Нет", callback_data="spouse_reloc:no")],
            [InlineKeyboardButton(text="🤝 Обсуждаемо", callback_data="spouse_reloc:maybe")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="spouse_cancel")],
        ]
    )
    await message.answer("Готов(а) к переезду?", reply_markup=kb)


@router.callback_query(F.data.startswith("spouse_reloc:"))
async def handle_spouse_profile_relocation(callback: CallbackQuery, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    choice = (callback.data or "").split(":", 1)[-1].strip().lower()
    mapping = {"yes": "Да", "no": "Нет", "maybe": "Обсуждаемо"}
    if choice not in mapping:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    await callback.answer()
    await state.update_data(relocation=mapping[choice])
    data = await state.get_data()
    if data.get("gender") == "Женщина":
        await state.set_state(SpouseProfileFlow.waiting_for_wali_contact)
        await callback.message.answer(
            "Введите контакт вали/махрама (как текст: @username или телефон).\n"
            "⚠️ Для доставки запросов вали должен открыть бота и привязать код.",
            reply_markup=_cancel_to_menu_kb(lang_code),
        )
        return
    await state.set_state(SpouseProfileFlow.waiting_for_publish)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, показывать", callback_data="spouse_publish:yes")],
            [InlineKeyboardButton(text="⛔ Нет, скрыть", callback_data="spouse_publish:no")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="spouse_cancel")],
        ]
    )
    await callback.message.answer("Показывать анкету в поиске?", reply_markup=kb)


@router.message(SpouseProfileFlow.waiting_for_wali_contact)
async def handle_spouse_profile_wali_contact(message: Message, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("menu.spouse_search.title", lang_code), reply_markup=_menu_kb(lang_code))
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Введите контакт (текстом).")
        return
    await state.update_data(wali_contact=text)
    await state.set_state(SpouseProfileFlow.waiting_for_publish)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, показывать", callback_data="spouse_publish:yes")],
            [InlineKeyboardButton(text="⛔ Нет, скрыть", callback_data="spouse_publish:no")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="spouse_cancel")],
        ]
    )
    await message.answer("Показывать анкету в поиске?", reply_markup=kb)


@router.callback_query(F.data.startswith("spouse_publish:"))
async def handle_spouse_profile_publish(
    callback: CallbackQuery,
    state: FSMContext,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    choice = (callback.data or "").split(":", 1)[-1].strip().lower()
    if choice not in {"yes", "no"}:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    await callback.answer()
    data = await state.get_data()
    profile: dict[str, Any] = {
        "user_id": callback.from_user.id,
        "gender": data.get("gender"),
        "name": data.get("name"),
        "age": data.get("age"),
        "location": data.get("location"),
        "marital_status": data.get("marital_status"),
        "wali_presence": data.get("wali_presence"),
        "requirements": data.get("requirements"),
        "relocation": data.get("relocation"),
        "wali_contact": data.get("wali_contact"),
        "wali_user_id": None,
        "published": choice == "yes",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }

    wali_links = await _load_latest_wali_links(db)
    if profile.get("gender") == "Женщина":
        profile["wali_user_id"] = wali_links.get(callback.from_user.id)

    filename = f"spouse_profile_{callback.from_user.id}_{uuid.uuid4().hex}.json"
    await db.documents.add_document(
        filename=filename,
        user_id=callback.from_user.id,
        category=CATEGORY,
        name="Spouse profile",
        content=json.dumps(profile, ensure_ascii=False, indent=2).encode("utf-8"),
        doc_type=DOC_PROFILE,
    )

    await state.clear()
    await callback.message.answer(_profile_summary(profile), reply_markup=_menu_kb(lang_code))

    if profile.get("gender") == "Женщина" and profile.get("wali_presence") == "Да" and not profile.get("wali_user_id"):
        code = f"{uuid.uuid4().int % 1_000_000:06d}"
        code_filename = f"spouse_wali_code_{callback.from_user.id}_{uuid.uuid4().hex}.json"
        await db.documents.add_document(
            filename=code_filename,
            user_id=callback.from_user.id,
            category=CATEGORY,
            name="Wali link code",
            content=json.dumps(
                {"bride_user_id": callback.from_user.id, "code": code, "created_at": _now_iso()},
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8"),
            doc_type=DOC_WALI_CODE,
        )
        await callback.message.answer(
            "🔗 Привязка вали/махрама\n\n"
            "Передайте этот код вашему вали/махраму и попросите его:\n"
            "1) открыть бота и нажать /start\n"
            "2) зайти в «🌿 Знакомство…» → «📝 Моя анкета» → «🔗 Я вали/махрам»\n"
            f"3) ввести код: `{code}`",
            reply_markup=_menu_kb(lang_code),
        )


@router.callback_query(F.data == "spouse_wali_link")
async def handle_spouse_wali_link_start(callback: CallbackQuery, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await state.clear()
    await state.set_state(SpouseWaliLinkFlow.waiting_for_code)
    await callback.message.answer("Введите код привязки (6 цифр):", reply_markup=_cancel_to_menu_kb(lang_code))


@router.message(SpouseWaliLinkFlow.waiting_for_code)
async def handle_spouse_wali_link_code(message: Message, state: FSMContext, db: DB, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("menu.spouse_search.title", lang_code), reply_markup=_menu_kb(lang_code))
        return
    code = (message.text or "").strip()
    if not (code.isdigit() and len(code) == 6):
        await message.answer("Код должен быть из 6 цифр.")
        return
    bride_user_id = await _find_wali_code_owner(db, code)
    if not bride_user_id:
        await message.answer("Код не найден или устарел.")
        return
    if bride_user_id == message.from_user.id:
        await message.answer("Нельзя привязать самого себя как вали.")
        return

    filename = f"spouse_wali_link_{bride_user_id}_{message.from_user.id}_{uuid.uuid4().hex}.json"
    await db.documents.add_document(
        filename=filename,
        user_id=message.from_user.id,
        category=CATEGORY,
        name="Wali link",
        content=json.dumps(
            {"bride_user_id": bride_user_id, "wali_user_id": message.from_user.id, "linked_at": _now_iso()},
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8"),
        doc_type=DOC_WALI_LINK,
    )
    await state.clear()
    await message.answer("✅ Привязка выполнена. Теперь запросы будут приходить вам.", reply_markup=_menu_kb(lang_code))
    try:
        await message.bot.send_message(
            chat_id=bride_user_id,
            text="✅ Ваш вали/махрам успешно привязан к боту. Теперь запросы будут приходить ему.",
        )
    except Exception:
        logger.exception("Failed to notify bride about wali link")


def _card_text(profile: dict[str, Any]) -> str:
    gender = profile.get("gender") or "—"
    age = profile.get("age") or "—"
    location = profile.get("location") or "—"
    marital = profile.get("marital_status") or "—"
    requirements = (profile.get("requirements") or "—").strip()
    relocation = profile.get("relocation") or "—"
    if len(requirements) > 280:
        requirements = requirements[:280].rstrip() + "…"
    return (
        "🌿 Кандидат\n\n"
        f"Пол: {gender}\n"
        f"Возраст: {age}\n"
        f"Страна/город: {location}\n"
        f"Семейное положение: {marital}\n"
        f"Требования/религиозность: {requirements}\n"
        f"Переезд: {relocation}\n\n"
        "⚠️ Контакты не показываются. Запрос отправляется вали/махраму."
    )


@router.callback_query(F.data == "spouse_search")
async def handle_spouse_search_start(callback: CallbackQuery, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await state.clear()
    await state.set_state(SpouseSearchFlow.waiting_for_country)
    await callback.message.answer("🔎 Поиск\n\nВведите страну (можно страна/город):", reply_markup=_cancel_to_menu_kb(lang_code))


@router.message(SpouseSearchFlow.waiting_for_country)
async def handle_spouse_search_country(message: Message, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("menu.spouse_search.title", lang_code), reply_markup=_menu_kb(lang_code))
        return
    country = (message.text or "").strip()
    if not country:
        await message.answer("Введите страну.")
        return
    await state.update_data(country=country)
    await state.set_state(SpouseSearchFlow.waiting_for_age_range)
    await message.answer("Возрастной диапазон (например: 20-35):", reply_markup=_cancel_to_menu_kb(lang_code))


@router.message(SpouseSearchFlow.waiting_for_age_range)
async def handle_spouse_search_age_range(message: Message, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("menu.spouse_search.title", lang_code), reply_markup=_menu_kb(lang_code))
        return
    raw = (message.text or "").strip().replace(" ", "")
    m = re.fullmatch(r"(\\d{1,2})-(\\d{1,2})", raw)
    if not m:
        await message.answer("Введите диапазон в формате 20-35.")
        return
    lo = int(m.group(1))
    hi = int(m.group(2))
    if lo < 16 or hi > 80 or lo > hi:
        await message.answer("Диапазон должен быть в пределах 16–80.")
        return
    await state.update_data(age_lo=lo, age_hi=hi)
    await state.set_state(SpouseSearchFlow.waiting_for_marital_status)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Любое", callback_data="spouse_s_marital:any")],
            [InlineKeyboardButton(text="Никогда не был(а) в браке", callback_data="spouse_s_marital:single")],
            [InlineKeyboardButton(text="Разведён(а)", callback_data="spouse_s_marital:divorced")],
            [InlineKeyboardButton(text="Вдовец/вдова", callback_data="spouse_s_marital:widowed")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="spouse_cancel")],
        ]
    )
    await message.answer("Семейное положение:", reply_markup=kb)


@router.callback_query(F.data.startswith("spouse_s_marital:"))
async def handle_spouse_search_marital(callback: CallbackQuery, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    choice = (callback.data or "").split(":", 1)[-1].strip().lower()
    mapping = {
        "any": None,
        "single": "Никогда не был(а) в браке",
        "divorced": "Разведён(а)",
        "widowed": "Вдовец/вдова",
    }
    if choice not in mapping:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    await callback.answer()
    await state.update_data(marital_filter=mapping[choice])
    await state.set_state(SpouseSearchFlow.waiting_for_prayer)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Любое", callback_data="spouse_s_pray:any")],
            [InlineKeyboardButton(text="Молится", callback_data="spouse_s_pray:yes")],
            [InlineKeyboardButton(text="Не молится", callback_data="spouse_s_pray:no")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="spouse_cancel")],
        ]
    )
    await callback.message.answer("Религиозность (по намазу):", reply_markup=kb)


@router.callback_query(F.data.startswith("spouse_s_pray:"))
async def handle_spouse_search_prayer(callback: CallbackQuery, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    choice = (callback.data or "").split(":", 1)[-1].strip().lower()
    if choice not in {"any", "yes", "no"}:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    await callback.answer()
    await state.update_data(prayer_filter=choice)
    await state.set_state(SpouseSearchFlow.waiting_for_relocation)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Любое", callback_data="spouse_s_reloc:any")],
            [InlineKeyboardButton(text="Готов(а) к переезду", callback_data="spouse_s_reloc:yes")],
            [InlineKeyboardButton(text="Не готов(а)", callback_data="spouse_s_reloc:no")],
            [InlineKeyboardButton(text="Обсуждаемо", callback_data="spouse_s_reloc:maybe")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="spouse_cancel")],
        ]
    )
    await callback.message.answer("Готовность к переезду:", reply_markup=kb)


async def _send_search_card(message: Message, state: FSMContext, db: DB, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, message.from_user)
    data = await state.get_data()
    ids = data.get("result_ids") or []
    pos = int(data.get("result_pos") or 0)
    if pos < 0 or pos >= len(ids):
        await message.answer("Результаты закончились.", reply_markup=_menu_kb(lang_code))
        return
    doc_id = int(ids[pos])
    doc = await db.documents.get_document_by_id(document_id=doc_id)
    if not doc:
        await message.answer("Анкета недоступна.", reply_markup=_menu_kb(lang_code))
        return
    profile = json.loads((doc.get("content") or b"").decode("utf-8", errors="replace"))
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✉️ Запрос на связь", callback_data=f"spouse_request:{doc_id}")],
            [InlineKeyboardButton(text="➡️ Следующий", callback_data="spouse_next")],
            [InlineKeyboardButton(text="🔎 Изменить фильтры", callback_data="spouse_search")],
            [InlineKeyboardButton(text=get_text("button.back", lang_code), callback_data="menu:menu.spouse_search")],
        ]
    )
    await message.answer(_card_text(profile), reply_markup=kb)


@router.callback_query(F.data.startswith("spouse_s_reloc:"))
async def handle_spouse_search_relocation(
    callback: CallbackQuery,
    state: FSMContext,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    choice = (callback.data or "").split(":", 1)[-1].strip().lower()
    if choice not in {"any", "yes", "no", "maybe"}:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    await callback.answer()
    await state.update_data(relocation_filter=choice)

    data = await state.get_data()
    profiles = await _load_all_profiles(db)

    results: list[dict[str, Any]] = []
    for profile in profiles:
        if not profile.get("published"):
            continue
        if profile.get("user_id") == callback.from_user.id:
            continue
        if profile.get("gender") != "Женщина":
            continue
        if data.get("country") and str(data["country"]).lower() not in str(profile.get("location") or "").lower():
            continue
        age = int(profile.get("age") or 0)
        if not (int(data.get("age_lo") or 0) <= age <= int(data.get("age_hi") or 999)):
            continue
        marital = data.get("marital_filter")
        if marital and profile.get("marital_status") != marital:
            continue
        prayer = data.get("prayer_filter")
        req = str(profile.get("requirements") or "").lower()
        if prayer == "yes" and "намаз" not in req:
            continue
        if prayer == "no" and "намаз" in req:
            continue
        reloc_filter = data.get("relocation_filter")
        if reloc_filter != "any":
            mapping = {"yes": "Да", "no": "Нет", "maybe": "Обсуждаемо"}
            if profile.get("relocation") != mapping.get(reloc_filter):
                continue
        results.append(profile)

    results.sort(key=lambda p: (int(p.get("age") or 0), str(p.get("location") or "")))
    ids = [int(p.get("_document_id") or 0) for p in results if p.get("_document_id")]
    await state.update_data(result_ids=ids, result_pos=0)
    await state.set_state(SpouseSearchFlow.showing_results)
    if not ids:
        await callback.message.answer("Ничего не найдено по фильтрам.", reply_markup=_menu_kb(lang_code))
        return
    await _send_search_card(callback.message, state, db, user_row)


@router.callback_query(F.data == "spouse_next")
async def handle_spouse_next(callback: CallbackQuery, state: FSMContext, db: DB, user_row: Optional[UserModel]) -> None:
    await callback.answer()
    data = await state.get_data()
    await state.update_data(result_pos=int(data.get("result_pos") or 0) + 1)
    if callback.message:
        await _send_search_card(callback.message, state, db, user_row)


@router.callback_query(F.data.startswith("spouse_request:"))
async def handle_spouse_request(callback: CallbackQuery, db: DB, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    try:
        profile_doc_id = int((callback.data or "").split(":", 1)[-1])
    except ValueError:
        await callback.message.answer(get_text("error.request.invalid", lang_code), reply_markup=_menu_kb(lang_code))
        return
    profile_doc = await db.documents.get_document_by_id(document_id=profile_doc_id)
    if not profile_doc:
        await callback.message.answer("Анкета недоступна.", reply_markup=_menu_kb(lang_code))
        return
    profile = json.loads((profile_doc.get("content") or b"").decode("utf-8", errors="replace"))
    bride_user_id = int(profile.get("user_id") or 0)
    if not bride_user_id:
        await callback.message.answer("Анкета недоступна.", reply_markup=_menu_kb(lang_code))
        return

    wali_links = await _load_latest_wali_links(db)
    wali_user_id = wali_links.get(bride_user_id)

    request_id = uuid.uuid4().int % 100000
    payload = {
        "request_id": request_id,
        "male_user_id": callback.from_user.id,
        "bride_user_id": bride_user_id,
        "profile_document_id": profile_doc_id,
        "status": "pending",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    filename = f"spouse_request_{callback.from_user.id}_{request_id}_{uuid.uuid4().hex}.json"
    await db.documents.add_document(
        filename=filename,
        user_id=callback.from_user.id,
        category=CATEGORY,
        name=f"Spouse request #{request_id}",
        content=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        doc_type=DOC_REQUEST,
    )

    if not wali_user_id:
        payload["status"] = "delivery_failed"
        payload["updated_at"] = _now_iso()
        filename2 = f"spouse_request_{callback.from_user.id}_{request_id}_{uuid.uuid4().hex}.json"
        await db.documents.add_document(
            filename=filename2,
            user_id=callback.from_user.id,
            category=CATEGORY,
            name=f"Spouse request #{request_id} (delivery_failed)",
            content=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
            doc_type=DOC_REQUEST,
        )
        await callback.message.answer(
            "⚠️ Запрос не доставлен: вали/махрам не привязан к боту.\n"
            "Попросите кандидатку привязать вали через код — после этого запросы будут доставляться.",
            reply_markup=_menu_kb(lang_code),
        )
        return

    text = (
        "Ассаляму алейкум.\n"
        f"Брат {callback.from_user.full_name}, намерение — никах.\n"
        "Просит разрешение пообщаться.\n\n"
        f"Кандидатка: {profile.get('age') or '—'} лет, {profile.get('location') or '—'}.\n"
        f"Заметки: {str(profile.get('requirements') or '').strip()[:300]}"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✔️ Разрешаю", callback_data=f"spouse_req_approve:{request_id}")],
            [InlineKeyboardButton(text="❌ Нет, не подходит", callback_data=f"spouse_req_decline:{request_id}")],
            [InlineKeyboardButton(text="❓ Хочу задать вопросы сначала", callback_data=f"spouse_req_questions:{request_id}")],
        ]
    )
    try:
        await callback.bot.send_message(chat_id=wali_user_id, text=text, reply_markup=kb)
        await callback.message.answer("✅ Запрос отправлен вали/махраму.", reply_markup=_menu_kb(lang_code))
    except Exception:
        logger.exception("Failed to send spouse request to wali")
        payload["status"] = "delivery_failed"
        payload["updated_at"] = _now_iso()
        filename3 = f"spouse_request_{callback.from_user.id}_{request_id}_{uuid.uuid4().hex}.json"
        await db.documents.add_document(
            filename=filename3,
            user_id=callback.from_user.id,
            category=CATEGORY,
            name=f"Spouse request #{request_id} (delivery_failed_send)",
            content=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
            doc_type=DOC_REQUEST,
        )
        await callback.message.answer("⚠️ Не удалось доставить запрос вали. Попробуйте позже.", reply_markup=_menu_kb(lang_code))


async def _update_request_status(db: DB, *, request: dict[str, Any], status: str, actor_user_id: int) -> None:
    request = dict(request)
    request["status"] = status
    request["updated_at"] = _now_iso()
    request["last_actor_user_id"] = actor_user_id
    filename = f"spouse_request_{actor_user_id}_{request.get('request_id')}_{uuid.uuid4().hex}.json"
    await db.documents.add_document(
        filename=filename,
        user_id=int(request.get("male_user_id") or actor_user_id),
        category=CATEGORY,
        name=f"Spouse request #{request.get('request_id')} ({status})",
        content=json.dumps(request, ensure_ascii=False, indent=2).encode("utf-8"),
        doc_type=DOC_REQUEST,
    )


@router.callback_query(F.data.startswith("spouse_req_decline:"))
async def handle_spouse_req_decline(callback: CallbackQuery, db: DB, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    try:
        request_id = int((callback.data or "").split(":", 1)[-1])
    except ValueError:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    req = await _get_request_by_id(db, request_id)
    if not req:
        await callback.message.answer("Запрос не найден.")
        return
    await _update_request_status(db, request=req, status="declined", actor_user_id=callback.from_user.id)
    try:
        await callback.bot.send_message(chat_id=int(req["male_user_id"]), text="❌ Вали отказал в общении.")
    except Exception:
        logger.exception("Failed to notify male about decline")
    await callback.message.answer("Отказ отправлен.")


@router.callback_query(F.data.startswith("spouse_req_questions:"))
async def handle_spouse_req_questions(callback: CallbackQuery, db: DB, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    try:
        request_id = int((callback.data or "").split(":", 1)[-1])
    except ValueError:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    req = await _get_request_by_id(db, request_id)
    if not req:
        await callback.message.answer("Запрос не найден.")
        return
    await _update_request_status(db, request=req, status="questions", actor_user_id=callback.from_user.id)
    await callback.message.answer(
        "❓ Вы выбрали режим вопросов.\n"
        "Откройте диалог и задайте вопросы (контакты и ссылки запрещены).",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="💬 Открыть диалог", callback_data=f"spouse_conv_open:{request_id}")]]
        ),
    )


@router.callback_query(F.data.startswith("spouse_req_approve:"))
async def handle_spouse_req_approve(callback: CallbackQuery, db: DB, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    try:
        request_id = int((callback.data or "").split(":", 1)[-1])
    except ValueError:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    req = await _get_request_by_id(db, request_id)
    if not req:
        await callback.message.answer("Запрос не найден.")
        return
    await _update_request_status(db, request=req, status="approved", actor_user_id=callback.from_user.id)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="💬 Открыть диалог", callback_data=f"spouse_conv_open:{request_id}")]]
    )
    try:
        await callback.bot.send_message(
            chat_id=int(req["male_user_id"]),
            text="✔️ Вали разрешил общение. Откройте диалог (только втроём, без контактов).",
            reply_markup=kb,
        )
    except Exception:
        logger.exception("Failed to notify male about approve")
    try:
        await callback.bot.send_message(
            chat_id=int(req["bride_user_id"]),
            text="✔️ Ваш вали разрешил общение. Откройте диалог (только втроём, без контактов).",
            reply_markup=kb,
        )
    except Exception:
        logger.exception("Failed to notify bride about approve")
    await callback.message.answer("✅ Разрешение отправлено. Диалог доступен участникам.", reply_markup=_menu_kb(lang_code))


@router.callback_query(F.data.startswith("spouse_conv_open:"))
async def handle_spouse_conv_open(callback: CallbackQuery, state: FSMContext, db: DB, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    try:
        request_id = int((callback.data or "").split(":", 1)[-1])
    except ValueError:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return

    req = await _get_request_by_id(db, request_id)
    if not req:
        await callback.message.answer("Диалог не найден.")
        return

    bride_user_id = int(req.get("bride_user_id") or 0)
    male_user_id = int(req.get("male_user_id") or 0)
    participants = {bride_user_id, male_user_id}
    wali_links = await _load_latest_wali_links(db)
    expected_wali = wali_links.get(bride_user_id)
    if expected_wali:
        participants.add(int(expected_wali))
    if callback.from_user.id not in participants:
        await callback.message.answer("Нет доступа к диалогу.")
        return

    await state.clear()
    await state.set_state(SpouseConversationFlow.active)
    await state.update_data(request_id=request_id)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Мы готовы перейти к никаху", callback_data=f"spouse_to_nikah:{request_id}")],
            [InlineKeyboardButton(text="❌ Завершить", callback_data=f"spouse_conv_close:{request_id}")],
            [InlineKeyboardButton(text=get_text("button.back", lang_code), callback_data="menu:menu.spouse_search")],
        ]
    )
    await callback.message.answer(
        "💬 Диалог открыт.\n"
        "Правила: коротко, по делу, без контактов и флирта. Голосовые/медиа запрещены.",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("spouse_conv_close:"))
async def handle_spouse_conv_close(callback: CallbackQuery, state: FSMContext, db: DB, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    try:
        request_id = int((callback.data or "").split(":", 1)[-1])
    except ValueError:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    await _save_event(
        db,
        user_id=callback.from_user.id,
        name="Spouse conversation closed",
        payload={"request_id": request_id, "action": "closed", "at": _now_iso()},
    )
    await state.clear()
    await callback.message.answer("Диалог завершён.", reply_markup=_menu_kb(lang_code))


@router.callback_query(F.data.startswith("spouse_to_nikah:"))
async def handle_spouse_to_nikah(callback: CallbackQuery, state: FSMContext, db: DB, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    try:
        request_id = int((callback.data or "").split(":", 1)[-1])
    except ValueError:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    await _save_event(
        db,
        user_id=callback.from_user.id,
        name="Spouse to nikah",
        payload={"request_id": request_id, "action": "to_nikah", "at": _now_iso()},
    )
    await state.clear()
    await callback.message.answer(
        "✅ Хорошо. Переходим в раздел «👰🤵 Никях».",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="👰🤵 Открыть «Никах»", callback_data="menu:menu.nikah")],
                [InlineKeyboardButton(text=get_text("button.back", lang_code), callback_data="menu:menu.spouse_search")],
            ]
        ),
    )


@router.message(SpouseConversationFlow.active)
async def handle_spouse_conversation_message(
    message: Message,
    state: FSMContext,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("menu.spouse_search.title", lang_code), reply_markup=_menu_kb(lang_code))
        return

    if not message.text:
        await message.answer("Можно отправлять только текстовые сообщения.")
        return

    text = (message.text or "").strip()
    if not text:
        return
    if len(text) > 800:
        await message.answer("Сообщение слишком длинное (лимит 800 символов).")
        return
    if CONTACT_RE.search(text):
        await message.answer("⚠️ Нельзя отправлять контакты, ссылки или телефоны. Сформулируйте иначе.")
        await _save_event(
            db,
            user_id=message.from_user.id,
            name="Spouse moderation: contacts blocked",
            payload={"text": text[:500], "at": _now_iso()},
        )
        await create_work_item(
            db,
            topic="spouse_search",
            kind="moderation_incident",
            created_by_user_id=message.from_user.id,
            target_user_id=message.from_user.id,
            priority="high",
            payload={"reason": "contacts_blocked", "text": text[:500]},
        )
        return

    data = await state.get_data()
    request_id = int(data.get("request_id") or 0)
    req = await _get_request_by_id(db, request_id)
    if not req:
        await message.answer("Диалог недоступен.", reply_markup=_menu_kb(lang_code))
        await state.clear()
        return

    bride_user_id = int(req.get("bride_user_id") or 0)
    male_user_id = int(req.get("male_user_id") or 0)
    recipients = {bride_user_id, male_user_id}
    wali_links = await _load_latest_wali_links(db)
    expected_wali = wali_links.get(bride_user_id)
    if expected_wali:
        recipients.add(int(expected_wali))
    recipients.discard(message.from_user.id)

    for rid in recipients:
        try:
            await message.bot.send_message(chat_id=rid, text=f"💬 {message.from_user.full_name}:\n{text}")
        except Exception:
            logger.exception("Failed to forward spouse conversation message to %s", rid)


@router.callback_query(F.data == "spouse_requests")
async def handle_spouse_requests(callback: CallbackQuery, db: DB, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    docs = await db.documents.get_documents_by_category(category=CATEGORY)
    requests: list[dict[str, Any]] = []
    for doc in docs:
        if (doc.get("type") or "") != DOC_REQUEST:
            continue
        try:
            payload = json.loads((doc.get("content") or b"").decode("utf-8", errors="replace"))
            requests.append(payload)
        except Exception:
            continue

    latest: dict[int, dict[str, Any]] = {}
    for r in requests:
        rid = int(r.get("request_id") or 0)
        if not rid:
            continue
        current = latest.get(rid)
        if current is None or str(r.get("updated_at") or "") > str(current.get("updated_at") or ""):
            latest[rid] = r

    wali_links = await _load_latest_wali_links(db)
    incoming: list[dict[str, Any]] = []
    outgoing: list[dict[str, Any]] = []
    for r in latest.values():
        if int(r.get("male_user_id") or 0) == callback.from_user.id:
            outgoing.append(r)
            continue
        bride_user_id = int(r.get("bride_user_id") or 0)
        if wali_links.get(bride_user_id) == callback.from_user.id:
            incoming.append(r)

    outgoing.sort(key=lambda x: str(x.get("updated_at") or ""), reverse=True)
    incoming.sort(key=lambda x: str(x.get("updated_at") or ""), reverse=True)

    lines: list[str] = ["📨 Мои запросы", ""]
    if outgoing:
        lines.append("Исходящие:")
        for r in outgoing[:10]:
            lines.append(f"- #{r.get('request_id')} статус: {r.get('status')}")
        lines.append("")
    if incoming:
        lines.append("Входящие (как вали):")
        for r in incoming[:10]:
            lines.append(f"- #{r.get('request_id')} статус: {r.get('status')}")
        lines.append("")
    if not outgoing and not incoming:
        lines.append("Пока нет запросов.")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="spouse_requests")],
            [InlineKeyboardButton(text=get_text("button.back", lang_code), callback_data="menu:menu.spouse_search")],
        ]
    )
    await callback.message.answer("\n".join(lines).strip(), reply_markup=kb)


def _ask_menu_kb(lang_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎥 Запросить видеоконференцию (Zoom/Meet)", callback_data="spouse_ask_type:video")],
            [InlineKeyboardButton(text="💬 Оставить вопрос текстом", callback_data="spouse_ask_type:text")],
            [InlineKeyboardButton(text="📎 Приложить документы", callback_data="spouse_ask_type:docs")],
            [InlineKeyboardButton(text=get_text("button.back", lang_code), callback_data="menu:menu.spouse_search")],
        ]
    )


def _ask_done_kb(lang_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Готово", callback_data="spouse_ask_docs_done")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="spouse_cancel")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="spouse_ask")],
        ]
    )


def _ask_confirm_kb(lang_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Отправить", callback_data="spouse_ask_submit")],
            [InlineKeyboardButton(text="📎 Приложить документы", callback_data="spouse_ask_attach")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="spouse_ask")],
        ]
    )


@router.callback_query(F.data == "spouse_ask")
async def handle_spouse_ask_start(callback: CallbackQuery, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await state.clear()
    spouse_scholar_attachments.pop(callback.from_user.id, None)
    await state.set_state(SpouseAskFlow.waiting_for_request_type)
    await callback.message.answer(
        "🤝 Вы можете задать вопрос учёному.\n"
        "Опишите ситуацию подробно.\n"
        "Вам ответит шариатский эксперт или будет назначено видеослушание.",
        reply_markup=_ask_menu_kb(lang_code),
    )


@router.callback_query(F.data.startswith("spouse_ask_type:"))
async def handle_spouse_ask_type(callback: CallbackQuery, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    choice = (callback.data or "").split(":", 1)[-1].strip().lower()
    if choice not in {"video", "text", "docs"}:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    await callback.answer()
    await state.update_data(ask_type=choice)
    if choice == "video":
        await state.set_state(SpouseAskFlow.waiting_for_video_time)
        await callback.message.answer("🎥 Укажите удобное время/интервал для видеосвязи.", reply_markup=_cancel_to_menu_kb(lang_code))
    elif choice == "text":
        await state.set_state(SpouseAskFlow.waiting_for_text_question)
        await callback.message.answer("💬 Опишите вопрос текстом.", reply_markup=_cancel_to_menu_kb(lang_code))
    else:
        spouse_scholar_attachments.pop(callback.from_user.id, None)
        await state.set_state(SpouseAskFlow.waiting_for_attachments)
        await callback.message.answer(
            f"📎 Пришлите документы (PDF/фото). Можно до {MAX_ATTACHMENTS} файлов.\nКогда закончите — нажмите «✅ Готово».",
            reply_markup=_ask_done_kb(lang_code),
        )


@router.message(SpouseAskFlow.waiting_for_text_question)
async def handle_spouse_ask_text_question(message: Message, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        spouse_scholar_attachments.pop(message.from_user.id, None)
        await message.answer(get_text("menu.spouse_search.title", lang_code), reply_markup=_menu_kb(lang_code))
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Опишите вопрос текстом.")
        return
    await state.update_data(ask_text=text, context="spouse_search", ask_type="text")
    data = await state.get_data()
    attachments = spouse_scholar_attachments.get(message.from_user.id) or []
    draft = ScholarRequestDraft(request_type="text", data=data, attachments=attachments)
    await message.answer(build_request_summary(draft), reply_markup=_ask_confirm_kb(lang_code))


@router.message(SpouseAskFlow.waiting_for_video_time)
async def handle_spouse_ask_video_time(message: Message, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        spouse_scholar_attachments.pop(message.from_user.id, None)
        await message.answer(get_text("menu.spouse_search.title", lang_code), reply_markup=_menu_kb(lang_code))
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Укажите время/интервал.")
        return
    await state.update_data(ask_video_time=text, context="spouse_search", ask_type="video")
    await state.set_state(SpouseAskFlow.waiting_for_video_contact)
    await message.answer("📞 Укажите контакт для связи (тел/username/почта).", reply_markup=_cancel_to_menu_kb(lang_code))


@router.message(SpouseAskFlow.waiting_for_video_contact)
async def handle_spouse_ask_video_contact(message: Message, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        spouse_scholar_attachments.pop(message.from_user.id, None)
        await message.answer(get_text("menu.spouse_search.title", lang_code), reply_markup=_menu_kb(lang_code))
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Укажите контакт.")
        return
    await state.update_data(ask_video_contact=text, ask_type="video", context="spouse_search")
    await state.set_state(SpouseAskFlow.waiting_for_video_description)
    await message.answer("📝 Коротко опишите ситуацию.", reply_markup=_cancel_to_menu_kb(lang_code))


@router.message(SpouseAskFlow.waiting_for_video_description)
async def handle_spouse_ask_video_description(message: Message, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        spouse_scholar_attachments.pop(message.from_user.id, None)
        await message.answer(get_text("menu.spouse_search.title", lang_code), reply_markup=_menu_kb(lang_code))
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Опишите ситуацию.")
        return
    await state.update_data(ask_video_description=text, ask_type="video", context="spouse_search")
    data = await state.get_data()
    attachments = spouse_scholar_attachments.get(message.from_user.id) or []
    draft = ScholarRequestDraft(request_type="video", data=data, attachments=attachments)
    await message.answer(build_request_summary(draft), reply_markup=_ask_confirm_kb(lang_code))


async def _extract_attachment(message: Message) -> Optional[ScholarAttachment]:
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
    stream = await message.bot.download_file(file.file_path)
    content = stream.read() if stream else b""
    if not content:
        return None
    return ScholarAttachment(content=content, filename=filename, content_type=content_type)


@router.message(SpouseAskFlow.waiting_for_attachments)
async def handle_spouse_ask_attachments(message: Message, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        spouse_scholar_attachments.pop(message.from_user.id, None)
        await message.answer(get_text("menu.spouse_search.title", lang_code), reply_markup=_menu_kb(lang_code))
        return
    extracted = await _extract_attachment(message)
    if extracted is None:
        await message.answer("Пришлите PDF или фото.")
        return
    items = spouse_scholar_attachments.setdefault(message.from_user.id, [])
    if len(items) >= MAX_ATTACHMENTS:
        await message.answer(f"Достигнут лимит {MAX_ATTACHMENTS} файлов. Нажмите «✅ Готово».")
        return
    items.append(extracted)
    await message.answer(f"Добавлено файлов: {len(items)}", reply_markup=_ask_done_kb(lang_code))


@router.callback_query(F.data == "spouse_ask_docs_done")
async def handle_spouse_ask_docs_done(callback: CallbackQuery, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await state.update_data(ask_type="docs", context="spouse_search")
    await state.set_state(SpouseAskFlow.waiting_for_attachments_description)
    await callback.message.answer("📝 Добавьте описание к документам.", reply_markup=_cancel_to_menu_kb(lang_code))


@router.message(SpouseAskFlow.waiting_for_attachments_description)
async def handle_spouse_ask_docs_description(message: Message, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        spouse_scholar_attachments.pop(message.from_user.id, None)
        await message.answer(get_text("menu.spouse_search.title", lang_code), reply_markup=_menu_kb(lang_code))
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Добавьте описание.")
        return
    await state.update_data(ask_docs_description=text, ask_type="docs", context="spouse_search")
    data = await state.get_data()
    attachments = spouse_scholar_attachments.get(message.from_user.id) or []
    draft = ScholarRequestDraft(request_type="docs", data=data, attachments=attachments)
    await message.answer(build_request_summary(draft), reply_markup=_ask_confirm_kb(lang_code))


@router.callback_query(F.data == "spouse_ask_attach")
async def handle_spouse_ask_attach(callback: CallbackQuery, state: FSMContext, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await state.set_state(SpouseAskFlow.waiting_for_attachments)
    await callback.message.answer(
        f"📎 Пришлите документы (PDF/фото). Можно до {MAX_ATTACHMENTS} файлов.\nКогда закончите — нажмите «✅ Готово».",
        reply_markup=_ask_done_kb(lang_code),
    )


@router.callback_query(F.data == "spouse_ask_submit")
async def handle_spouse_ask_submit(callback: CallbackQuery, state: FSMContext, db: DB, user_row: Optional[UserModel]) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    data = await state.get_data()
    attachments = spouse_scholar_attachments.get(callback.from_user.id) or []
    request_type = str(data.get("ask_type") or "text").strip().lower()
    if request_type not in {"video", "text", "docs"}:
        request_type = "text"
    ok = await _submit_scholar_request(
        db=db,
        bot=callback.bot,
        telegram_user=callback.from_user,
        lang_code=lang_code,
        request_type=request_type,  # type: ignore[arg-type]
        data=dict(data, context="spouse_search"),
        attachments=attachments,
    )
    await create_work_item(
        db,
        topic="spouse_search",
        kind="scholar_request",
        created_by_user_id=callback.from_user.id,
        target_user_id=callback.from_user.id,
        payload={"request_type": request_type, "attachments_count": len(attachments)},
    )
    spouse_scholar_attachments.pop(callback.from_user.id, None)
    await state.clear()
    await callback.message.answer(
        "✅ Заявка отправлена. Ожидайте ответа учёного."
        if ok
        else "⚠️ Не удалось отправить заявку в группу, но заявка сохранена. Мы свяжемся с вами.",
        reply_markup=_menu_kb(lang_code),
    )
