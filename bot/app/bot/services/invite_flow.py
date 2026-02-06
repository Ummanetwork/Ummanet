from __future__ import annotations

import re
import uuid
from typing import Any

from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup

from app.services.i18n.localization import get_text


def normalize_invite_payload(payload: str | None) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", payload or "").upper()


def _build_contract_party_keyboard(contract_id: int, lang_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("contracts.flow.party.sign", lang_code),
                    callback_data=f"contract_party_sign:{contract_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("contracts.flow.party.changes", lang_code),
                    callback_data=f"contract_party_changes:{contract_id}",
                )
            ],
        ]
    )


async def _ensure_contract_document(
    *,
    db: Any,
    user_id: int,
    contract_id: int,
    title: str,
    rendered_text: str,
) -> None:
    if not user_id or not contract_id or not rendered_text:
        return
    try:
        existing = await db.documents.get_user_document_by_contract_id(
            user_id=user_id,
            contract_id=contract_id,
        )
    except Exception:
        existing = None
    if existing:
        return
    try:
        from app.bot.handlers.comitee_contracts import _build_contract_pdf
        pdf_bytes = _build_contract_pdf(rendered_text, title)
    except Exception:
        return
    filename = f"{uuid.uuid4()}.pdf"
    try:
        await db.documents.add_document(
            filename=filename,
            user_id=user_id,
            category="Contract",
            name=title,
            content=pdf_bytes,
            doc_type="Contract",
            contract_id=contract_id,
        )
    except Exception:
        return


async def try_attach_invite_contract(
    *,
    bot: Any,
    db: Any,
    user_id: int,
    invite_code: str,
    lang_code: str,
) -> bool:
    contract = await db.contracts.get_contract_by_invite_code(invite_code=invite_code)
    if contract is None:
        return False
    if int(contract.get("user_id") or 0) == user_id:
        await bot.send_message(chat_id=user_id, text=get_text("contracts.invite.self", lang_code))
        return True

    data = contract.get("data") or {}
    existing_recipient = data.get("recipient_id")
    if existing_recipient and int(existing_recipient) != int(user_id):
        await bot.send_message(chat_id=user_id, text=get_text("contracts.invite.used", lang_code))
        return True

    data["recipient_id"] = int(user_id)
    data["recipient"] = str(user_id)
    data["invite_pending"] = False
    data.setdefault("party_status", "pending")

    rendered_text = str(contract.get("rendered_text") or "")
    contract_title = (
        data.get("contract_title")
        or contract.get("template_topic")
        or contract.get("type")
        or get_text("contracts.title.unknown", lang_code)
    )
    try:
        await db.contracts.update_contract(
            contract_id=int(contract.get("id") or 0),
            status="sent_to_party",
            rendered_text=rendered_text,
            data=data,
        )
    except Exception:
        pass

    await _ensure_contract_document(
        db=db,
        user_id=user_id,
        contract_id=int(contract.get("id") or 0),
        title=str(contract_title),
        rendered_text=rendered_text,
    )

    await bot.send_message(
        chat_id=user_id,
        text=get_text("contracts.invite.joined", lang_code, title=str(contract_title)),
    )

    if rendered_text:
        if len(rendered_text) <= 3500:
            await bot.send_message(
                chat_id=user_id,
                text=rendered_text,
                reply_markup=_build_contract_party_keyboard(int(contract.get("id") or 0), lang_code),
            )
        else:
            await bot.send_message(
                chat_id=user_id,
                text=get_text("contracts.flow.preview.too_long", lang_code),
                reply_markup=_build_contract_party_keyboard(int(contract.get("id") or 0), lang_code),
            )
            buffer = BufferedInputFile(rendered_text.encode("utf-8"), filename="contract.txt")
            await bot.send_document(
                chat_id=user_id,
                document=buffer,
                caption=str(contract_title),
            )

    owner_id = contract.get("user_id")
    if owner_id:
        try:
            await bot.send_message(
                chat_id=int(owner_id),
                text=get_text("contracts.invite.owner_notice", lang_code, title=str(contract_title)),
            )
        except Exception:
            pass
    return True


async def try_attach_invite_case(
    *,
    bot: Any,
    db: Any,
    user_id: int,
    invite_code: str,
    lang_code: str,
) -> bool:
    case = await db.court_cases.get_case_by_invite_code(invite_code=invite_code)
    if case is None:
        return False
    if case.get("plaintiff_id") == user_id or case.get("user_id") == user_id:
        await bot.send_message(chat_id=user_id, text=get_text("courts.invite.self", lang_code))
        return True
    if case.get("defendant_id") is not None:
        await bot.send_message(chat_id=user_id, text=get_text("courts.invite.used", lang_code))
        return True
    updated = await db.court_cases.attach_defendant(case_id=int(case.get("id") or 0), defendant_id=user_id)
    if updated:
        await bot.send_message(
            chat_id=user_id,
            text=get_text(
                "courts.invite.joined",
                lang_code,
                case_number=updated.get("case_number") or updated.get("id"),
            ),
        )
        plaintiff_id = updated.get("plaintiff_id") or updated.get("user_id")
        if plaintiff_id:
            try:
                await bot.send_message(
                    chat_id=int(plaintiff_id),
                    text=get_text(
                        "courts.invite.plaintiff_notice",
                        lang_code,
                        case_number=updated.get("case_number") or updated.get("id"),
                    ),
                )
            except Exception:
                pass
        return True
    await bot.send_message(chat_id=user_id, text=get_text("courts.invite.used", lang_code))
    return True


async def try_attach_invite(
    *,
    bot: Any,
    db: Any,
    user_id: int,
    invite_code: str,
    lang_code: str,
) -> None:
    handled = await try_attach_invite_contract(
        bot=bot,
        db=db,
        user_id=user_id,
        invite_code=invite_code,
        lang_code=lang_code,
    )
    if handled:
        return
    handled = await try_attach_invite_case(
        bot=bot,
        db=db,
        user_id=user_id,
        invite_code=invite_code,
        lang_code=lang_code,
    )
    if handled:
        return
    await bot.send_message(chat_id=user_id, text=get_text("courts.invite.invalid", lang_code))
