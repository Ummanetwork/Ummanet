
from __future__ import annotations

import io
import json
import logging
import os
import re
from urllib.parse import quote_plus
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from secrets import choice as secrets_choice
from typing import Any, Iterable, Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.bot.states.comitee import CourtCaseEditFlow, CourtCaseMediateFlow, CourtClaimFlow
from app.infrastructure.database.db import DB
from app.infrastructure.database.models.user import UserModel
from app.services.i18n.localization import get_text
from app.services.work_items.service import create_work_item

from .comitee_common import is_cancel_command, safe_state_clear, user_language
from .comitee_menu import INLINE_MENU_BY_KEY, build_inline_keyboard
from config.config import settings

logger = logging.getLogger(__name__)

router = Router(name="comitee.courts")

CATEGORY_KEYS = {
    "financial": "courts.category.financial",
    "contract_breach": "courts.category.contract_breach",
    "property": "courts.category.property",
    "goods": "courts.category.goods",
    "services": "courts.category.services",
    "family": "courts.category.family",
    "ethics": "courts.category.ethics",
}

EVIDENCE_LIMIT = 15
_CLOSED_STATUSES = {"closed", "cancelled"}
PROHIBITED_WORDS = {
    "дурак",
    "идиот",
    "тварь",
    "сука",
    "мразь",
    "урод",
    "убью",
    "угрожаю",
}
INTEREST_WORDS = {"процент", "проценты", "ростовщ", "риба", "переплата"}
UNCLEAR_WORDS = {"неясн", "непонят", "без договора", "не договорились"}
INVITE_CODE_LENGTH = 6


def _scholars_group_id() -> int:
    try:
        value = getattr(settings.bot, "SCHOLARS_GROUP_ID", None)
        if value is None:
            value = getattr(settings.bot, "scholars_group_id", 0)
        return int(value or 0)
    except (AttributeError, TypeError, ValueError):
        return 0


def _category_label(lang_code: str, slug: str) -> str:
    key = CATEGORY_KEYS.get(slug, "courts.category.unknown")
    return get_text(key, lang_code)


def _build_category_keyboard(lang_code: str) -> InlineKeyboardMarkup:
    buttons = [
        ["financial", "contract_breach"],
        ["property", "goods"],
        ["services", "family"],
        ["ethics"],
    ]
    keyboard = []
    for row in buttons:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=_category_label(lang_code, slug),
                    callback_data=f"courts:category:{slug}",
                )
                for slug in row
            ]
        )
    keyboard.append(
        [
            InlineKeyboardButton(
                text=get_text("button.back", lang_code),
                callback_data="menu:menu.courts",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def _build_contract_keyboard(lang_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("button.yes.upload", lang_code),
                    callback_data="courts:contract:yes",
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("button.no", lang_code),
                    callback_data="courts:contract:no",
                )
            ],
        ]
    )


def _build_family_keyboard(lang_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("courts.family.inheritance", lang_code),
                    callback_data="courts:family:inheritance",
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("courts.family.nikah", lang_code),
                    callback_data="courts:family:nikah",
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("courts.family.no", lang_code),
                    callback_data="courts:family:no",
                )
            ],
        ]
    )


def _build_evidence_keyboard(lang_code: str, *, include_skip: bool = True) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                text=get_text("button.courts.evidence.photo", lang_code),
                callback_data="courts:evidence:photo",
            )
        ],
        [
            InlineKeyboardButton(
                text=get_text("button.courts.evidence.link", lang_code),
                callback_data="courts:evidence:link",
            )
        ],
        [
            InlineKeyboardButton(
                text=get_text("button.courts.evidence.audio", lang_code),
                callback_data="courts:evidence:audio",
            )
        ],
        [
            InlineKeyboardButton(
                text=get_text("button.courts.evidence.text", lang_code),
                callback_data="courts:evidence:text",
            )
        ],
    ]
    if include_skip:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=get_text("button.courts.evidence.skip", lang_code),
                    callback_data="courts:evidence:skip",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def _contains_personal_data(text: str) -> bool:
    lowered = text.lower()
    if any(word in lowered for word in ("паспорт", "адрес", "улиц", "дом ", "квартир", "серия")):
        return True
    digits = re.sub(r"\D", "", text)
    return len(digits) >= 6


def _contains_prohibited_content(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in PROHIBITED_WORDS)


def _generate_invite_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets_choice(alphabet) for _ in range(INVITE_CODE_LENGTH))


async def _resolve_bot_username(bot: Any) -> str | None:
    username = getattr(bot, "username", None)
    if username:
        return username
    try:
        me = await bot.get_me()
        return getattr(me, "username", None)
    except Exception:
        return None


def _case_role(case: dict[str, Any], user_id: int) -> str:
    if case.get("plaintiff_id") == user_id or case.get("user_id") == user_id:
        return "plaintiff"
    if case.get("defendant_id") == user_id:
        return "defendant"
    participants = case.get("participants") or []
    if isinstance(participants, str):
        try:
            participants = json.loads(participants)
        except json.JSONDecodeError:
            participants = []
    if user_id in participants:
        return "participant"
    return "unknown"


def _case_participants(case: dict[str, Any]) -> set[int]:
    participants = case.get("participants") or []
    if isinstance(participants, str):
        try:
            participants = json.loads(participants)
        except json.JSONDecodeError:
            participants = []
    result: set[int] = set()
    for item in participants or []:
        try:
            result.add(int(item))
        except (TypeError, ValueError):
            continue
    for key in ("plaintiff_id", "defendant_id", "user_id"):
        value = case.get(key)
        if value:
            try:
                result.add(int(value))
            except (TypeError, ValueError):
                continue
    return result


def _resolve_scholar_observer(case: dict[str, Any]) -> Optional[int]:
    value = case.get("scholar_contact")
    if isinstance(value, (int, float)):
        return int(value) if value else None
    if isinstance(value, str):
        raw = value.strip()
        if raw.startswith("+"):
            raw = raw[1:]
        if raw.isdigit():
            return int(raw)
    return None


def _pdf_font_path() -> Optional[str]:
    candidates = [
        os.getenv("CHAT_PDF_FONT_PATH"),
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\times.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def _wrap_pdf_text(text: str, *, font_name: str, font_size: int, max_width: float) -> list[str]:
    from reportlab.pdfbase import pdfmetrics

    if not text:
        return [""]
    lines: list[str] = []
    for paragraph in text.splitlines():
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
            if pdfmetrics.stringWidth(word, font_name, font_size) <= max_width:
                current = word
                continue
            chunk = ""
            for ch in word:
                candidate = f"{chunk}{ch}"
                if pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_width:
                    chunk = candidate
                else:
                    if chunk:
                        lines.append(chunk)
                    chunk = ch
            current = chunk
        if current:
            lines.append(current)
    return lines


def _render_chat_pdf(lines: list[str]) -> Optional[bytes]:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas
    except Exception:
        logger.exception("reportlab is not available for chat PDF")
        return None

    buffer = io.BytesIO()
    page_width, page_height = A4
    margin = 48
    font_path = _pdf_font_path()
    font_name = "Helvetica"
    if font_path:
        try:
            pdfmetrics.registerFont(TTFont("ChatFont", font_path))
            font_name = "ChatFont"
        except Exception:
            logger.exception("Failed to register PDF font")

    title_size = 14
    body_size = 10
    line_height = body_size + 4
    canvas_obj = canvas.Canvas(buffer, pagesize=A4)
    y = page_height - margin
    max_width = page_width - margin * 2

    for idx, raw in enumerate(lines):
        size = title_size if idx == 0 else body_size
        canvas_obj.setFont(font_name, size)
        for wrapped in _wrap_pdf_text(raw, font_name=font_name, font_size=size, max_width=max_width):
            if y < margin:
                canvas_obj.showPage()
                y = page_height - margin
                canvas_obj.setFont(font_name, size)
            canvas_obj.drawString(margin, y, wrapped)
            y -= line_height
        y -= 4

    canvas_obj.save()
    return buffer.getvalue()


def _normalize_mediate_log(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        return [raw]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except Exception:
            return []
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
        if isinstance(parsed, dict):
            return [parsed]
    return []


def _build_mediate_pdf_lines(
    *,
    case: dict[str, Any],
    log: list[dict[str, Any]],
    lang_code: str,
) -> list[str]:
    case_number = case.get("case_number") or case.get("id") or "-"
    title = get_text("courts.mediate.pdf.title", lang_code, case_number=case_number)
    lines = [
        title,
        get_text("courts.mediate.pdf.plaintiff", lang_code, name=case.get("plaintiff") or "-"),
        get_text("courts.mediate.pdf.defendant", lang_code, name=case.get("defendant") or "-"),
        get_text(
            "courts.mediate.pdf.category",
            lang_code,
            name=_category_label(lang_code, str(case.get("category") or "")),
        ),
        get_text("courts.mediate.pdf.generated", lang_code, timestamp=datetime.now(timezone.utc).isoformat()),
        "",
    ]
    for entry in log:
        ts = entry.get("ts") or ""
        name = entry.get("name") or "-"
        text = entry.get("text") or ""
        kind = entry.get("kind") or "text"
        if kind == "media":
            label = get_text("courts.mediate.pdf.media", lang_code)
            line = f"[{ts}] {name}: {label}"
            lines.append(line)
            if text:
                lines.append(text)
        else:
            line = f"[{ts}] {name}: {text}"
            lines.append(line)
    return lines


async def _send_mediate_history(
    *,
    bot: Any,
    chat_id: int,
    log: list[dict[str, Any]],
    lang_code: str,
) -> None:
    if not log:
        return
    title = get_text("courts.case.mediate.history.title", lang_code)
    lines: list[str] = [title]
    for entry in log:
        ts = entry.get("ts") or ""
        name = entry.get("name") or "-"
        kind = entry.get("kind") or "text"
        text = entry.get("text") or ""
        if kind == "media":
            label = get_text("courts.case.mediate.history.media", lang_code)
            line = f"[{ts}] {name}: {label}"
            if text:
                line = f"{line} ({text})"
        else:
            line = f"[{ts}] {name}: {text}"
        lines.append(line)

    max_len = 3500
    current = ""
    for line in lines:
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > max_len:
            await bot.send_message(chat_id=chat_id, text=current)
            current = line
        else:
            current = candidate
    if current:
        await bot.send_message(chat_id=chat_id, text=current)


async def _finalize_mediate_chat(
    *,
    bot: Any,
    db: DB,
    case_id: int,
    lang_code: str,
    notify_chat_id: int,
) -> None:
    log = _normalize_mediate_log(await db.court_cases.get_mediate_log(case_id=case_id))
    if not log:
        await bot.send_message(chat_id=notify_chat_id, text=get_text("courts.case.mediate.pdf.empty", lang_code))
        return
    case = await db.court_cases.get_case_by_id(case_id=case_id)
    if not case:
        await bot.send_message(chat_id=notify_chat_id, text=get_text("courts.case.not_found", lang_code))
        return
    lines = _build_mediate_pdf_lines(case=case, log=log, lang_code=lang_code)
    pdf_bytes = _render_chat_pdf(lines)
    if not pdf_bytes:
        await bot.send_message(chat_id=notify_chat_id, text=get_text("courts.case.mediate.pdf.failed", lang_code))
        return
    case_number = case.get("case_number") or case_id
    filename = f"court_chat_{case_number}.pdf"
    try:
        sent = await bot.send_document(
            chat_id=notify_chat_id,
            document=BufferedInputFile(pdf_bytes, filename=filename),
            caption=get_text("courts.case.mediate.pdf.saved", lang_code),
        )
    except Exception:
        logger.exception("Failed to send chat PDF for case %s", case_id)
        await bot.send_message(chat_id=notify_chat_id, text=get_text("courts.case.mediate.pdf.failed", lang_code))
        return
    file = getattr(sent, "document", None)
    file_id = getattr(file, "file_id", None)
    if not file_id:
        await bot.send_message(chat_id=notify_chat_id, text=get_text("courts.case.mediate.pdf.failed", lang_code))
        return
    evidence_item = _evidence_item(
        kind="chat_pdf",
        uploaded_by=int(notify_chat_id),
        uploaded_role="participant",
        file_id=file_id,
        file_name=filename,
        mime_type="application/pdf",
        size=len(pdf_bytes),
        caption=get_text("courts.case.mediate.pdf.caption", lang_code, case_number=case_number),
    )
    await db.court_cases.append_evidence(case_id=case_id, evidence_item=evidence_item)


def _build_mediate_keyboard(lang_code: str, *, case_id: int, mode: str) -> InlineKeyboardMarkup:
    if mode == "join":
        button = InlineKeyboardButton(
            text=get_text("button.courts.mediate.join", lang_code),
            callback_data=f"courts:case:{case_id}:mediate_join",
        )
    else:
        button = InlineKeyboardButton(
            text=get_text("button.courts.mediate.stop", lang_code),
            callback_data=f"courts:case:{case_id}:mediate_stop",
        )
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


async def _notify_mediate_start(
    *,
    bot: Any,
    case: dict[str, Any],
    initiator: Any,
    lang_code: str,
) -> None:
    recipients = _case_participants(case)
    scholar_id = _resolve_scholar_observer(case)
    if scholar_id:
        recipients.add(scholar_id)
    recipients.discard(int(getattr(initiator, "id", 0) or 0))
    if not recipients:
        return
    case_number = case.get("case_number") or case.get("id") or "-"
    name = getattr(initiator, "full_name", None) or getattr(initiator, "username", None) or "-"
    text = get_text(
        "courts.case.mediate.notice",
        lang_code,
        case_number=case_number,
        name=name,
    )
    keyboard = _build_mediate_keyboard(lang_code, case_id=int(case.get("id") or 0), mode="join")
    for recipient_id in recipients:
        try:
            await bot.send_message(chat_id=int(recipient_id), text=text, reply_markup=keyboard)
        except Exception:
            logger.exception("Failed to notify mediate chat for %s", recipient_id)


def _opponent_name(case: dict[str, Any], user_id: int) -> str:
    role = _case_role(case, user_id)
    if role == "defendant":
        return case.get("plaintiff") or "-"
    return case.get("defendant") or "-"


def _parse_amount(text: str) -> Decimal | None:
    cleaned = text.strip().lower()
    if cleaned in {"нет", "не указано", "не знаю"}:
        return None
    cleaned = cleaned.replace(" ", "").replace(",", ".")
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    if value <= 0:
        return None
    return value


def _evidence_item(
    *,
    kind: str,
    uploaded_by: int | None = None,
    uploaded_role: str | None = None,
    file_id: str | None = None,
    file_name: str | None = None,
    mime_type: str | None = None,
    size: int | None = None,
    text: str | None = None,
    url: str | None = None,
    caption: str | None = None,
) -> dict[str, Any]:
    return {
        "type": kind,
        "uploaded_by": uploaded_by,
        "uploaded_role": uploaded_role,
        "file_id": file_id,
        "file_name": file_name,
        "mime_type": mime_type,
        "size": size,
        "text": text,
        "url": url,
        "caption": caption,
        "created_at": datetime.utcnow().isoformat(timespec="seconds"),
    }


def _build_confirmation(data: dict[str, Any], lang_code: str) -> str:
    amount = data.get("amount")
    evidence = data.get("evidence") or []
    amount_text = str(amount) if amount is not None else get_text("courts.amount.none", lang_code)
    return get_text(
        "courts.confirmation",
        lang_code,
        plaintiff=data.get("plaintiff_name", "-"),
        defendant=data.get("defendant_name", "-"),
        category=_category_label(lang_code, str(data.get("category") or "")),
        claim_text=data.get("claim_text_full") or data.get("claim_text", "-"),
        amount=amount_text,
        evidence_count=len(evidence),
    )


def _sharia_check(claim_text: str, category: str) -> tuple[str, str | None]:
    lowered = claim_text.lower()
    if any(word in lowered for word in INTEREST_WORDS):
        return "block", "courts.sharia.blocked"
    if _contains_prohibited_content(claim_text):
        return "block", "courts.sharia.blocked"
    if len(claim_text.strip()) < 20:
        return "clarify", "courts.sharia.clarify"
    if any(word in lowered for word in UNCLEAR_WORDS):
        return "clarify", "courts.sharia.clarify"
    if category == "family":
        return "ok", None
    return "ok", None


async def _show_cases(
    message: Message,
    *,
    cases: Iterable[dict[str, Any]],
    lang_code: str,
    empty_key: str,
    user_id: int,
) -> None:
    items = list(cases)
    if not items:
        await message.answer(get_text(empty_key, lang_code))
        return
    for item in items:
        case_id = int(item.get("id") or 0)
        case_number = item.get("case_number") or f"{case_id}"
        category = _category_label(lang_code, str(item.get("category") or ""))
        defendant = _opponent_name(item, user_id)
        status_key = f"courts.status.{item.get('status') or 'open'}"
        status_label = get_text(status_key, lang_code)
        text = get_text(
            "courts.case.list.item",
            lang_code,
            case_number=case_number,
            category=category,
            defendant=defendant,
            status=status_label,
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=get_text("button.courts.details.more", lang_code),
                        callback_data=f"courts:case:{case_id}",
                    )
                ]
            ]
        )
        await message.answer(text, reply_markup=keyboard)


def _build_case_details(item: dict[str, Any], lang_code: str) -> str:
    case_number = item.get("case_number") or str(item.get("id") or "")
    category = _category_label(lang_code, str(item.get("category") or ""))
    evidence = item.get("evidence") or []
    claim = item.get("claim") or "-"
    status_key = f"courts.status.{item.get('status') or 'open'}"
    status_label = get_text(status_key, lang_code)
    scholar = item.get("scholar_name") or get_text("courts.scholar.unassigned", lang_code)
    contact = item.get("scholar_contact") or get_text("courts.scholar.contact.none", lang_code)
    return get_text(
        "courts.case.details",
        lang_code,
        case_number=case_number,
        category=category,
        status=status_label,
        claim=claim,
        evidence_count=len(evidence),
        scholar=scholar,
        contact=contact,
    )


async def _forward_case_to_scholars(
    *,
    bot: Any,
    lang_code: str,
    case: dict[str, Any],
    user: Any,
) -> bool:
    group_id = _scholars_group_id()
    if not group_id:
        return False


async def _send_case_evidence(
    *,
    bot: Any,
    message: Message,
    lang_code: str,
    evidence: list[dict[str, Any]],
) -> None:
    if not evidence:
        await message.answer(get_text("courts.evidence.empty", lang_code))
        return
    await message.answer(get_text("courts.evidence.list.title", lang_code))
    for item in evidence:
        kind = (item or {}).get("type")
        if kind in {"text", "link"}:
            text = (item or {}).get("text") or (item or {}).get("url")
            if text:
                await message.answer(
                    get_text("courts.case.forward.evidence.text", lang_code, text=text),
                )
            continue
        file_id = (item or {}).get("file_id")
        caption = (item or {}).get("caption")
        if not file_id:
            continue
        if kind in {"photo", "contract_photo"}:
            await bot.send_photo(chat_id=message.chat.id, photo=file_id, caption=caption)
        elif kind in {"audio"}:
            await bot.send_audio(chat_id=message.chat.id, audio=file_id, caption=caption)
        elif kind in {"voice"}:
            await bot.send_voice(chat_id=message.chat.id, voice=file_id, caption=caption)
        else:
            await bot.send_document(chat_id=message.chat.id, document=file_id, caption=caption)
    evidence = case.get("evidence") or []
    if isinstance(evidence, str):
        try:
            evidence = json.loads(evidence)
        except json.JSONDecodeError:
            evidence = []
    username = f"@{user.username}" if getattr(user, "username", None) else "-"
    summary = get_text(
        "courts.case.forward.summary",
        lang_code,
        case_number=case.get("case_number") or case.get("id"),
        plaintiff=case.get("plaintiff") or "-",
        defendant=case.get("defendant") or "-",
        category=_category_label(lang_code, str(case.get("category") or "")),
        claim=case.get("claim") or "-",
        amount=str(case.get("amount")) if case.get("amount") is not None else get_text("courts.amount.none", lang_code),
        evidence_count=len(evidence),
        full_name=getattr(user, "full_name", "-"),
        username=username,
        user_id=getattr(user, "id", "-"),
    )
    try:
        await bot.send_message(chat_id=group_id, text=summary)
        for item in evidence:
            kind = (item or {}).get("type")
            if kind in {"text", "link"}:
                text = (item or {}).get("text") or (item or {}).get("url")
                if text:
                    await bot.send_message(
                        chat_id=group_id,
                        text=get_text("courts.case.forward.evidence.text", lang_code, text=text),
                    )
                continue
            file_id = (item or {}).get("file_id")
            caption = (item or {}).get("caption")
            if not file_id:
                continue
            if kind in {"photo", "contract_photo"}:
                await bot.send_photo(chat_id=group_id, photo=file_id, caption=caption)
            elif kind in {"audio"}:
                await bot.send_audio(chat_id=group_id, audio=file_id, caption=caption)
            elif kind in {"voice"}:
                await bot.send_voice(chat_id=group_id, voice=file_id, caption=caption)
            else:
                await bot.send_document(chat_id=group_id, document=file_id, caption=caption)
        return True
    except Exception:
        logger.exception("Failed to forward case to scholars group")
        return False

@router.callback_query(F.data == "courts:file")
async def handle_courts_file(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await state.clear()
    await state.set_state(CourtClaimFlow.choosing_category)
    await callback.message.answer(
        get_text("courts.step.category", lang_code),
        reply_markup=_build_category_keyboard(lang_code),
    )


@router.callback_query(F.data.startswith("courts:category:"))
async def handle_courts_category(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    slug = (callback.data or "").split(":", 2)[-1].strip()
    if slug not in CATEGORY_KEYS:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    await state.update_data(category=slug)
    await state.set_state(CourtClaimFlow.waiting_for_plaintiff)
    await callback.message.answer(get_text("courts.step.plaintiff", lang_code))


@router.message(CourtClaimFlow.waiting_for_plaintiff)
async def handle_plaintiff(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    text = (message.text or "").strip()
    if not text:
        await message.answer(get_text("courts.error.name.empty", lang_code))
        return
    if _contains_personal_data(text):
        await message.answer(get_text("courts.error.personal_data", lang_code))
        return
    await state.update_data(plaintiff_name=text)
    await state.set_state(CourtClaimFlow.waiting_for_defendant)
    await message.answer(get_text("courts.step.defendant", lang_code))


@router.message(CourtClaimFlow.waiting_for_defendant)
async def handle_defendant(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    text = (message.text or "").strip()
    if not text:
        await message.answer(get_text("courts.error.name.empty", lang_code))
        return
    if _contains_personal_data(text):
        await message.answer(get_text("courts.error.personal_data", lang_code))
        return
    await state.update_data(defendant_name=text)
    await state.set_state(CourtClaimFlow.waiting_for_claim)
    await message.answer(get_text("courts.step.claim", lang_code))


@router.message(CourtClaimFlow.waiting_for_claim)
async def handle_claim(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    text = (message.text or "").strip()
    if not text:
        await message.answer(get_text("courts.error.claim.empty", lang_code))
        return
    data = await state.get_data()
    contract_context = data.get("contract_context") or {}
    if contract_context:
        contract_number = str(
            contract_context.get("contract_number")
            or contract_context.get("contract_id")
            or "-"
        )
        contract_title = str(contract_context.get("contract_title") or "-")
        prefix = get_text(
            "courts.claim.contract_prefix",
            lang_code,
            contract_number=contract_number,
            contract_title=contract_title,
        )
        await state.update_data(
            claim_text=text,
            claim_text_full=f"{prefix} {text}".strip(),
        )
    else:
        await state.update_data(claim_text=text)
    data = await state.get_data()
    category = str(data.get("category") or "")
    if category == "financial":
        await state.set_state(CourtClaimFlow.waiting_for_amount)
        await message.answer(get_text("courts.step.amount", lang_code))
        return
    if category in {"goods", "services"}:
        await state.set_state(CourtClaimFlow.waiting_for_contract_question)
        await message.answer(
            get_text("courts.step.contract", lang_code),
            reply_markup=_build_contract_keyboard(lang_code),
        )
        return
    if category == "family":
        await state.set_state(CourtClaimFlow.waiting_for_family_relation)
        await message.answer(
            get_text("courts.step.family", lang_code),
            reply_markup=_build_family_keyboard(lang_code),
        )
        return
    await state.set_state(CourtClaimFlow.waiting_for_evidence)
    await message.answer(
        get_text("courts.step.evidence", lang_code),
        reply_markup=_build_evidence_keyboard(lang_code),
    )


@router.message(CourtClaimFlow.waiting_for_amount)
async def handle_amount(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    text = (message.text or "").strip()
    amount = _parse_amount(text)
    if text.lower() not in {"нет", "не указано", "не знаю"} and amount is None:
        await message.answer(get_text("courts.error.amount.invalid", lang_code))
        return
    await state.update_data(amount=amount)
    await state.set_state(CourtClaimFlow.waiting_for_evidence)
    await message.answer(
        get_text("courts.step.evidence", lang_code),
        reply_markup=_build_evidence_keyboard(lang_code),
    )


@router.callback_query(CourtClaimFlow.waiting_for_contract_question, F.data.startswith("courts:contract:"))
async def handle_contract_question(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    choice = (callback.data or "").split(":", 2)[-1]
    if choice == "yes":
        await state.update_data(contract_present=True)
        await state.set_state(CourtClaimFlow.waiting_for_contract_file)
        await callback.message.answer(get_text("courts.step.contract.upload", lang_code))
        return
    await state.update_data(contract_present=False)
    await state.set_state(CourtClaimFlow.waiting_for_evidence)
    await callback.message.answer(
        get_text("courts.step.evidence", lang_code),
        reply_markup=_build_evidence_keyboard(lang_code),
    )


@router.message(CourtClaimFlow.waiting_for_contract_file)
async def handle_contract_file(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    document = message.document
    photo = message.photo[-1] if message.photo else None
    if document is None and photo is None:
        await message.answer(get_text("courts.error.contract.file", lang_code))
        return
    evidence: list[dict[str, Any]] = (await state.get_data()).get("evidence") or []
    if len(evidence) >= EVIDENCE_LIMIT:
        await message.answer(get_text("courts.error.evidence.limit", lang_code))
        return
    role = "plaintiff"
    if document is not None:
        item = _evidence_item(
            kind="contract",
            uploaded_by=message.from_user.id,
            uploaded_role=role,
            file_id=document.file_id,
            file_name=document.file_name,
            mime_type=document.mime_type,
            size=document.file_size,
            caption=message.caption,
        )
    else:
        item = _evidence_item(
            kind="contract_photo",
            uploaded_by=message.from_user.id,
            uploaded_role=role,
            file_id=photo.file_id,
            size=photo.file_size,
            caption=message.caption,
        )
    evidence.append(item)
    await state.update_data(evidence=evidence)
    await state.set_state(CourtClaimFlow.waiting_for_evidence)
    await message.answer(
        get_text("courts.step.evidence", lang_code),
        reply_markup=_build_evidence_keyboard(lang_code),
    )


@router.callback_query(CourtClaimFlow.waiting_for_family_relation, F.data.startswith("courts:family:"))
async def handle_family_relation(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    choice = (callback.data or "").split(":", 2)[-1]
    if choice == "inheritance":
        await state.clear()
        await callback.message.answer(
            get_text("courts.family.redirect", lang_code),
            reply_markup=build_inline_keyboard(INLINE_MENU_BY_KEY["menu.inheritance"], lang_code),
        )
        return
    if choice == "nikah":
        await state.clear()
        await callback.message.answer(
            get_text("courts.family.redirect", lang_code),
            reply_markup=build_inline_keyboard(INLINE_MENU_BY_KEY["menu.nikah"], lang_code),
        )
        return
    await state.set_state(CourtClaimFlow.waiting_for_evidence)
    await callback.message.answer(
        get_text("courts.step.evidence", lang_code),
        reply_markup=_build_evidence_keyboard(lang_code),
    )


@router.callback_query(F.data.startswith("courts:evidence:"))
async def handle_evidence_choice(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    choice = (callback.data or "").split(":", 2)[-1]
    if choice == "skip":
        if await state.get_state() == CourtClaimFlow.waiting_for_evidence:
            data = await state.get_data()
            await state.set_state(CourtClaimFlow.waiting_for_confirm)
            await callback.message.answer(
                _build_confirmation(data, lang_code),
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text=get_text("button.courts.confirm.send", lang_code),
                                callback_data="courts:confirm:send",
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text=get_text("button.courts.confirm.edit", lang_code),
                                callback_data="courts:confirm:edit",
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text=get_text("button.courts.confirm.cancel", lang_code),
                                callback_data="courts:confirm:cancel",
                            )
                        ],
                    ]
                ),
            )
        else:
            await callback.message.answer(
                get_text("courts.edit.done", lang_code),
                reply_markup=build_inline_keyboard(INLINE_MENU_BY_KEY["menu.courts"], lang_code),
            )
            await state.clear()
        return
    await state.update_data(evidence_mode=choice)
    prompt_key = f"courts.evidence.prompt.{choice}"
    await callback.message.answer(get_text(prompt_key, lang_code))


@router.message(CourtClaimFlow.waiting_for_evidence)
@router.message(CourtCaseEditFlow.waiting_for_evidence)
async def handle_evidence_input(
    message: Message,
    state: FSMContext,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    data = await state.get_data()
    mode = data.get("evidence_mode")
    evidence: list[dict[str, Any]] = data.get("evidence") or []
    if len(evidence) >= EVIDENCE_LIMIT:
        await message.answer(get_text("courts.error.evidence.limit", lang_code))
        return
    item: dict[str, Any] | None = None
    role = "plaintiff"
    case_id = data.get("edit_case_id")
    if case_id:
        case = await db.court_cases.get_case_by_id(
            case_id=int(case_id),
            user_id=message.from_user.id,
        )
        if case:
            role = _case_role(case, message.from_user.id)
    if mode == "photo":
        photo = message.photo[-1] if message.photo else None
        if photo is None:
            await message.answer(get_text("courts.error.evidence.photo", lang_code))
            return
        item = _evidence_item(
            kind="photo",
            uploaded_by=message.from_user.id,
            uploaded_role=role,
            file_id=photo.file_id,
            size=photo.file_size,
            caption=message.caption,
        )
    elif mode == "audio":
        audio = message.audio or message.voice
        if audio is None:
            await message.answer(get_text("courts.error.evidence.audio", lang_code))
            return
        item = _evidence_item(
            kind="audio" if message.audio else "voice",
            uploaded_by=message.from_user.id,
            uploaded_role=role,
            file_id=audio.file_id,
            file_name=getattr(audio, "file_name", None),
            mime_type=getattr(audio, "mime_type", None),
            size=getattr(audio, "file_size", None),
            caption=message.caption,
        )
    elif mode == "text":
        text = (message.text or "").strip()
        if not text:
            await message.answer(get_text("courts.error.evidence.text", lang_code))
            return
        if _contains_prohibited_content(text):
            await message.answer(get_text("courts.error.evidence.blocked", lang_code))
            return
        item = _evidence_item(
            kind="text",
            uploaded_by=message.from_user.id,
            uploaded_role=role,
            text=text,
        )
    elif mode == "link":
        text = (message.text or "").strip()
        if not text or not re.match(r"^https?://", text):
            await message.answer(get_text("courts.error.evidence.link", lang_code))
            return
        item = _evidence_item(
            kind="link",
            uploaded_by=message.from_user.id,
            uploaded_role=role,
            url=text,
        )
    else:
        if message.document:
            doc = message.document
            item = _evidence_item(
                kind="document",
                uploaded_by=message.from_user.id,
                uploaded_role=role,
                file_id=doc.file_id,
                file_name=doc.file_name,
                mime_type=doc.mime_type,
                size=doc.file_size,
                caption=message.caption,
            )
        else:
            await message.answer(get_text("courts.error.evidence.expected", lang_code))
            return
    if item is None:
        await message.answer(get_text("courts.error.evidence.expected", lang_code))
        return
    if item.get("text") and _contains_prohibited_content(str(item.get("text"))):
        await message.answer(get_text("courts.error.evidence.blocked", lang_code))
        return
    if case_id:
        await db.court_cases.append_evidence(case_id=int(case_id), evidence_item=item)
        await message.answer(
            get_text("courts.evidence.added", lang_code),
            reply_markup=_build_evidence_keyboard(lang_code, include_skip=True),
        )
        return
    evidence.append(item)
    await state.update_data(evidence=evidence)
    await message.answer(
        get_text("courts.evidence.added", lang_code),
        reply_markup=_build_evidence_keyboard(lang_code, include_skip=True),
    )


@router.callback_query(CourtClaimFlow.waiting_for_confirm, F.data.startswith("courts:confirm:"))
async def handle_confirmation_action(
    callback: CallbackQuery,
    state: FSMContext,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    action = (callback.data or "").split(":", 2)[-1]
    if action == "cancel":
        await state.clear()
        await callback.message.answer(get_text("courts.confirm.cancelled", lang_code))
        return
    if action == "edit":
        await state.clear()
        await state.set_state(CourtClaimFlow.choosing_category)
        await callback.message.answer(
            get_text("courts.step.category", lang_code),
            reply_markup=_build_category_keyboard(lang_code),
        )
        return
    data = await state.get_data()
    claim = str(data.get("claim_text") or "")
    claim_full = str(data.get("claim_text_full") or claim)
    category = str(data.get("category") or "")
    verdict, message_key = _sharia_check(claim, category)
    if verdict == "block":
        await callback.message.answer(get_text(message_key or "courts.sharia.blocked", lang_code))
        return
    if verdict == "clarify":
        await state.set_state(CourtClaimFlow.waiting_for_claim)
        await callback.message.answer(get_text(message_key or "courts.sharia.clarify", lang_code))
        return
    amount = data.get("amount")
    if isinstance(amount, str):
        amount = _parse_amount(amount)
    evidence = data.get("evidence") or []
    invite_code = None
    for _ in range(5):
        candidate = _generate_invite_code()
        if not await db.court_cases.get_case_by_invite_code(invite_code=candidate):
            invite_code = candidate
            break
    case = await db.court_cases.create_case(
        user_id=callback.from_user.id,
        plaintiff_id=callback.from_user.id,
        invite_code=invite_code,
        category=category,
        plaintiff=str(data.get("plaintiff_name") or "-"),
        defendant=str(data.get("defendant_name") or "-"),
        claim=claim_full,
        amount=amount if isinstance(amount, Decimal) or amount is None else None,
        evidence=evidence,
        status="open",
        sent_to_scholar=False,
    )
    await create_work_item(
        db,
        topic="courts",
        kind="case_created",
        target_user_id=callback.from_user.id,
        created_by_user_id=callback.from_user.id,
        payload={
            "case_id": case.get("id"),
            "case_number": case.get("case_number"),
            "category": category,
            "status": "open",
            "plaintiff": data.get("plaintiff_name"),
            "defendant": data.get("defendant_name"),
        },
    )
    sent = await _forward_case_to_scholars(
        bot=callback.bot,
        lang_code=lang_code,
        case=case,
        user=callback.from_user,
    )
    if sent:
        await db.court_cases.mark_sent_to_scholar(case_id=int(case.get("id") or 0), sent=True)
    await state.clear()
    await callback.message.answer(
        get_text(
            "courts.case.created",
            lang_code,
            case_number=case.get("case_number") or case.get("id"),
        ),
        reply_markup=build_inline_keyboard(INLINE_MENU_BY_KEY["menu.courts"], lang_code),
    )
    invite_code = case.get("invite_code")
    if invite_code:
        username = await _resolve_bot_username(callback.bot)
        if username:
            invite_link = f"https://t.me/{username}?start={invite_code}"
            await callback.message.answer(
                get_text(
                    "courts.invite.code",
                    lang_code,
                    invite_link=invite_link,
                )
            )
        else:
            await callback.message.answer(
                get_text(
                    "courts.invite.code.only",
                    lang_code,
                    invite_code=invite_code,
                )
            )


@router.callback_query(F.data == "courts:opened")
async def handle_opened_cases(
    callback: CallbackQuery,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    cases = await db.court_cases.list_cases_by_status(
        user_id=callback.from_user.id, statuses=["open"]
    )
    await _show_cases(
        callback.message,
        cases=cases,
        lang_code=lang_code,
        empty_key="courts.cases.empty.opened",
        user_id=callback.from_user.id,
    )


@router.callback_query(F.data == "courts:in_progress")
async def handle_in_progress_cases(
    callback: CallbackQuery,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    cases = await db.court_cases.list_cases_by_status(
        user_id=callback.from_user.id, statuses=["in_progress"]
    )
    await _show_cases(
        callback.message,
        cases=cases,
        lang_code=lang_code,
        empty_key="courts.cases.empty.in_progress",
        user_id=callback.from_user.id,
    )


@router.callback_query(F.data == "courts:closed")
async def handle_closed_cases(
    callback: CallbackQuery,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    cases = await db.court_cases.list_cases_by_status(
        user_id=callback.from_user.id, statuses=["closed", "cancelled"]
    )
    await _show_cases(
        callback.message,
        cases=cases,
        lang_code=lang_code,
        empty_key="courts.cases.empty.closed",
        user_id=callback.from_user.id,
    )

@router.callback_query(F.data.regexp(r"^courts:case:\d+$"))
async def handle_case_details(
    callback: CallbackQuery,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    payload = (callback.data or "").split(":", 2)[-1]
    try:
        case_id = int(payload)
    except ValueError:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    item = await db.court_cases.get_case_by_id(case_id=case_id, user_id=callback.from_user.id)
    if not item:
        await callback.message.answer(get_text("courts.case.not_found", lang_code))
        return
    role = _case_role(item, callback.from_user.id)
    is_plaintiff = role == "plaintiff"
    is_closed = str(item.get("status") or "").lower() in _CLOSED_STATUSES
    inline_rows: list[list[InlineKeyboardButton]] = []
    if not is_closed:
        inline_rows.append(
            [
                InlineKeyboardButton(
                    text=get_text("button.courts.details.add_evidence", lang_code),
                    callback_data=f"courts:case:{case_id}:add_evidence",
                )
            ]
        )
    inline_rows.append(
        [
            InlineKeyboardButton(
                text=get_text("button.courts.details.view_evidence", lang_code),
                callback_data=f"courts:case:{case_id}:view_evidence",
            )
        ]
    )
    if is_plaintiff and not is_closed:
        inline_rows.extend(
            [
                [
                    InlineKeyboardButton(
                        text=get_text("button.courts.details.edit_claim", lang_code),
                        callback_data=f"courts:case:{case_id}:edit_claim",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=get_text("button.courts.details.edit_category", lang_code),
                        callback_data=f"courts:case:{case_id}:edit_category",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=get_text("button.courts.details.cancel_case", lang_code),
                        callback_data=f"courts:case:{case_id}:cancel",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=get_text("button.courts.details.send_scholar", lang_code),
                        callback_data=f"courts:case:{case_id}:send_scholar",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=get_text("button.courts.details.invite", lang_code),
                        callback_data=f"courts:case:{case_id}:invite",
                    )
                ],
            ]
        )
    inline_rows.append(
        [
            InlineKeyboardButton(
                text=get_text("button.courts.details.mediate", lang_code),
                callback_data=f"courts:case:{case_id}:mediate",
            )
        ]
    )
    inline_rows.append(
        [
            InlineKeyboardButton(
                text=get_text("button.back", lang_code),
                callback_data="menu:menu.courts",
            )
        ]
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_rows)
    await callback.message.answer(_build_case_details(item, lang_code), reply_markup=keyboard)


@router.callback_query(F.data.startswith("courts:case:"))
async def handle_case_action(
    callback: CallbackQuery,
    state: FSMContext,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    parts = (callback.data or "").split(":")
    if len(parts) < 4:
        return
    await callback.answer()
    case_id = int(parts[2])
    action = parts[3]
    item = await db.court_cases.get_case_by_id(case_id=case_id, user_id=callback.from_user.id)
    if not item:
        await callback.message.answer(get_text("courts.case.not_found", lang_code))
        return
    role = _case_role(item, callback.from_user.id)
    is_plaintiff = role == "plaintiff"
    is_closed = str(item.get("status") or "").lower() in _CLOSED_STATUSES
    if is_closed and action not in {"mediate", "mediate_join", "mediate_stop"}:
        await callback.message.answer(get_text("courts.error.closed", lang_code))
        return
    if action == "add_evidence":
        await state.clear()
        await state.set_state(CourtCaseEditFlow.waiting_for_evidence)
        await state.update_data(edit_case_id=case_id, evidence_mode=None)
        await callback.message.answer(
            get_text("courts.step.evidence", lang_code),
            reply_markup=_build_evidence_keyboard(lang_code, include_skip=True),
        )
        return
    if action == "view_evidence":
        evidence = item.get("evidence") or []
        if isinstance(evidence, str):
            try:
                evidence = json.loads(evidence)
            except json.JSONDecodeError:
                evidence = []
        await _send_case_evidence(
            bot=callback.bot,
            message=callback.message,
            lang_code=lang_code,
            evidence=evidence,
        )
        return
    if action == "edit_claim":
        if not is_plaintiff:
            await callback.message.answer(get_text("courts.error.permission", lang_code))
            return
        await state.clear()
        await state.set_state(CourtCaseEditFlow.waiting_for_claim)
        await state.update_data(edit_case_id=case_id)
        await callback.message.answer(get_text("courts.edit.claim.prompt", lang_code))
        return
    if action == "edit_category":
        if not is_plaintiff:
            await callback.message.answer(get_text("courts.error.permission", lang_code))
            return
        await state.clear()
        await state.set_state(CourtCaseEditFlow.waiting_for_category)
        await state.update_data(edit_case_id=case_id)
        await callback.message.answer(
            get_text("courts.step.category", lang_code),
            reply_markup=_build_category_keyboard(lang_code),
        )
        return
    if action == "cancel":
        if not is_plaintiff:
            await callback.message.answer(get_text("courts.error.permission", lang_code))
            return
        confirm_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=get_text("button.courts.details.cancel_confirm", lang_code),
                        callback_data=f"courts:case:{case_id}:cancel_confirm",
                    ),
                    InlineKeyboardButton(
                        text=get_text("button.courts.details.cancel_abort", lang_code),
                        callback_data=f"courts:case:{case_id}:cancel_abort",
                    ),
                ]
            ]
        )
        await callback.message.answer(
            get_text("courts.case.cancel.confirm", lang_code),
            reply_markup=confirm_keyboard,
        )
        return
    if action == "cancel_confirm":
        if not is_plaintiff:
            await callback.message.answer(get_text("courts.error.permission", lang_code))
            return
        await db.court_cases.update_status(case_id=case_id, status="cancelled")
        await callback.message.answer(get_text("courts.case.cancelled", lang_code))
        return
    if action == "cancel_abort":
        await callback.message.answer(get_text("courts.case.cancel.aborted", lang_code))
        return
    if action == "send_scholar":
        if not is_plaintiff:
            await callback.message.answer(get_text("courts.error.permission", lang_code))
            return
        if item.get("sent_to_scholar"):
            await callback.message.answer(get_text("courts.case.already_sent", lang_code))
            return
        claim = str(item.get("claim") or "")
        verdict, message_key = _sharia_check(claim, str(item.get("category") or ""))
        if verdict == "block":
            await callback.message.answer(get_text(message_key or "courts.sharia.blocked", lang_code))
            return
        if verdict == "clarify":
            await callback.message.answer(get_text(message_key or "courts.sharia.clarify", lang_code))
            return
        sent = await _forward_case_to_scholars(
            bot=callback.bot,
            lang_code=lang_code,
            case=item,
            user=callback.from_user,
        )
        if sent:
            await db.court_cases.mark_sent_to_scholar(case_id=case_id, sent=True)
            await callback.message.answer(get_text("courts.case.sent_to_scholar", lang_code))
        else:
            await callback.message.answer(get_text("courts.file.unavailable", lang_code))
        return
    if action == "invite":
        if not is_plaintiff:
            await callback.message.answer(get_text("courts.error.permission", lang_code))
            return
        if item.get("defendant_id"):
            await callback.message.answer(get_text("courts.invite.already_connected", lang_code))
            return
        invite_code = item.get("invite_code")
        if not invite_code:
            await callback.message.answer(get_text("courts.invite.missing", lang_code))
            return
        username = await _resolve_bot_username(callback.bot)
        if username:
            invite_link = f"https://t.me/{username}?start={invite_code}"
            text = get_text(
                "courts.invite.code",
                lang_code,
                invite_link=invite_link,
            )
            share_text = get_text(
                "courts.invite.share.text",
                lang_code,
                invite_link=invite_link,
            )
            share_url = (
                "https://t.me/share/url?url="
                + quote_plus(invite_link)
                + "&text="
                + quote_plus(share_text)
            )
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=get_text("button.courts.details.invite_share", lang_code),
                            url=share_url,
                        )
                    ]
                ]
            )
            await callback.message.answer(text, reply_markup=keyboard)
        else:
            text = get_text(
                "courts.invite.code.only",
                lang_code,
                invite_code=invite_code,
            )
            await callback.message.answer(text)
        return
    if action in {"mediate", "mediate_join"}:
        await state.set_state(CourtCaseMediateFlow.active)
        await state.update_data(mediate_case_id=case_id)
        if action == "mediate":
            await callback.message.answer(
                get_text("courts.case.mediate.start", lang_code),
                reply_markup=_build_mediate_keyboard(lang_code, case_id=case_id, mode="stop"),
            )
            await _notify_mediate_start(
                bot=callback.bot,
                case=item,
                initiator=callback.from_user,
                lang_code=lang_code,
            )
            history = _normalize_mediate_log(item.get("mediate_log"))
            await _send_mediate_history(
                bot=callback.bot,
                chat_id=callback.from_user.id,
                log=history,
                lang_code=lang_code,
            )
        else:
            case_number = item.get("case_number") or case_id
            await callback.message.answer(
                get_text("courts.case.mediate.joined", lang_code, case_number=case_number),
                reply_markup=_build_mediate_keyboard(lang_code, case_id=case_id, mode="stop"),
            )
            history = _normalize_mediate_log(item.get("mediate_log"))
            await _send_mediate_history(
                bot=callback.bot,
                chat_id=callback.from_user.id,
                log=history,
                lang_code=lang_code,
            )
        return
    if action == "mediate_stop":
        await _finalize_mediate_chat(
            bot=callback.bot,
            db=db,
            case_id=case_id,
            lang_code=lang_code,
            notify_chat_id=callback.from_user.id,
        )
        await safe_state_clear(state)
        await callback.message.answer(get_text("courts.case.mediate.stopped", lang_code))
        return


@router.message(CourtCaseMediateFlow.active)
async def handle_mediate_message(
    message: Message,
    state: FSMContext,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        data = await state.get_data()
        case_id = int(data.get("mediate_case_id") or 0)
        if case_id:
            await _finalize_mediate_chat(
                bot=message.bot,
                db=db,
                case_id=case_id,
                lang_code=lang_code,
                notify_chat_id=message.chat.id,
            )
        await safe_state_clear(state)
        await message.answer(get_text("courts.case.mediate.stopped", lang_code))
        return
    data = await state.get_data()
    case_id = int(data.get("mediate_case_id") or 0)
    if not case_id:
        await safe_state_clear(state)
        await message.answer(get_text("courts.case.not_found", lang_code))
        return
    item = await db.court_cases.get_case_by_id(case_id=case_id, user_id=message.from_user.id)
    if not item:
        await safe_state_clear(state)
        await message.answer(get_text("courts.case.not_found", lang_code))
        return
    recipients = _case_participants(item)
    scholar_id = _resolve_scholar_observer(item)
    if scholar_id:
        recipients.add(scholar_id)
    recipients.discard(int(message.from_user.id))
    if not recipients:
        await message.answer(get_text("courts.case.mediate.no_recipients", lang_code))
        return

    sender_name = (
        message.from_user.full_name
        or message.from_user.username
        or get_text("user.default_name", lang_code)
    )
    text = (message.text or "").strip()
    if text:
        payload = get_text("courts.case.mediate.forward", lang_code, name=sender_name, text=text)
        for recipient_id in recipients:
            try:
                await message.bot.send_message(chat_id=int(recipient_id), text=payload)
            except Exception:
                logger.exception("Failed to forward mediate text to %s", recipient_id)
        await db.court_cases.append_mediate_log(
            case_id=case_id,
            entry={
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "name": sender_name,
                "text": text,
                "kind": "text",
            },
        )
        return

    caption = (message.caption or "").strip()
    has_media = any(
        [
            message.photo,
            message.document,
            message.audio,
            message.voice,
            message.video,
            message.video_note,
            message.animation,
            message.sticker,
        ]
    )
    if not has_media:
        await message.answer(get_text("courts.case.mediate.unsupported", lang_code))
        return
    header = get_text(
        "courts.case.mediate.forward.media",
        lang_code,
        name=sender_name,
        caption=caption,
    )
    for recipient_id in recipients:
        try:
            if header:
                await message.bot.send_message(chat_id=int(recipient_id), text=header)
            await message.copy_to(chat_id=int(recipient_id))
        except Exception:
            logger.exception("Failed to forward mediate media to %s", recipient_id)
    await db.court_cases.append_mediate_log(
        case_id=case_id,
        entry={
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "name": sender_name,
            "text": caption,
            "kind": "media",
        },
    )


@router.message(CourtCaseEditFlow.waiting_for_claim)
async def handle_edit_claim(
    message: Message,
    state: FSMContext,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    text = (message.text or "").strip()
    if not text:
        await message.answer(get_text("courts.error.claim.empty", lang_code))
        return
    data = await state.get_data()
    case_id = int(data.get("edit_case_id") or 0)
    await db.court_cases.update_claim(case_id=case_id, claim=text)
    await state.clear()
    await message.answer(get_text("courts.edit.claim.saved", lang_code))


@router.callback_query(CourtCaseEditFlow.waiting_for_category, F.data.startswith("courts:category:"))
async def handle_edit_category(
    callback: CallbackQuery,
    state: FSMContext,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    slug = (callback.data or "").split(":", 2)[-1].strip()
    if slug not in CATEGORY_KEYS:
        await callback.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        return
    data = await state.get_data()
    case_id = int(data.get("edit_case_id") or 0)
    await db.court_cases.update_category(case_id=case_id, category=slug)
    await state.clear()
    await callback.message.answer(get_text("courts.edit.category.saved", lang_code))
