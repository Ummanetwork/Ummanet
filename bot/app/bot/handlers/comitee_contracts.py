
from __future__ import annotations

import io
import logging
import math
import os
import re
import uuid
from secrets import choice as secrets_choice
from datetime import datetime, timezone
from xml.sax.saxutils import escape
from typing import Optional

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    KeyboardButtonRequestUser,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.bot.states.comitee import (
    ContractAgreementFlow,
    ContractAutoPickFlow,
    ContractCreation,
    ContractSearch,
    ContractTemplateFlow,
    CourtClaimFlow,
)
from app.infrastructure.database.db import DB
from app.infrastructure.database.models.user import UserModel
from app.services.i18n.localization import get_text, resolve_language
from app.services.work_items.service import create_work_item
from config.config import settings

from .comitee_common import (
    edit_or_send_callback,
    get_backend_client,
    is_cancel_command,
    send_documents,
    user_language,
)
from .comitee_menu import INLINE_MENU_BY_KEY, InlineButton, InlineMenu, build_inline_keyboard

logger = logging.getLogger(__name__)

router = Router(name="comitee.contracts")

_PDF_FONTS_READY = False
_PDF_FONT_REGULAR: str | None = None
_PDF_FONT_BOLD: str | None = None
_PDF_FONT_ITALIC: str | None = None
_PDF_FONT_SYMBOL: str | None = None

_STATUS_KEY_BY_VALUE: dict[str, str] = {
    "draft": "contracts.status.draft",
    "confirmed": "contracts.status.confirmed",
    "sent_to_party": "contracts.status.sent_to_party",
    "party_approved": "contracts.status.party_approved",
    "party_changes_requested": "contracts.status.party_changes_requested",
    "signed": "contracts.status.signed",
    "sent_to_scholar": "contracts.status.sent_to_scholar",
    "scholar_send_failed": "contracts.status.scholar_send_failed",
    "sent": "contracts.status.sent",
}

_EDITABLE_CONTRACT_STATUSES: set[str] = {
    "draft",
    "confirmed",
    "party_changes_requested",
    "scholar_send_failed",
}
_INVITE_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_INVITE_CODE_LENGTH = 6


def _format_contract_status(status: str | None, lang_code: str) -> str:
    if not status:
        return get_text("contracts.status.draft", lang_code)
    key = _STATUS_KEY_BY_VALUE.get(status)
    return get_text(key, lang_code) if key else status


def _format_contract_date(value: object) -> str:
    if value is None:
        return "-"
    if hasattr(value, "date"):
        try:
            return value.date().isoformat()
        except Exception:
            return "-"
    if isinstance(value, str):
        if len(value) >= 10:
            return value[:10]
        return value
    return "-"


def _is_contract_fully_signed(contract: dict[str, object] | None) -> bool:
    if not contract:
        return False
    status = str(contract.get("status") or "")
    if status != "signed":
        return False
    data = contract.get("data") or {}
    return str(data.get("party_status") or "") == "signed"


def _is_contract_counterparty_signed(contract: dict[str, object] | None) -> bool:
    if not contract:
        return False
    data = contract.get("data") or {}
    return str(data.get("party_status") or "") == "signed"


def _extract_contract_defendant_name(data: dict[str, object]) -> str | None:
    candidate_keys = (
        "recipient_name",
        "recipient",
        "borrower_name",
        "buyer_name",
        "seller_name",
        "donor_name",
        "partner2_name",
        "party_two_name",
        "lessee_name",
        "lessor_name",
        "tenant_name",
    )
    for key in candidate_keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_contract_recipient_id(data: dict[str, object]) -> int | None:
    raw = data.get("recipient_id")
    if raw is None:
        raw = data.get("recipient")
    if raw is None:
        return None
    try:
        return int(str(raw).strip())
    except Exception:
        return None


def _build_contract_edit_keyboard(
    contract_id: int,
    lang_code: str,
    *,
    can_edit: bool,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if can_edit:
        rows.append(
            [
                InlineKeyboardButton(
                    text=get_text("contracts.flow.button.edit", lang_code),
                    callback_data=f"contract_list_edit:{contract_id}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _build_contract_recipient_keyboard(lang_code: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text=get_text("contracts.flow.button.pick_contact", lang_code),
                    request_user=KeyboardButtonRequestUser(request_id=1),
                )
            ],
            [KeyboardButton(text=get_text("button.cancel", lang_code))],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

PRIMARY_COLOR = colors.HexColor("#0b4f4f")
ACCENT_COLOR = colors.HexColor("#c9a227")
_SYMBOL_GLYPH = "ﷺ"


def _first_existing_path(paths: list[str]) -> Optional[str]:
    for path in paths:
        if os.path.exists(path):
            return path
    return None


def _generate_invite_code() -> str:
    alphabet = _INVITE_CODE_ALPHABET
    return "".join(secrets_choice(alphabet) for _ in range(_INVITE_CODE_LENGTH))


async def _resolve_bot_username(bot: types.Bot) -> str | None:
    username = getattr(bot, "username", None)
    if username:
        return username
    try:
        me = await bot.get_me()
        return getattr(me, "username", None)
    except Exception:
        return None


def _ensure_pdf_fonts() -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    global _PDF_FONTS_READY, _PDF_FONT_REGULAR, _PDF_FONT_BOLD, _PDF_FONT_ITALIC, _PDF_FONT_SYMBOL
    if _PDF_FONTS_READY:
        return _PDF_FONT_REGULAR, _PDF_FONT_BOLD, _PDF_FONT_ITALIC, _PDF_FONT_SYMBOL

    regular_path = _first_existing_path(
        [
            os.getenv("CONTRACT_PDF_FONT_PATH") or "",
            r"C:\Windows\Fonts\times.ttf",
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\calibri.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
        ]
    )
    bold_path = _first_existing_path(
        [
            os.getenv("CONTRACT_PDF_FONT_BOLD_PATH") or "",
            r"C:\Windows\Fonts\timesbd.ttf",
            r"C:\Windows\Fonts\arialbd.ttf",
            r"C:\Windows\Fonts\calibrib.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
        ]
    )
    italic_path = _first_existing_path(
        [
            os.getenv("CONTRACT_PDF_FONT_ITALIC_PATH") or "",
            r"C:\Windows\Fonts\timesi.ttf",
            r"C:\Windows\Fonts\ariali.ttf",
            r"C:\Windows\Fonts\calibrii.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf",
        ]
    )
    symbol_path = _first_existing_path(
        [
            os.getenv("CONTRACT_PDF_FONT_SYMBOL_PATH") or "",
            r"C:\Windows\Fonts\seguisym.ttf",
        ]
    )
    if regular_path:
        try:
            pdfmetrics.registerFont(TTFont("ContractRegular", regular_path))
            _PDF_FONT_REGULAR = "ContractRegular"
        except Exception:
            logger.exception("Failed to register regular PDF font")
    if bold_path:
        try:
            pdfmetrics.registerFont(TTFont("ContractBold", bold_path))
            _PDF_FONT_BOLD = "ContractBold"
        except Exception:
            logger.exception("Failed to register bold PDF font")
    if italic_path:
        try:
            pdfmetrics.registerFont(TTFont("ContractItalic", italic_path))
            _PDF_FONT_ITALIC = "ContractItalic"
        except Exception:
            logger.exception("Failed to register italic PDF font")
    if symbol_path:
        try:
            pdfmetrics.registerFont(TTFont("ContractSymbol", symbol_path))
            _PDF_FONT_SYMBOL = "ContractSymbol"
        except Exception:
            logger.exception("Failed to register symbol PDF font")

    _PDF_FONTS_READY = True
    return _PDF_FONT_REGULAR, _PDF_FONT_BOLD, _PDF_FONT_ITALIC, _PDF_FONT_SYMBOL


CONTRACT_FLOW_DEFINITIONS: dict[str, dict[str, object]] = {
    "qard": {
        "title_key": "contracts.flow.type.qard",
        "topic": "contracts.finance.qard",
        "fields": [
            {"key": "lender_name", "prompt_key": "contracts.flow.qard.lender_name"},
            {
                "key": "lender_document",
                "prompt_key": "contracts.flow.qard.lender_document",
                "optional": True,
            },
            {
                "key": "lender_address",
                "prompt_key": "contracts.flow.qard.lender_address",
                "optional": True,
            },
            {
                "key": "lender_contact",
                "prompt_key": "contracts.flow.qard.lender_contact",
                "optional": True,
            },
            {"key": "borrower_name", "prompt_key": "contracts.flow.qard.borrower_name"},
            {
                "key": "borrower_document",
                "prompt_key": "contracts.flow.qard.borrower_document",
                "optional": True,
            },
            {
                "key": "borrower_address",
                "prompt_key": "contracts.flow.qard.borrower_address",
                "optional": True,
            },
            {
                "key": "borrower_contact",
                "prompt_key": "contracts.flow.qard.borrower_contact",
                "optional": True,
            },
            {"key": "amount", "prompt_key": "contracts.flow.qard.amount"},
            {
                "key": "purpose",
                "prompt_key": "contracts.flow.qard.purpose",
                "optional": True,
            },
            {"key": "due_date", "prompt_key": "contracts.flow.qard.due_date"},
            {
                "key": "repayment_method",
                "prompt_key": "contracts.flow.qard.repayment_method",
                "optional": True,
            },
            {
                "key": "collateral_required",
                "prompt_key": "contracts.flow.qard.collateral_required",
                "choices": [
                    {"value": "yes", "label_key": "contracts.flow.choice.yes"},
                    {"value": "no", "label_key": "contracts.flow.choice.no"},
                ],
            },
            {
                "key": "collateral_description",
                "prompt_key": "contracts.flow.qard.collateral_description",
                "depends_on": {"key": "collateral_required", "value": "yes"},
            },
            {
                "key": "extra_terms",
                "prompt_key": "contracts.flow.qard.extra_terms",
                "optional": True,
            },
        ],
    },
    "ijara": {
        "title_key": "contracts.flow.type.ijara",
        "topic": "contracts.exchange.ijara",
        "fields": [
            {"key": "landlord_name", "prompt_key": "contracts.flow.ijara.landlord"},
            {
                "key": "landlord_document",
                "prompt_key": "contracts.flow.ijara.landlord_document",
                "optional": True,
            },
            {
                "key": "landlord_address",
                "prompt_key": "contracts.flow.ijara.landlord_address",
                "optional": True,
            },
            {
                "key": "landlord_contact",
                "prompt_key": "contracts.flow.ijara.landlord_contact",
                "optional": True,
            },
            {"key": "tenant_name", "prompt_key": "contracts.flow.ijara.tenant"},
            {
                "key": "tenant_document",
                "prompt_key": "contracts.flow.ijara.tenant_document",
                "optional": True,
            },
            {
                "key": "tenant_address",
                "prompt_key": "contracts.flow.ijara.tenant_address",
                "optional": True,
            },
            {
                "key": "tenant_contact",
                "prompt_key": "contracts.flow.ijara.tenant_contact",
                "optional": True,
            },
            {"key": "lease_object", "prompt_key": "contracts.flow.ijara.object"},
            {
                "key": "lease_object_details",
                "prompt_key": "contracts.flow.ijara.object_details",
                "optional": True,
            },
            {
                "key": "lease_object_condition",
                "prompt_key": "contracts.flow.ijara.object_condition",
                "optional": True,
            },
            {"key": "lease_term", "prompt_key": "contracts.flow.ijara.term"},
            {"key": "lease_price", "prompt_key": "contracts.flow.ijara.price"},
            {
                "key": "lease_currency",
                "prompt_key": "contracts.flow.ijara.currency",
                "optional": True,
            },
            {
                "key": "payment_order",
                "prompt_key": "contracts.flow.ijara.payment_order",
                "choices": [
                    {
                        "value": "monthly",
                        "label_key": "contracts.flow.choice.ijara.payment.monthly",
                    },
                    {
                        "value": "one_time",
                        "label_key": "contracts.flow.choice.ijara.payment.one_time",
                    },
                    {
                        "value": "other",
                        "label_key": "contracts.flow.choice.ijara.payment.other",
                    },
                ],
            },
            {
                "key": "damage_responsibility",
                "prompt_key": "contracts.flow.ijara.damage_responsibility",
                "choices": [
                    {
                        "value": "tenant_fault",
                        "label_key": "contracts.flow.choice.ijara.damage.tenant",
                    },
                    {
                        "value": "agreement",
                        "label_key": "contracts.flow.choice.ijara.damage.agreement",
                    },
                ],
            },
            {
                "key": "additional_terms",
                "prompt_key": "contracts.flow.ijara.additional_terms",
                "optional": True,
            },
        ],
    },
    "salam": {
        "title_key": "contracts.flow.type.salam",
        "topic": "contracts.exchange.salam",
        "fields": [
            {"key": "buyer_name", "prompt_key": "contracts.flow.salam.buyer"},
            {
                "key": "buyer_document",
                "prompt_key": "contracts.flow.salam.buyer_document",
                "optional": True,
            },
            {
                "key": "buyer_address",
                "prompt_key": "contracts.flow.salam.buyer_address",
                "optional": True,
            },
            {
                "key": "buyer_contact",
                "prompt_key": "contracts.flow.salam.buyer_contact",
                "optional": True,
            },
            {"key": "supplier_name", "prompt_key": "contracts.flow.salam.supplier"},
            {
                "key": "supplier_document",
                "prompt_key": "contracts.flow.salam.supplier_document",
                "optional": True,
            },
            {
                "key": "supplier_address",
                "prompt_key": "contracts.flow.salam.supplier_address",
                "optional": True,
            },
            {
                "key": "supplier_contact",
                "prompt_key": "contracts.flow.salam.supplier_contact",
                "optional": True,
            },
            {"key": "goods_name", "prompt_key": "contracts.flow.salam.goods_name"},
            {"key": "goods_quality", "prompt_key": "contracts.flow.salam.goods_quality"},
            {"key": "goods_quantity", "prompt_key": "contracts.flow.salam.goods_quantity"},
            {
                "key": "goods_packaging",
                "prompt_key": "contracts.flow.salam.goods_packaging",
                "optional": True,
            },
            {"key": "delivery_date", "prompt_key": "contracts.flow.salam.delivery_date"},
            {"key": "fixed_price", "prompt_key": "contracts.flow.salam.fixed_price"},
            {"key": "delivery_place", "prompt_key": "contracts.flow.salam.delivery_place"},
        ],
    },
    "istisna": {
        "title_key": "contracts.flow.type.istisna",
        "topic": "contracts.exchange.istisna",
        "fields": [
            {"key": "customer_name", "prompt_key": "contracts.flow.istisna.customer"},
            {
                "key": "customer_document",
                "prompt_key": "contracts.flow.istisna.customer_document",
                "optional": True,
            },
            {
                "key": "customer_address",
                "prompt_key": "contracts.flow.istisna.customer_address",
                "optional": True,
            },
            {
                "key": "customer_contact",
                "prompt_key": "contracts.flow.istisna.customer_contact",
                "optional": True,
            },
            {"key": "contractor_name", "prompt_key": "contracts.flow.istisna.contractor"},
            {
                "key": "contractor_document",
                "prompt_key": "contracts.flow.istisna.contractor_document",
                "optional": True,
            },
            {
                "key": "contractor_address",
                "prompt_key": "contracts.flow.istisna.contractor_address",
                "optional": True,
            },
            {
                "key": "contractor_contact",
                "prompt_key": "contracts.flow.istisna.contractor_contact",
                "optional": True,
            },
            {"key": "product_name", "prompt_key": "contracts.flow.istisna.product_name"},
            {"key": "product_materials", "prompt_key": "contracts.flow.istisna.product_materials"},
            {"key": "product_dimensions", "prompt_key": "contracts.flow.istisna.product_dimensions"},
            {"key": "product_quality", "prompt_key": "contracts.flow.istisna.product_quality"},
            {"key": "product_quantity", "prompt_key": "contracts.flow.istisna.product_quantity"},
            {"key": "deadline", "prompt_key": "contracts.flow.istisna.term"},
            {
                "key": "materials_owner",
                "prompt_key": "contracts.flow.istisna.materials",
                "choices": [
                    {
                        "value": "customer",
                        "label_key": "contracts.flow.choice.istisna.materials.customer",
                    },
                    {
                        "value": "contractor",
                        "label_key": "contracts.flow.choice.istisna.materials.contractor",
                    },
                ],
            },
            {"key": "price", "prompt_key": "contracts.flow.istisna.price"},
            {
                "key": "payment_schedule",
                "prompt_key": "contracts.flow.istisna.payment_schedule",
                "optional": True,
            },
            {
                "key": "start_date",
                "prompt_key": "contracts.flow.istisna.start_date",
                "optional": True,
            },
            {
                "key": "delivery_place",
                "prompt_key": "contracts.flow.istisna.delivery_place",
                "optional": True,
            },
        ],
    },
    "bay": {
        "title_key": "contracts.flow.type.bay",
        "topic": "contracts.exchange.bay",
        "fields": [
            {"key": "seller_name", "prompt_key": "contracts.flow.bay.seller"},
            {
                "key": "seller_document",
                "prompt_key": "contracts.flow.bay.seller_document",
                "optional": True,
            },
            {
                "key": "seller_address",
                "prompt_key": "contracts.flow.bay.seller_address",
                "optional": True,
            },
            {
                "key": "seller_contact",
                "prompt_key": "contracts.flow.bay.seller_contact",
                "optional": True,
            },
            {"key": "buyer_name", "prompt_key": "contracts.flow.bay.buyer"},
            {
                "key": "buyer_document",
                "prompt_key": "contracts.flow.bay.buyer_document",
                "optional": True,
            },
            {
                "key": "buyer_address",
                "prompt_key": "contracts.flow.bay.buyer_address",
                "optional": True,
            },
            {
                "key": "buyer_contact",
                "prompt_key": "contracts.flow.bay.buyer_contact",
                "optional": True,
            },
            {"key": "goods_description", "prompt_key": "contracts.flow.bay.goods"},
            {
                "key": "goods_details",
                "prompt_key": "contracts.flow.bay.goods_details",
                "optional": True,
            },
            {
                "key": "goods_condition",
                "prompt_key": "contracts.flow.bay.condition",
                "choices": [
                    {
                        "value": "new",
                        "label_key": "contracts.flow.choice.bay.condition.new",
                    },
                    {
                        "value": "used",
                        "label_key": "contracts.flow.choice.bay.condition.used",
                    },
                ],
            },
            {"key": "price", "prompt_key": "contracts.flow.bay.price"},
            {
                "key": "price_currency",
                "prompt_key": "contracts.flow.bay.currency",
                "optional": True,
            },
            {
                "key": "payment_timing",
                "prompt_key": "contracts.flow.bay.payment_timing",
                "choices": [
                    {
                        "value": "before",
                        "label_key": "contracts.flow.choice.bay.payment.before",
                    },
                    {
                        "value": "after",
                        "label_key": "contracts.flow.choice.bay.payment.after",
                    },
                    {
                        "value": "installments",
                        "label_key": "contracts.flow.choice.bay.payment.installments",
                    },
                    {
                        "value": "deferred",
                        "label_key": "contracts.flow.choice.bay.payment.deferred",
                    },
                ],
            },
            {
                "key": "delivery_term",
                "prompt_key": "contracts.flow.bay.delivery_term",
                "optional": True,
            },
            {
                "key": "khiyar_term",
                "prompt_key": "contracts.flow.bay.khiyar_term",
                "optional": True,
            },
        ],
    },
    "installment": {
        "title_key": "contracts.flow.type.installment",
        "topic": "contracts.exchange.installment",
        "fields": [
            {"key": "seller_name", "prompt_key": "contracts.flow.installment.seller"},
            {"key": "buyer_name", "prompt_key": "contracts.flow.installment.buyer"},
            {"key": "goods_description", "prompt_key": "contracts.flow.installment.goods"},
            {
                "key": "goods_details",
                "prompt_key": "contracts.flow.installment.goods_details",
                "optional": True,
            },
            {
                "key": "goods_condition",
                "prompt_key": "contracts.flow.installment.goods_condition",
                "choices": [
                    {"value": "new", "label_key": "contracts.flow.choice.bay.condition.new"},
                    {"value": "used", "label_key": "contracts.flow.choice.bay.condition.used"},
                ],
            },
            {"key": "total_price", "prompt_key": "contracts.flow.installment.total_price"},
            {
                "key": "price_currency",
                "prompt_key": "contracts.flow.installment.currency",
                "optional": True,
            },
            {
                "key": "down_payment",
                "prompt_key": "contracts.flow.installment.down_payment",
                "optional": True,
            },
            {"key": "installment_count", "prompt_key": "contracts.flow.installment.count"},
            {"key": "installment_amount", "prompt_key": "contracts.flow.installment.amount"},
            {
                "key": "installment_schedule",
                "prompt_key": "contracts.flow.installment.schedule",
                "optional": True,
            },
            {
                "key": "delivery_term",
                "prompt_key": "contracts.flow.installment.delivery_term",
                "optional": True,
            },
        ],
    },
    "murabaha": {
        "title_key": "contracts.flow.type.murabaha",
        "topic": "contracts.exchange.murabaha",
        "fields": [
            {"key": "seller_name", "prompt_key": "contracts.flow.murabaha.seller"},
            {"key": "buyer_name", "prompt_key": "contracts.flow.murabaha.buyer"},
            {"key": "goods_description", "prompt_key": "contracts.flow.murabaha.goods"},
            {"key": "cost_price", "prompt_key": "contracts.flow.murabaha.cost_price"},
            {"key": "markup", "prompt_key": "contracts.flow.murabaha.markup"},
            {"key": "final_price", "prompt_key": "contracts.flow.murabaha.final_price"},
            {
                "key": "price_currency",
                "prompt_key": "contracts.flow.murabaha.currency",
                "optional": True,
            },
            {
                "key": "payment_schedule",
                "prompt_key": "contracts.flow.murabaha.payment_schedule",
                "optional": True,
            },
            {
                "key": "delivery_term",
                "prompt_key": "contracts.flow.murabaha.delivery_term",
                "optional": True,
            },
        ],
    },
    "musharaka": {
        "title_key": "contracts.flow.type.musharaka",
        "topic": "contracts.partnership.musharaka",
        "fields": [
            {
                "key": "partner1_name",
                "prompt_key": "contracts.flow.musharaka.partner1_name",
            },
            {
                "key": "partner2_name",
                "prompt_key": "contracts.flow.musharaka.partner2_name",
            },
            {
                "key": "business_description",
                "prompt_key": "contracts.flow.musharaka.business_description",
                "optional": True,
            },
            {
                "key": "partner1_contribution",
                "prompt_key": "contracts.flow.musharaka.partner1_contribution",
            },
            {
                "key": "partner2_contribution",
                "prompt_key": "contracts.flow.musharaka.partner2_contribution",
            },
            {
                "key": "profit_split",
                "prompt_key": "contracts.flow.musharaka.profit_split",
                "percent_pair": True,
                "allow_percent": True,
            },
            {
                "key": "loss_share",
                "prompt_key": "contracts.flow.musharaka.loss_share",
                "optional": True,
            },
            {
                "key": "management_roles",
                "prompt_key": "contracts.flow.musharaka.management_roles",
                "optional": True,
            },
            {
                "key": "duration",
                "prompt_key": "contracts.flow.musharaka.duration",
                "optional": True,
            },
        ],
    },
    "mudaraba": {
        "title_key": "contracts.flow.type.mudaraba",
        "topic": "contracts.partnership.mudaraba",
        "fields": [
            {"key": "investor_name", "prompt_key": "contracts.flow.mudaraba.investor"},
            {"key": "manager_name", "prompt_key": "contracts.flow.mudaraba.manager"},
            {"key": "capital_amount", "prompt_key": "contracts.flow.mudaraba.capital"},
            {
                "key": "business_description",
                "prompt_key": "contracts.flow.mudaraba.business_description",
                "optional": True,
            },
            {
                "key": "duration",
                "prompt_key": "contracts.flow.mudaraba.duration",
                "optional": True,
            },
            {
                "key": "profit_share_investor",
                "prompt_key": "contracts.flow.mudaraba.profit_investor",
                "percent_value": True,
                "allow_percent": True,
            },
            {
                "key": "profit_share_manager",
                "prompt_key": "contracts.flow.mudaraba.profit_manager",
                "percent_value": True,
                "allow_percent": True,
            },
            {
                "key": "profit_distribution",
                "prompt_key": "contracts.flow.mudaraba.profit_distribution",
                "optional": True,
            },
            {
                "key": "loss_terms",
                "prompt_key": "contracts.flow.mudaraba.loss_terms",
                "optional": True,
            },
        ],
    },
    "inan": {
        "title_key": "contracts.flow.type.inan",
        "topic": "contracts.partnership.inan",
        "fields": [
            {"key": "partner1_name", "prompt_key": "contracts.flow.inan.partner1_name"},
            {"key": "partner2_name", "prompt_key": "contracts.flow.inan.partner2_name"},
            {
                "key": "business_description",
                "prompt_key": "contracts.flow.inan.business_description",
                "optional": True,
            },
            {"key": "partner1_contribution", "prompt_key": "contracts.flow.inan.partner1_contribution"},
            {"key": "partner2_contribution", "prompt_key": "contracts.flow.inan.partner2_contribution"},
            {
                "key": "profit_split",
                "prompt_key": "contracts.flow.inan.profit_split",
                "percent_pair": True,
                "allow_percent": True,
            },
            {
                "key": "management_roles",
                "prompt_key": "contracts.flow.inan.management_roles",
                "optional": True,
            },
            {
                "key": "duration",
                "prompt_key": "contracts.flow.inan.duration",
                "optional": True,
            },
        ],
    },
    "wakala": {
        "title_key": "contracts.flow.type.wakala",
        "topic": "contracts.partnership.wakala",
        "fields": [
            {"key": "principal_name", "prompt_key": "contracts.flow.wakala.principal"},
            {"key": "agent_name", "prompt_key": "contracts.flow.wakala.agent"},
            {"key": "agency_scope", "prompt_key": "contracts.flow.wakala.scope"},
            {
                "key": "agency_fee",
                "prompt_key": "contracts.flow.wakala.fee",
                "optional": True,
            },
            {
                "key": "duration",
                "prompt_key": "contracts.flow.wakala.duration",
                "optional": True,
            },
            {
                "key": "reporting_terms",
                "prompt_key": "contracts.flow.wakala.reporting_terms",
                "optional": True,
            },
            {
                "key": "termination_terms",
                "prompt_key": "contracts.flow.wakala.termination_terms",
                "optional": True,
            },
        ],
    },
    "hiba": {
        "title_key": "contracts.flow.type.hiba",
        "topic": "contracts.gratis.hiba",
        "fields": [
            {"key": "donor_name", "prompt_key": "contracts.flow.hiba.donor"},
            {"key": "recipient_name", "prompt_key": "contracts.flow.hiba.recipient"},
            {"key": "gift_description", "prompt_key": "contracts.flow.hiba.gift"},
            {
                "key": "return_condition",
                "prompt_key": "contracts.flow.hiba.return_condition",
                "choices": [
                    {"value": "yes", "label_key": "contracts.flow.choice.yes"},
                    {"value": "no", "label_key": "contracts.flow.choice.no"},
                ],
            },
        ],
    },
    "sadaqa": {
        "title_key": "contracts.flow.type.sadaqa",
        "topic": "contracts.gratis.sadaqa",
        "fields": [
            {"key": "donor_name", "prompt_key": "contracts.flow.sadaqa.donor"},
            {"key": "beneficiary_name", "prompt_key": "contracts.flow.sadaqa.beneficiary"},
            {"key": "donation_description", "prompt_key": "contracts.flow.sadaqa.description"},
            {
                "key": "donation_amount",
                "prompt_key": "contracts.flow.sadaqa.amount",
                "optional": True,
            },
            {
                "key": "donation_purpose",
                "prompt_key": "contracts.flow.sadaqa.purpose",
                "optional": True,
            },
            {
                "key": "transfer_method",
                "prompt_key": "contracts.flow.sadaqa.transfer_method",
                "optional": True,
            },
        ],
    },
    "ariya": {
        "title_key": "contracts.flow.type.ariya",
        "topic": "contracts.gratis.ariya",
        "fields": [
            {"key": "lender_name", "prompt_key": "contracts.flow.ariya.lender"},
            {"key": "borrower_name", "prompt_key": "contracts.flow.ariya.borrower"},
            {"key": "item_description", "prompt_key": "contracts.flow.ariya.item_description"},
            {"key": "use_term", "prompt_key": "contracts.flow.ariya.use_term"},
            {
                "key": "return_condition",
                "prompt_key": "contracts.flow.ariya.return_condition",
                "optional": True,
            },
            {
                "key": "liability_terms",
                "prompt_key": "contracts.flow.ariya.liability_terms",
                "optional": True,
            },
        ],
    },
    "waqf": {
        "title_key": "contracts.flow.type.waqf",
        "topic": "contracts.gratis.waqf",
        "fields": [
            {"key": "founder_name", "prompt_key": "contracts.flow.waqf.founder"},
            {"key": "manager_name", "prompt_key": "contracts.flow.waqf.manager"},
            {"key": "waqf_asset", "prompt_key": "contracts.flow.waqf.asset"},
            {"key": "waqf_purpose", "prompt_key": "contracts.flow.waqf.purpose"},
            {"key": "beneficiaries", "prompt_key": "contracts.flow.waqf.beneficiaries"},
            {
                "key": "management_conditions",
                "prompt_key": "contracts.flow.waqf.management_conditions",
                "optional": True,
            },
        ],
    },
    "wasiya": {
        "title_key": "contracts.flow.type.wasiya",
        "topic": "contracts.gratis.wasiya",
        "fields": [
            {"key": "testator_name", "prompt_key": "contracts.flow.wasiya.testator"},
            {"key": "beneficiary_name", "prompt_key": "contracts.flow.wasiya.beneficiary"},
            {
                "key": "executor_name",
                "prompt_key": "contracts.flow.wasiya.executor",
                "optional": True,
            },
            {"key": "bequest_description", "prompt_key": "contracts.flow.wasiya.description"},
            {
                "key": "bequest_conditions",
                "prompt_key": "contracts.flow.wasiya.conditions",
                "optional": True,
            },
        ],
    },
    "amana": {
        "title_key": "contracts.flow.type.amana",
        "topic": "contracts.settlement.amana",
        "fields": [
            {"key": "owner_name", "prompt_key": "contracts.flow.amana.owner"},
            {"key": "custodian_name", "prompt_key": "contracts.flow.amana.custodian"},
            {"key": "asset_description", "prompt_key": "contracts.flow.amana.asset"},
            {"key": "storage_term", "prompt_key": "contracts.flow.amana.term"},
            {
                "key": "storage_conditions",
                "prompt_key": "contracts.flow.amana.storage_conditions",
                "optional": True,
            },
            {
                "key": "custodian_liability",
                "prompt_key": "contracts.flow.amana.custodian_liability",
                "optional": True,
            },
            {
                "key": "return_terms",
                "prompt_key": "contracts.flow.amana.return_terms",
                "optional": True,
            },
        ],
    },
    "uaria": {
        "title_key": "contracts.flow.type.uaria",
        "topic": "contracts.settlement.uaria",
        "fields": [
            {"key": "lender_name", "prompt_key": "contracts.flow.uaria.lender"},
            {"key": "borrower_name", "prompt_key": "contracts.flow.uaria.borrower"},
            {"key": "item_description", "prompt_key": "contracts.flow.uaria.item_description"},
            {"key": "use_term", "prompt_key": "contracts.flow.uaria.use_term"},
            {
                "key": "return_condition",
                "prompt_key": "contracts.flow.uaria.return_condition",
                "optional": True,
            },
            {
                "key": "liability_terms",
                "prompt_key": "contracts.flow.uaria.liability_terms",
                "optional": True,
            },
        ],
    },
    "kafala": {
        "title_key": "contracts.flow.type.kafala",
        "topic": "contracts.finance.kafala",
        "fields": [
            {"key": "guarantor_name", "prompt_key": "contracts.flow.kafala.guarantor"},
            {"key": "debtor_name", "prompt_key": "contracts.flow.kafala.debtor"},
            {
                "key": "creditor_name",
                "prompt_key": "contracts.flow.kafala.creditor",
                "optional": True,
            },
            {"key": "obligation", "prompt_key": "contracts.flow.kafala.obligation"},
            {"key": "guarantee_term", "prompt_key": "contracts.flow.kafala.term"},
        ],
    },
    "rahn": {
        "title_key": "contracts.flow.type.rahn",
        "topic": "contracts.finance.rahn",
        "fields": [
            {"key": "pledger_name", "prompt_key": "contracts.flow.rahn.pledger"},
            {"key": "pledgee_name", "prompt_key": "contracts.flow.rahn.pledgee"},
            {"key": "pledged_asset", "prompt_key": "contracts.flow.rahn.asset"},
            {
                "key": "asset_value",
                "prompt_key": "contracts.flow.rahn.asset_value",
                "optional": True,
            },
            {"key": "secured_debt_amount", "prompt_key": "contracts.flow.rahn.debt_amount"},
            {"key": "debt_due_date", "prompt_key": "contracts.flow.rahn.debt_due_date"},
            {
                "key": "storage_terms",
                "prompt_key": "contracts.flow.rahn.storage_terms",
                "optional": True,
            },
            {
                "key": "redemption_terms",
                "prompt_key": "contracts.flow.rahn.redemption_terms",
                "optional": True,
            },
        ],
    },
    "hawala": {
        "title_key": "contracts.flow.type.hawala",
        "topic": "contracts.finance.hawala",
        "fields": [
            {"key": "transferor_name", "prompt_key": "contracts.flow.hawala.transferor"},
            {"key": "new_debtor_name", "prompt_key": "contracts.flow.hawala.new_debtor"},
            {"key": "transferee_name", "prompt_key": "contracts.flow.hawala.transferee"},
            {"key": "debt_amount", "prompt_key": "contracts.flow.hawala.debt_amount"},
            {
                "key": "debt_currency",
                "prompt_key": "contracts.flow.hawala.debt_currency",
                "optional": True,
            },
            {"key": "due_date", "prompt_key": "contracts.flow.hawala.due_date"},
            {
                "key": "transfer_terms",
                "prompt_key": "contracts.flow.hawala.transfer_terms",
                "optional": True,
            },
        ],
    },
    "sulh": {
        "title_key": "contracts.flow.type.sulh",
        "topic": "contracts.settlement.sulh",
        "fields": [
            {"key": "party_one_name", "prompt_key": "contracts.flow.sulh.party_one_name"},
            {
                "key": "party_one_document",
                "prompt_key": "contracts.flow.sulh.party_one_document",
                "optional": True,
            },
            {
                "key": "party_one_address",
                "prompt_key": "contracts.flow.sulh.party_one_address",
                "optional": True,
            },
            {
                "key": "party_one_contact",
                "prompt_key": "contracts.flow.sulh.party_one_contact",
                "optional": True,
            },
            {"key": "party_two_name", "prompt_key": "contracts.flow.sulh.party_two_name"},
            {
                "key": "party_two_document",
                "prompt_key": "contracts.flow.sulh.party_two_document",
                "optional": True,
            },
            {
                "key": "party_two_address",
                "prompt_key": "contracts.flow.sulh.party_two_address",
                "optional": True,
            },
            {
                "key": "party_two_contact",
                "prompt_key": "contracts.flow.sulh.party_two_contact",
                "optional": True,
            },
            {"key": "dispute_subject", "prompt_key": "contracts.flow.sulh.dispute_subject"},
            {
                "key": "proposed_resolution",
                "prompt_key": "contracts.flow.sulh.proposed_resolution",
            },
            {
                "key": "claims_waived",
                "prompt_key": "contracts.flow.sulh.claims_waived",
                "choices": [
                    {"value": "yes", "label_key": "contracts.flow.choice.yes"},
                    {"value": "no", "label_key": "contracts.flow.choice.no"},
                ],
            },
        ],
    },
    "nikah": {
        "title_key": "contracts.flow.type.nikah",
        "topic": "contracts.family.nikah",
        "fields": [
            {"key": "groom_name", "prompt_key": "contracts.flow.nikah.groom"},
            {"key": "bride_name", "prompt_key": "contracts.flow.nikah.bride"},
            {
                "key": "wali_name",
                "prompt_key": "contracts.flow.nikah.wali",
                "optional": True,
            },
            {"key": "mahr_amount", "prompt_key": "contracts.flow.nikah.mahr"},
            {"key": "witnesses", "prompt_key": "contracts.flow.nikah.witnesses"},
            {"key": "marriage_date_place", "prompt_key": "contracts.flow.nikah.date_place"},
            {
                "key": "additional_terms",
                "prompt_key": "contracts.flow.nikah.additional_terms",
                "optional": True,
            },
        ],
    },
    "talaq": {
        "title_key": "contracts.flow.type.talaq",
        "topic": "contracts.family.talaq",
        "fields": [
            {"key": "husband_name", "prompt_key": "contracts.flow.talaq.husband"},
            {"key": "wife_name", "prompt_key": "contracts.flow.talaq.wife"},
            {"key": "talaq_date", "prompt_key": "contracts.flow.talaq.date"},
            {
                "key": "iddah_terms",
                "prompt_key": "contracts.flow.talaq.iddah_terms",
                "optional": True,
            },
            {
                "key": "rights_settlement",
                "prompt_key": "contracts.flow.talaq.rights_settlement",
                "optional": True,
            },
        ],
    },
    "khul": {
        "title_key": "contracts.flow.type.khul",
        "topic": "contracts.family.khul",
        "fields": [
            {"key": "wife_name", "prompt_key": "contracts.flow.khul.wife"},
            {"key": "husband_name", "prompt_key": "contracts.flow.khul.husband"},
            {"key": "compensation_amount", "prompt_key": "contracts.flow.khul.compensation"},
            {
                "key": "agreement_date",
                "prompt_key": "contracts.flow.khul.date",
                "optional": True,
            },
            {
                "key": "additional_terms",
                "prompt_key": "contracts.flow.khul.additional_terms",
                "optional": True,
            },
        ],
    },
    "ridaa": {
        "title_key": "contracts.flow.type.ridaa",
        "topic": "contracts.family.ridaa",
        "fields": [
            {"key": "nurse_name", "prompt_key": "contracts.flow.ridaa.nurse"},
            {"key": "child_name", "prompt_key": "contracts.flow.ridaa.child"},
            {"key": "guardian_name", "prompt_key": "contracts.flow.ridaa.guardian"},
            {"key": "feeding_period", "prompt_key": "contracts.flow.ridaa.period"},
            {
                "key": "compensation",
                "prompt_key": "contracts.flow.ridaa.compensation",
                "optional": True,
            },
            {
                "key": "additional_terms",
                "prompt_key": "contracts.flow.ridaa.additional_terms",
                "optional": True,
            },
        ],
    },
}

CONTRACT_FLOW_TYPES = list(CONTRACT_FLOW_DEFINITIONS.keys())

UNCLEAR_TERMS_PATTERNS = [
    r"как получится",
    r"потом решим",
    r"по ситуации",
    r"по обстоятельствам",
    r"как договоримся",
    r"по договоренности",
]
RIBA_PATTERNS = [r"\bпроцент", r"\bпроценты\b", r"\bриб[аы]\b", r"%"]
RIBA_STRICT_PATTERNS = [r"сверху", r"в обмен на время", r"за время", r"за срок"]
HARAM_PATTERNS = [
    r"\bалкогол",
    r"\bнаркот",
    r"оружи[ея] массового поражения",
]
PROFIT_GUARANTEE_PATTERNS = [
    r"гарантир",
    r"фиксированн[аяы] прибыль",
    r"гарантия прибыли",
]


AUTO_INTENT_QUESTION = {
    "key": "intent",
    "question_key": "contracts.auto.question.intent",
    "choices": [
        {"value": "family", "label_key": "contracts.auto.option.family"},
        {"value": "money", "label_key": "contracts.auto.option.money"},
        {"value": "purchase", "label_key": "contracts.auto.option.purchase"},
        {"value": "work", "label_key": "contracts.auto.option.work"},
        {"value": "rent", "label_key": "contracts.auto.option.rent"},
        {"value": "storage", "label_key": "contracts.auto.option.storage"},
        {"value": "gift", "label_key": "contracts.auto.option.gift"},
        {"value": "guarantee", "label_key": "contracts.auto.option.guarantee"},
        {"value": "settlement", "label_key": "contracts.auto.option.settlement"},
    ],
}
AUTO_HAS_MONEY_QUESTION = {
    "key": "has_money",
    "question_key": "contracts.auto.question.money",
    "choices": [
        {"value": "yes", "label_key": "contracts.flow.choice.yes"},
        {"value": "no", "label_key": "contracts.flow.choice.no"},
    ],
}
AUTO_MONEY_KIND_QUESTION = {
    "key": "money_kind",
    "question_key": "contracts.auto.question.money_kind",
    "choices": [
        {"value": "loan", "label_key": "contracts.auto.option.loan"},
        {"value": "purchase", "label_key": "contracts.auto.option.purchase"},
        {"value": "rent", "label_key": "contracts.auto.option.rent"},
        {"value": "investment", "label_key": "contracts.auto.option.investment"},
    ],
}
AUTO_GOODS_QUESTION = {
    "key": "goods_timing",
    "question_key": "contracts.auto.question.goods",
    "choices": [
        {"value": "now", "label_key": "contracts.auto.option.goods_now"},
        {"value": "later", "label_key": "contracts.auto.option.goods_later"},
        {"value": "custom", "label_key": "contracts.auto.option.goods_custom"},
        {"value": "none", "label_key": "contracts.auto.option.goods_none"},
    ],
}
AUTO_INVESTMENT_QUESTION = {
    "key": "investment_kind",
    "question_key": "contracts.auto.question.investment",
    "choices": [
        {"value": "mudaraba", "label_key": "contracts.flow.type.mudaraba"},
        {"value": "musharaka", "label_key": "contracts.flow.type.musharaka"},
    ],
}


def _contract_title(contract_slug: str, lang_code: str) -> str:
    definition = CONTRACT_FLOW_DEFINITIONS.get(contract_slug, {})
    return get_text(str(definition.get("title_key") or contract_slug), lang_code)


def _find_next_field_index(
    fields: list[dict[str, object]],
    start_index: int,
    field_data: dict[str, str],
) -> Optional[int]:
    for idx in range(start_index, len(fields)):
        field = fields[idx]
        depends_on = field.get("depends_on") or {}
        if depends_on:
            dep_key = str(depends_on.get("key") or "")
            expected = depends_on.get("value")
            actual = field_data.get(dep_key)
            if expected is None:
                if not actual:
                    continue
            elif isinstance(expected, (list, tuple, set)):
                if actual not in expected:
                    continue
            else:
                if actual != expected:
                    continue
        return idx
    return None


def _draw_contract_frame(canvas_obj: canvas.Canvas, _doc: SimpleDocTemplate) -> None:
    width, height = A4
    margin = 36
    inner = margin + 6

    canvas_obj.saveState()
    canvas_obj.setStrokeColor(PRIMARY_COLOR)
    canvas_obj.setLineWidth(1.6)
    canvas_obj.rect(margin, margin, width - 2 * margin, height - 2 * margin)

    canvas_obj.setStrokeColor(ACCENT_COLOR)
    canvas_obj.setLineWidth(0.8)
    canvas_obj.rect(inner, inner, width - 2 * inner, height - 2 * inner)

    canvas_obj.setFillColor(ACCENT_COLOR)
    for x, y in [
        (margin, margin),
        (width - margin, margin),
        (margin, height - margin),
        (width - margin, height - margin),
    ]:
        canvas_obj.circle(x, y, 2.2, stroke=0, fill=1)

    canvas_obj.setStrokeColor(colors.Color(0.85, 0.82, 0.75))
    canvas_obj.setLineWidth(0.6)
    cx, cy = width / 2, height / 2
    r_outer, r_inner = 70, 30
    points = []
    for i in range(16):
        angle = i * math.pi / 8
        r = r_outer if i % 2 == 0 else r_inner
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    for idx in range(len(points)):
        x1, y1 = points[idx]
        x2, y2 = points[(idx + 1) % len(points)]
        canvas_obj.line(x1, y1, x2, y2)

    canvas_obj.setStrokeColor(colors.Color(0.75, 0.75, 0.75))
    canvas_obj.setLineWidth(0.5)
    canvas_obj.line(margin + 40, margin + 18, width - margin - 40, margin + 18)
    canvas_obj.restoreState()


def _looks_like_title(line: str) -> bool:
    normalized = line.strip()
    if not normalized:
        return False
    lowered = normalized.lower()
    if "договор" in lowered or "contract" in lowered:
        return True
    letters = [ch for ch in normalized if ch.isalpha()]
    if not letters:
        return False
    upper_ratio = sum(ch.isupper() for ch in letters) / len(letters)
    return upper_ratio >= 0.75


def _is_section_heading(line: str) -> bool:
    if not re.match(r"^\d+\.\s", line):
        return False
    letters = [ch for ch in line if ch.isalpha()]
    if not letters:
        return False
    upper_ratio = sum(ch.isupper() for ch in letters) / len(letters)
    return upper_ratio >= 0.7


def _is_subtitle_line(line: str) -> bool:
    lowered = line.lower()
    return lowered.startswith("во имя") or lowered.startswith("in the name") or lowered.startswith("хвала")


def _is_note_line(line: str) -> bool:
    lowered = line.lower()
    return lowered.startswith("аллах") or lowered.startswith("allah")


def _apply_symbol_font(text: str, symbol_font: Optional[str]) -> str:
    if not symbol_font or _SYMBOL_GLYPH not in text:
        return text
    return text.replace(_SYMBOL_GLYPH, f"<font face='{symbol_font}'>{_SYMBOL_GLYPH}</font>")


def _build_contract_pdf_styles(
    regular_font: str,
    bold_font: str,
    italic_font: str,
) -> dict[str, ParagraphStyle]:
    return {
        "title": ParagraphStyle(
            "title",
            fontName=bold_font,
            fontSize=16,
            leading=20,
            alignment=TA_CENTER,
            textColor=PRIMARY_COLOR,
            spaceAfter=10,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            fontName=italic_font,
            fontSize=11.5,
            leading=14,
            alignment=TA_CENTER,
            textColor=colors.black,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body",
            fontName=regular_font,
            fontSize=11,
            leading=15,
            alignment=TA_LEFT,
            textColor=colors.black,
            spaceAfter=6,
        ),
        "section": ParagraphStyle(
            "section",
            fontName=bold_font,
            fontSize=12.2,
            leading=16,
            alignment=TA_LEFT,
            textColor=PRIMARY_COLOR,
            spaceBefore=8,
            spaceAfter=4,
        ),
        "note": ParagraphStyle(
            "note",
            fontName=italic_font,
            fontSize=10.5,
            leading=13,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#444444"),
            spaceAfter=6,
        ),
    }


def _build_contract_story(
    text: str,
    title: str,
    styles: dict[str, ParagraphStyle],
    symbol_font: Optional[str],
) -> list:
    lines = text.splitlines()
    story: list = []

    first_idx = next((idx for idx, line in enumerate(lines) if line.strip()), None)
    if first_idx is None:
        if title:
            story.append(Paragraph(_apply_symbol_font(escape(title), symbol_font), styles["title"]))
        return story

    first_line = lines[first_idx].strip()
    if _looks_like_title(first_line):
        story.append(Paragraph(_apply_symbol_font(escape(first_line), symbol_font), styles["title"]))
        lines = lines[first_idx + 1 :]
    else:
        if title:
            story.append(Paragraph(_apply_symbol_font(escape(title), symbol_font), styles["title"]))
        lines = lines[first_idx:]

    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped:
            story.append(Spacer(1, 6))
            continue
        if re.fullmatch(r"[-_]{3,}", stripped):
            story.append(Spacer(1, 8))
            continue
        if _is_section_heading(stripped):
            style_key = "section"
        elif _is_subtitle_line(stripped):
            style_key = "subtitle"
        elif _is_note_line(stripped):
            style_key = "note"
        else:
            style_key = "body"
        styled_text = _apply_symbol_font(escape(stripped), symbol_font)
        story.append(Paragraph(styled_text, styles[style_key]))

    return story


def _build_contract_pdf(text: str, title: str) -> bytes:
    buffer = io.BytesIO()
    regular_font, bold_font, italic_font, symbol_font = _ensure_pdf_fonts()
    regular_name = regular_font or "Helvetica"
    bold_name = bold_font or regular_name
    italic_name = italic_font or regular_name
    styles = _build_contract_pdf_styles(regular_name, bold_name, italic_name)
    story = _build_contract_story(text, title, styles, symbol_font)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=72,
        bottomMargin=54,
        leftMargin=54,
        rightMargin=54,
        title=title,
    )
    doc.build(story, onFirstPage=_draw_contract_frame, onLaterPages=_draw_contract_frame)
    return buffer.getvalue()


async def _ensure_contract_document(
    db: DB,
    *,
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
        pdf_bytes = _build_contract_pdf(rendered_text, title)
    except Exception:
        logger.exception("Failed to build PDF for contract document user_id=%s", user_id)
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
        logger.exception("Failed to persist contract document user_id=%s", user_id)


def _build_contract_actions_keyboard(
    lang_code: str,
    *,
    allow_send_court: bool = False,
    allow_delete: bool = True,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=get_text("contracts.flow.button.confirm", lang_code),
                callback_data="contract_confirm",
            )
        ],
        [
            InlineKeyboardButton(
                text=get_text("contracts.flow.button.edit", lang_code),
                callback_data="contract_edit",
            )
        ],
        [
            InlineKeyboardButton(
                text=get_text("contracts.flow.button.send_other", lang_code),
                callback_data="contract_send_other",
            )
        ],
    ]
    if allow_send_court:
        rows.append(
            [
                InlineKeyboardButton(
                    text=get_text("contracts.flow.button.send_court", lang_code),
                    callback_data="contract_send_court",
                )
            ]
        )
    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text=get_text("contracts.flow.button.download_txt", lang_code),
                    callback_data="contract_download_txt",
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("contracts.flow.button.download_pdf", lang_code),
                    callback_data="contract_download_pdf",
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("contracts.flow.button.send_scholar", lang_code),
                    callback_data="contract_send_scholar",
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("button.cancel", lang_code),
                    callback_data="contract_cancel",
                )
            ],
        ]
    )
    if allow_delete:
        rows.insert(
            -1,
            [
                InlineKeyboardButton(
                    text=get_text("contracts.flow.button.delete", lang_code),
                    callback_data="contract_delete",
                )
            ],
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
                ),
            ],
        ]
    )


async def _show_contract_actions(
    message: Message,
    lang_code: str,
    *,
    db: DB | None = None,
    state: FSMContext | None = None,
) -> None:
    allow_send_court = False
    allow_delete = True
    if db is not None and state is not None:
        data = await state.get_data()
        contract_id = data.get("contract_id")
        if contract_id:
            contract = await db.contracts.get_contract(contract_id=int(contract_id))
            allow_send_court = _is_contract_fully_signed(contract)
            allow_delete = not _is_contract_counterparty_signed(contract)
    await message.answer(
        get_text("contracts.flow.actions.title", lang_code),
        reply_markup=_build_contract_actions_keyboard(
            lang_code,
            allow_send_court=allow_send_court,
            allow_delete=allow_delete,
        ),
    )


def _choice_label(choice: dict[str, object], lang_code: str) -> str:
    return get_text(str(choice.get("label_key") or ""), lang_code)


def _normalize_percent_value(value: str) -> Optional[str]:
    match = re.search(r"(\d+(?:[.,]\d+)?)", value)
    if not match:
        return None
    number = float(match.group(1).replace(",", "."))
    if number <= 0 or number > 100:
        return None
    if abs(number - round(number)) < 0.0001:
        formatted = str(int(round(number)))
    else:
        formatted = f"{number:.2f}".rstrip("0").rstrip(".")
    return f"{formatted}%"


def _normalize_percent_pair(value: str) -> Optional[str]:
    matches = re.findall(r"\d+(?:[.,]\d+)?", value)
    if len(matches) != 2:
        return None
    first = float(matches[0].replace(",", "."))
    second = float(matches[1].replace(",", "."))
    if first <= 0 or second <= 0:
        return None
    if abs((first + second) - 100) > 0.01:
        return None
    first_fmt = (
        str(int(round(first))) if abs(first - round(first)) < 0.0001 else f"{first:.2f}".rstrip("0").rstrip(".")
    )
    second_fmt = (
        str(int(round(second))) if abs(second - round(second)) < 0.0001 else f"{second:.2f}".rstrip("0").rstrip(".")
    )
    return f"{first_fmt}% / {second_fmt}%"


def _has_pattern(patterns: list[str], text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _validate_contract_value(
    contract_slug: str,
    field: dict[str, object],
    value: str,
    lang_code: str,
    field_data: dict[str, str],
) -> tuple[Optional[str], Optional[str]]:
    if field.get("choices"):
        choices = {str(choice.get("value")) for choice in field.get("choices") or []}
        if value not in choices:
            return None, get_text("contracts.flow.choice.required", lang_code)
    else:
        if not value:
            return None, get_text("contracts.flow.field.required", lang_code)

    if field.get("percent_pair"):
        normalized = _normalize_percent_pair(value)
        if not normalized:
            return None, get_text("contracts.validation.percent_invalid", lang_code)
        value = normalized

    if field.get("percent_value"):
        normalized = _normalize_percent_value(value)
        if not normalized:
            return None, get_text("contracts.validation.percent_invalid", lang_code)
        value = normalized

    allow_percent = bool(field.get("allow_percent"))
    if not field.get("choices"):
        if _has_pattern(UNCLEAR_TERMS_PATTERNS, value):
            return None, get_text("contracts.validation.unclear_terms", lang_code)
        if _has_pattern(HARAM_PATTERNS, value):
            return None, get_text("contracts.validation.haram_goods", lang_code)
        if _has_pattern(RIBA_STRICT_PATTERNS, value):
            return None, get_text("contracts.validation.riba", lang_code)
        if _has_pattern(RIBA_PATTERNS, value) and not allow_percent:
            return None, get_text("contracts.validation.riba", lang_code)

    if contract_slug == "salam" and field.get("key") == "fixed_price":
        if _has_pattern(UNCLEAR_TERMS_PATTERNS, value):
            return None, get_text("contracts.validation.price_fixed", lang_code)

    if contract_slug == "mudaraba":
        if not field.get("choices") and _has_pattern(PROFIT_GUARANTEE_PATTERNS, value):
            return None, get_text("contracts.validation.profit_guarantee", lang_code)
        if field.get("key") == "profit_share_manager":
            investor_share = field_data.get("profit_share_investor")
            if investor_share:
                inv = _normalize_percent_value(investor_share)
                mgr = _normalize_percent_value(value)
                if not inv or not mgr:
                    return None, get_text("contracts.validation.percent_invalid", lang_code)
                inv_value = float(inv.strip("%"))
                mgr_value = float(mgr.strip("%"))
                if abs((inv_value + mgr_value) - 100) > 0.01:
                    return None, get_text("contracts.validation.percent_invalid", lang_code)
                value = mgr

    if contract_slug == "hiba" and field.get("key") == "return_condition":
        if value == "yes":
            return None, get_text("contracts.validation.hiba_return_forbidden", lang_code)

    return value, None


def _render_contract_template(
    template_text: str,
    field_data: dict[str, str],
    contract_slug: str,
    lang_code: str,
) -> str:
    definition = CONTRACT_FLOW_DEFINITIONS.get(contract_slug, {})
    render_values: dict[str, str] = {}
    fields = definition.get("fields") or []
    if isinstance(fields, list):
        for field in fields:
            key = str(field.get("key") or "")
            if not key:
                continue
            raw_value = field_data.get(key, "")
            if field.get("choices"):
                label = raw_value
                for choice in field.get("choices") or []:
                    if str(choice.get("value")) == raw_value:
                        label = _choice_label(choice, lang_code)
                        break
                render_values[key] = label
            else:
                render_values[key] = raw_value

    missing_keys = {k for k, v in render_values.items() if not v}
    lines: list[str] = []
    for line in template_text.splitlines():
        if any(re.search(rf"{{{{\s*{re.escape(key)}\s*}}}}", line) for key in missing_keys):
            continue
        new_line = re.sub(
            r"{{\s*([a-zA-Z0-9_]+)\s*}}",
            lambda match: render_values.get(match.group(1), ""),
            line,
        )
        if "{{" in new_line and "}}" in new_line:
            continue
        if not new_line.strip():
            lines.append("")
            continue
        if re.search(r":\s*$", new_line) and not re.search(r":\s*\S", new_line):
            continue
        lines.append(new_line.rstrip())
    return "\n".join(lines).strip()


def _build_contract_type_keyboard(lang_code: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for contract_slug in CONTRACT_FLOW_TYPES:
        rows.append(
            [
                InlineKeyboardButton(
                    text=_contract_title(contract_slug, lang_code),
                    callback_data=f"contract_new:{contract_slug}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=get_text("contracts.auto.button", lang_code),
                callback_data="contract_auto",
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text=get_text("button.back", lang_code),
                callback_data="back_to_contracts",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _build_contract_field_keyboard(
    field: dict[str, object],
    lang_code: str,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for choice in field.get("choices") or []:
        rows.append(
            [
                InlineKeyboardButton(
                    text=_choice_label(choice, lang_code),
                    callback_data=f"contract_choice:{choice.get('value')}",
                )
            ]
        )
    if field.get("optional"):
        rows.append(
            [
                InlineKeyboardButton(
                    text=get_text("contracts.flow.button.skip", lang_code),
                    callback_data="contract_field_skip",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=get_text("button.cancel", lang_code),
                callback_data="contract_cancel",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _build_contract_generate_keyboard(lang_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("contracts.flow.button.generate", lang_code),
                    callback_data="contract_generate",
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("button.cancel", lang_code),
                    callback_data="contract_cancel",
                )
            ],
        ]
    )


def _next_auto_question(answers: dict[str, str]) -> Optional[dict[str, object]]:
    if "intent" not in answers:
        return AUTO_INTENT_QUESTION

    intent = answers["intent"]
    if intent in {"family", "gift", "storage", "rent", "guarantee", "settlement"}:
        return None

    if "has_money" not in answers:
        return AUTO_HAS_MONEY_QUESTION

    if answers["has_money"] == "no":
        return None

    if "money_kind" not in answers:
        return AUTO_MONEY_KIND_QUESTION

    if answers["money_kind"] == "purchase":
        if "goods_timing" not in answers:
            return AUTO_GOODS_QUESTION
        return None

    if answers["money_kind"] == "investment":
        if "investment_kind" not in answers:
            return AUTO_INVESTMENT_QUESTION
        return None

    return None


def _auto_pick_contract(answers: dict[str, str]) -> Optional[str]:
    intent = answers.get("intent")
    if intent == "gift":
        return "hiba"
    if intent == "storage":
        return "amana"
    if intent == "rent":
        return "ijara"
    if intent == "guarantee":
        return "kafala"
    if intent == "settlement":
        return "sulh"
    if intent == "family":
        return None

    money_kind = answers.get("money_kind")
    if money_kind == "loan":
        return "qard"
    if money_kind == "rent":
        return "ijara"
    if money_kind == "purchase":
        timing = answers.get("goods_timing")
        if timing == "now":
            return "bay"
        if timing == "later":
            return "salam"
        if timing == "custom":
            return "istisna"
    if money_kind == "investment":
        return answers.get("investment_kind")

    if intent == "work":
        return "istisna"

    return None


async def _ask_next_contract_field(
    target: Message | CallbackQuery,
    state: FSMContext,
    lang_code: str,
) -> None:
    data = await state.get_data()
    fields = list(data.get("contract_fields") or [])
    field_data = dict(data.get("field_data") or {})
    start_index = int(data.get("field_index") or 0)
    next_index = _find_next_field_index(fields, start_index, field_data)

    if next_index is None:
        contract_title = str(data.get("contract_title") or "")
        await state.set_state(ContractTemplateFlow.preview)
        ready_text = get_text("contracts.flow.ready", lang_code, contract=contract_title)
        if isinstance(target, CallbackQuery):
            await target.message.answer(ready_text, reply_markup=_build_contract_generate_keyboard(lang_code))
        else:
            await target.answer(ready_text, reply_markup=_build_contract_generate_keyboard(lang_code))
        return

    field = fields[next_index]
    prompt = get_text(str(field.get("prompt_key") or ""), lang_code)
    await state.update_data(field_index=next_index)
    keyboard = _build_contract_field_keyboard(field, lang_code)

    if isinstance(target, CallbackQuery):
        await target.message.answer(prompt, reply_markup=keyboard)
    else:
        await target.answer(prompt, reply_markup=keyboard)


async def _show_contract_creation_menu(
    message: types.Message,
    lang_code: str,
) -> None:
    text = get_text("contracts.flow.title", lang_code)
    await message.answer(text, reply_markup=_build_contract_type_keyboard(lang_code))


async def _start_contract_flow(
    target: Message | CallbackQuery,
    state: FSMContext,
    contract_slug: str,
    lang_code: str,
) -> None:
    definition = CONTRACT_FLOW_DEFINITIONS.get(contract_slug)
    if not definition:
        if isinstance(target, CallbackQuery):
            await target.answer(get_text("error.request.invalid", lang_code), show_alert=True)
        else:
            await target.answer(get_text("error.request.invalid", lang_code))
        return

    await state.set_state(ContractTemplateFlow.waiting_for_field)
    await state.update_data(
        contract_type=contract_slug,
        contract_title=_contract_title(contract_slug, lang_code),
        contract_topic=str(definition.get("topic") or ""),
        contract_fields=definition.get("fields") or [],
        field_index=0,
        field_data={},
        rendered_text="",
        contract_id=None,
    )
    await _ask_next_contract_field(target, state, lang_code)


async def _ask_auto_question(
    message: Message | CallbackQuery,
    question: dict[str, object],
    lang_code: str,
) -> None:
    rows: list[list[InlineKeyboardButton]] = []
    for choice in question.get("choices") or []:
        rows.append(
            [
                InlineKeyboardButton(
                    text=get_text(str(choice.get("label_key") or ""), lang_code),
                    callback_data=f"contract_auto_answer:{question.get('key')}:{choice.get('value')}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=get_text("button.cancel", lang_code),
                callback_data="contract_cancel",
            )
        ]
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=rows)
    text = get_text(str(question.get("question_key") or ""), lang_code)
    if isinstance(message, CallbackQuery):
        await message.message.answer(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data == "contract_auto")
async def handle_contract_auto_start(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await state.set_state(ContractAutoPickFlow.waiting_for_answer)
    await state.update_data(auto_answers={})
    await _ask_auto_question(callback, AUTO_INTENT_QUESTION, lang_code)


@router.callback_query(F.data.startswith("contract_auto_answer:"))
async def handle_contract_auto_answer(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    parts = (callback.data or "").split(":", 2)
    if len(parts) != 3:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    _, key, value = parts
    data = await state.get_data()
    answers = dict(data.get("auto_answers") or {})
    answers[key] = value
    await state.update_data(auto_answers=answers)

    question = _next_auto_question(answers)
    if question:
        await _ask_auto_question(callback, question, lang_code)
        return

    contract_slug = _auto_pick_contract(answers)
    if answers.get("intent") == "family":
        await state.clear()
        await callback.message.answer(get_text("contracts.auto.family", lang_code))
        await _show_contract_creation_menu(callback.message, lang_code)
        return

    if not contract_slug:
        await state.clear()
        await callback.message.answer(get_text("contracts.auto.unsupported", lang_code))
        await _show_contract_creation_menu(callback.message, lang_code)
        return

    contract_title = _contract_title(contract_slug, lang_code)
    await state.set_state(ContractAutoPickFlow.waiting_for_confirm)
    await callback.message.answer(
        get_text("contracts.auto.result", lang_code, contract=contract_title),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=get_text("contracts.auto.button.confirm", lang_code),
                        callback_data=f"contract_auto_confirm:{contract_slug}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=get_text("contracts.auto.button.restart", lang_code),
                        callback_data="contract_auto_restart",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=get_text("button.back", lang_code),
                        callback_data="create_contract",
                    )
                ],
            ]
        ),
    )


@router.callback_query(F.data == "contract_auto_restart")
async def handle_contract_auto_restart(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await state.set_state(ContractAutoPickFlow.waiting_for_answer)
    await state.update_data(auto_answers={})
    await _ask_auto_question(callback, AUTO_INTENT_QUESTION, lang_code)


@router.callback_query(F.data.startswith("contract_auto_confirm:"))
async def handle_contract_auto_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    contract_slug = (callback.data or "").split(":", 1)[-1].strip()
    await _start_contract_flow(callback, state, contract_slug, lang_code)


@router.callback_query(F.data.startswith("contract_new:"))
async def handle_contract_new(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    contract_slug = (callback.data or "").split(":", 1)[-1].strip()
    await _start_contract_flow(callback, state, contract_slug, lang_code)


@router.callback_query(F.data.startswith("contract_choice:"))
async def handle_contract_choice(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    value = (callback.data or "").split(":", 1)[-1].strip()
    data = await state.get_data()
    contract_slug = str(data.get("contract_type") or "")
    fields = list(data.get("contract_fields") or [])
    field_index = int(data.get("field_index") or 0)
    field_data = dict(data.get("field_data") or {})
    if not contract_slug or field_index >= len(fields):
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    field = fields[field_index]
    normalized, error = _validate_contract_value(contract_slug, field, value, lang_code, field_data)
    if error:
        await callback.message.answer(error)
        await _ask_next_contract_field(callback, state, lang_code)
        return

    field_data[str(field.get("key") or "")] = normalized or ""
    await state.update_data(field_data=field_data, field_index=field_index + 1)
    await _ask_next_contract_field(callback, state, lang_code)


@router.callback_query(F.data == "contract_field_skip")
async def handle_contract_field_skip(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    data = await state.get_data()
    fields = list(data.get("contract_fields") or [])
    field_index = int(data.get("field_index") or 0)
    field_data = dict(data.get("field_data") or {})
    if field_index >= len(fields):
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    field = fields[field_index]
    if not field.get("optional"):
        await callback.message.answer(get_text("contracts.flow.field.required", lang_code))
        await _ask_next_contract_field(callback, state, lang_code)
        return
    field_data[str(field.get("key") or "")] = ""
    await state.update_data(field_data=field_data, field_index=field_index + 1)
    await _ask_next_contract_field(callback, state, lang_code)


@router.message(ContractTemplateFlow.waiting_for_field)
async def handle_contract_field(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await _show_contract_creation_menu(message, lang_code)
        return

    value = (message.text or "").strip()
    data = await state.get_data()
    contract_slug = str(data.get("contract_type") or "")
    fields = list(data.get("contract_fields") or [])
    field_index = int(data.get("field_index") or 0)
    field_data = dict(data.get("field_data") or {})
    if not contract_slug or field_index >= len(fields):
        await message.answer(get_text("error.request.invalid", lang_code))
        return

    field = fields[field_index]
    if field.get("choices"):
        await message.answer(get_text("contracts.flow.choice.required", lang_code))
        await _ask_next_contract_field(message, state, lang_code)
        return

    normalized, error = _validate_contract_value(contract_slug, field, value, lang_code, field_data)
    if error:
        await message.answer(error)
        return

    field_data[str(field.get("key") or "")] = normalized or ""
    await state.update_data(field_data=field_data, field_index=field_index + 1)
    await _ask_next_contract_field(message, state, lang_code)

@router.callback_query(F.data == "contract_generate")
async def handle_contract_generate(
    callback: CallbackQuery,
    state: FSMContext,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    data = await state.get_data()
    contract_slug = str(data.get("contract_type") or "")
    contract_title = str(data.get("contract_title") or "")
    topic = str(data.get("contract_topic") or "")
    field_data = dict(data.get("field_data") or {})
    if not contract_slug or not topic:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return

    backend_client = get_backend_client(callback.bot)
    if backend_client is None:
        await callback.message.answer(get_text("contracts.template.missing", lang_code))
        return

    try:
        documents = await backend_client.list_documents(topic)
    except Exception:
        logger.exception("Failed to fetch contract template for %s", topic)
        await callback.message.answer(get_text("contracts.template.missing", lang_code))
        return

    fallback_language = getattr(settings, "backend_default_language", None)
    document_info = backend_client.select_document(
        documents,
        preferred_language=lang_code,
        fallback_language=fallback_language,
    )
    if document_info is None:
        await callback.message.answer(get_text("contracts.template.missing", lang_code))
        return

    try:
        content, _, _ = await backend_client.download_document(document_info.id)
    except Exception:
        logger.exception("Failed to download contract template %s", topic)
        await callback.message.answer(get_text("contracts.template.missing", lang_code))
        return

    template_text = content.decode("utf-8", errors="replace").strip()
    if not template_text:
        await callback.message.answer(get_text("contracts.flow.template.empty", lang_code))
        return

    rendered = _render_contract_template(template_text, field_data, contract_slug, lang_code)
    await state.update_data(rendered_text=rendered)
    await state.set_state(ContractTemplateFlow.preview)

    contract_id = data.get("contract_id")
    if not contract_id:
        try:
            contract_id = await db.contracts.add_contract(
                user_id=callback.from_user.id,
                contract_type=contract_slug,
                template_topic=topic,
                language=document_info.language_code or lang_code,
                data=field_data,
                rendered_text=rendered,
                status="draft",
            )
            await state.update_data(contract_id=contract_id)
        except Exception:
            logger.exception("Failed to persist contract draft")

    preview_text = rendered
    if len(preview_text) > 3800:
        preview_text = get_text("contracts.flow.preview.too_long", lang_code)

    await callback.message.answer(preview_text)
    await _show_contract_actions(callback.message, lang_code, db=db, state=state)


@router.callback_query(F.data == "contract_actions")
async def handle_contract_actions(
    callback: CallbackQuery,
    state: FSMContext,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    data = await state.get_data()
    if not data.get("rendered_text"):
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    await state.set_state(ContractTemplateFlow.preview)
    await _show_contract_actions(callback.message, lang_code, db=db, state=state)


@router.callback_query(F.data == "contract_send_court")
async def handle_contract_send_court(
    callback: CallbackQuery,
    state: FSMContext,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    data = await state.get_data()
    contract_id = data.get("contract_id")
    if not contract_id:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    contract = await db.contracts.get_contract(contract_id=int(contract_id))
    if not _is_contract_fully_signed(contract):
        await callback.message.answer(get_text("contracts.flow.send_court.not_signed", lang_code))
        return
    field_data = dict(data.get("field_data") or {})
    contract_slug = str(data.get("contract_type") or "")
    contract_title = (
        str(data.get("contract_title") or "")
        or _contract_title(contract_slug, lang_code)
        or get_text("contracts.title.unknown", lang_code)
    )
    recipient_id = field_data.get("recipient_id")
    defendant_name = None
    if recipient_id:
        try:
            recipient_user = await db.users.get_user(user_id=int(recipient_id))
            if recipient_user and recipient_user.full_name:
                defendant_name = recipient_user.full_name
        except Exception:
            defendant_name = None
    if not defendant_name:
        defendant_name = _extract_contract_defendant_name(field_data)
    if not defendant_name:
        defendant_name = get_text("contracts.list.party.unknown", lang_code)
    plaintiff_name = (user_row.full_name if user_row else None) or callback.from_user.full_name
    contract_number = str(contract_id) if contract_id else "-"

    await state.clear()
    await state.set_state(CourtClaimFlow.waiting_for_claim)
    await state.update_data(
        category="contract_breach",
        plaintiff_name=plaintiff_name,
        defendant_name=defendant_name,
        contract_context={
            "contract_id": contract_id,
            "contract_number": contract_number,
            "contract_title": contract_title,
        },
    )
    await callback.message.answer(
        get_text(
            "courts.step.claim.contract",
            lang_code,
            contract_number=contract_number,
            contract_title=contract_title,
            defendant=defendant_name,
        )
    )


@router.callback_query(F.data == "contract_confirm")
async def handle_contract_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    data = await state.get_data()
    rendered_text = str(data.get("rendered_text") or "")
    contract_slug = str(data.get("contract_type") or "contract")
    contract_title = str(data.get("contract_title") or contract_slug)
    contract_id = data.get("contract_id")
    if not rendered_text:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return

    try:
        pdf_bytes = _build_contract_pdf(rendered_text, contract_title)
    except Exception:
        logger.exception("Failed to build PDF for contract confirm")
        await callback.message.answer(get_text("contracts.flow.pdf.failed", lang_code))
        return

    filename = f"{uuid.uuid4()}.pdf"
    await db.documents.add_document(
        filename=filename,
        user_id=callback.from_user.id,
        category="Contract",
        name=contract_title,
        content=pdf_bytes,
        doc_type="Contract",
        contract_id=int(contract_id) if contract_id else None,
    )
    recipient_id = None
    field_data = dict(data.get("field_data") or {})
    if contract_id:
        recipient_id = field_data.get("recipient_id")
        if recipient_id:
            await _ensure_contract_document(
                db,
                user_id=int(recipient_id),
                contract_id=int(contract_id),
                title=contract_title,
                rendered_text=rendered_text,
            )

    if contract_id:
        try:
            await db.contracts.update_contract(
                contract_id=int(contract_id),
                status="confirmed",
                rendered_text=rendered_text,
                data=field_data,
            )
        except Exception:
            logger.exception("Failed to update contract status")

    await state.clear()
    await callback.message.answer(
        get_text("contracts.flow.confirmed", lang_code),
        reply_markup=build_inline_keyboard(INLINE_MENU_BY_KEY["menu.contracts"], lang_code),
    )


@router.callback_query(F.data == "contract_edit")
async def handle_contract_edit(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    data = await state.get_data()
    contract_slug = str(data.get("contract_type") or "")
    if not contract_slug:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    await state.update_data(field_index=0, field_data={}, rendered_text="")
    await state.set_state(ContractTemplateFlow.waiting_for_field)
    await _ask_next_contract_field(callback, state, lang_code)

@router.callback_query(F.data == "contract_download_txt")
async def handle_contract_download_txt(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    data = await state.get_data()
    rendered_text = str(data.get("rendered_text") or "")
    contract_slug = str(data.get("contract_type") or "contract")
    if not rendered_text:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return

    filename = f"{contract_slug}.txt"
    buffer = BufferedInputFile(rendered_text.encode("utf-8"), filename=filename)
    await callback.message.answer_document(document=buffer)


@router.callback_query(F.data == "contract_download_pdf")
async def handle_contract_download_pdf(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    data = await state.get_data()
    rendered_text = str(data.get("rendered_text") or "")
    contract_slug = str(data.get("contract_type") or "contract")
    contract_title = str(data.get("contract_title") or contract_slug)
    if not rendered_text:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return

    try:
        pdf_bytes = _build_contract_pdf(rendered_text, contract_title)
    except Exception:
        logger.exception("Failed to build PDF")
        await callback.message.answer(get_text("contracts.flow.pdf.failed", lang_code))
        return
    buffer = BufferedInputFile(pdf_bytes, filename=f"{contract_slug}.pdf")
    await callback.message.answer_document(document=buffer, caption=contract_title)


@router.callback_query(F.data == "contract_send_other")
async def handle_contract_send_other(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    data = await state.get_data()
    if not data.get("rendered_text"):
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    await state.set_state(ContractTemplateFlow.waiting_for_recipient)
    await callback.message.answer(
        get_text("contracts.flow.send_other.prompt", lang_code),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=get_text("contracts.flow.button.back_actions", lang_code),
                        callback_data="contract_actions",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=get_text("button.cancel", lang_code),
                        callback_data="contract_cancel",
                    )
                ],
            ]
        ),
    )
    await callback.message.answer(
        get_text("contracts.flow.send_other.pick_contact", lang_code),
        reply_markup=_build_contract_recipient_keyboard(lang_code),
    )


async def _send_contract_invite(
    message: Message,
    *,
    db: DB,
    contract_id: int,
    lang_code: str,
) -> None:
    invite_code: str | None = None
    for _ in range(5):
        candidate = _generate_invite_code()
        existing = await db.contracts.get_contract_by_invite_code(invite_code=candidate)
        if existing is None:
            invite_code = candidate
            break
    if invite_code is None:
        await message.answer(get_text("contracts.flow.send_other.failed", lang_code))
        return
    await db.contracts.set_invite_code(contract_id=contract_id, invite_code=invite_code)

    username = await _resolve_bot_username(message.bot)
    if username:
        invite_link = f"https://t.me/{username}?start={invite_code}"
        await message.answer(
            get_text("contracts.invite.code", lang_code, invite_link=invite_link),
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        await message.answer(
            get_text("contracts.invite.code.only", lang_code, invite_code=invite_code),
            reply_markup=ReplyKeyboardRemove(),
        )


@router.message(ContractTemplateFlow.waiting_for_recipient, F.text)
async def handle_contract_send_other_recipient(
    message: Message,
    state: FSMContext,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.set_state(ContractTemplateFlow.preview)
        await _show_contract_actions(message, lang_code, db=db, state=state)
        return
    raw = (message.text or "").strip()
    if not raw:
        await message.answer(get_text("contracts.flow.send_other.invalid", lang_code))
        return

    recipient: str | int | None = None
    if raw.startswith("@"):
        recipient = raw
    elif raw.isdigit():
        recipient = int(raw)
    elif "t.me/" in raw:
        handle = raw.split("t.me/", 1)[-1].strip().strip("/")
        if handle:
            recipient = f"@{handle}"
    else:
        try:
            matches = await db.users.find_users_by_full_name(query=raw)
        except Exception:
            matches = []
        if len(matches) == 1:
            recipient = int(matches[0].get("user_id") or 0) or None
        elif len(matches) > 1:
            await message.answer(get_text("contracts.flow.send_other.ambiguous", lang_code))
            return
        else:
            await message.answer(get_text("contracts.flow.send_other.not_found", lang_code))
            return

    if recipient is None:
        await message.answer(get_text("contracts.flow.send_other.invalid", lang_code))
        return

    if isinstance(recipient, str) and recipient.startswith("@"):
        try:
            chat = await message.bot.get_chat(recipient)
            if getattr(chat, "type", None) == "private":
                recipient = int(getattr(chat, "id", 0) or 0) or recipient
        except Exception:
            pass

    data = await state.get_data()
    rendered_text = str(data.get("rendered_text") or "")
    contract_slug = str(data.get("contract_type") or "contract")
    contract_title = str(data.get("contract_title") or contract_slug)
    contract_id = data.get("contract_id")
    field_data = dict(data.get("field_data") or {})
    if not rendered_text:
        await message.answer(get_text("error.request.invalid", lang_code))
        return
    if not contract_id:
        contract_topic = str(data.get("contract_topic") or "")
        if not contract_topic:
            await message.answer(get_text("error.request.invalid", lang_code))
            return
        try:
            contract_id = await db.contracts.add_contract(
                user_id=message.from_user.id,
                contract_type=contract_slug,
                template_topic=contract_topic,
                language=lang_code,
                data=field_data,
                rendered_text=rendered_text,
                status="draft",
            )
            await state.update_data(contract_id=contract_id)
        except Exception:
            logger.exception("Failed to persist contract draft before send")
            await message.answer(get_text("error.request.invalid", lang_code))
            return
        if not contract_id:
            await message.answer(get_text("error.request.invalid", lang_code))
            return

    sender_name = (user_row.full_name if user_row else None) or message.from_user.full_name
    party_keyboard = (
        _build_contract_party_keyboard(int(contract_id), lang_code)
        if contract_id
        else None
    )
    try:
        if len(rendered_text) <= 3500:
            await message.bot.send_message(
                chat_id=recipient,
                text=get_text(
                    "contracts.flow.send_other.message",
                    lang_code,
                    sender=sender_name,
                )
                + "\n\n"
                + rendered_text,
                reply_markup=party_keyboard,
            )
        else:
            await message.bot.send_message(
                chat_id=recipient,
                text=get_text(
                    "contracts.flow.send_other.message",
                    lang_code,
                    sender=sender_name,
                ),
                reply_markup=party_keyboard,
            )
            buffer = BufferedInputFile(rendered_text.encode("utf-8"), filename=f"{contract_slug}.txt")
            await message.bot.send_document(
                chat_id=recipient,
                document=buffer,
                caption=contract_title,
            )
    except Exception:
        logger.exception("Failed to send contract to recipient")
        if contract_id:
            try:
                contract_data = dict(field_data)
                contract_data.update(
                    {
                        "recipient": str(recipient),
                        "recipient_id": int(recipient) if isinstance(recipient, int) else None,
                        "invite_pending": True,
                    }
                )
                await db.contracts.update_contract(
                    contract_id=int(contract_id),
                    status="sent_to_party",
                    rendered_text=rendered_text,
                    data=contract_data,
                )
            except Exception:
                logger.exception("Failed to update contract status for invite")
            await _send_contract_invite(message, db=db, contract_id=int(contract_id), lang_code=lang_code)
            await state.set_state(ContractTemplateFlow.preview)
            await _show_contract_actions(message, lang_code, db=db, state=state)
            return
        await message.answer(get_text("contracts.flow.send_other.failed", lang_code))
        await state.set_state(ContractTemplateFlow.preview)
        await _show_contract_actions(message, lang_code, db=db, state=state)
        return

    if contract_id and isinstance(recipient, int):
        await _ensure_contract_document(
            db,
            user_id=int(recipient),
            contract_id=int(contract_id),
            title=contract_title,
            rendered_text=rendered_text,
        )

    if contract_id:
        try:
            contract_data = dict(field_data)
            contract_data.update(
                {
                    "recipient": str(recipient),
                    "recipient_id": int(recipient) if isinstance(recipient, int) else None,
                }
            )
            await db.contracts.update_contract(
                contract_id=int(contract_id),
                status="sent_to_party",
                rendered_text=rendered_text,
                data=contract_data,
            )
        except Exception:
            logger.exception("Failed to update contract status to sent")

    await message.answer(
        get_text("contracts.flow.send_other.sent", lang_code, recipient=str(recipient)),
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(ContractTemplateFlow.preview)
    await _show_contract_actions(message, lang_code, db=db, state=state)


@router.message(ContractTemplateFlow.waiting_for_recipient, F.user_shared)
async def handle_contract_send_other_user_shared(
    message: Message,
    state: FSMContext,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    shared = getattr(message, "user_shared", None)
    if shared is None:
        await message.answer(get_text("contracts.flow.send_other.invalid", lang_code))
        return
    recipient_id = int(getattr(shared, "user_id", 0) or 0)
    if not recipient_id:
        await message.answer(get_text("contracts.flow.send_other.invalid", lang_code))
        return

    data = await state.get_data()
    rendered_text = str(data.get("rendered_text") or "")
    contract_slug = str(data.get("contract_type") or "contract")
    contract_title = str(data.get("contract_title") or contract_slug)
    contract_id = data.get("contract_id")
    field_data = dict(data.get("field_data") or {})
    if not rendered_text:
        await message.answer(get_text("error.request.invalid", lang_code))
        return
    if not contract_id:
        contract_topic = str(data.get("contract_topic") or "")
        if not contract_topic:
            await message.answer(get_text("error.request.invalid", lang_code))
            return
        try:
            contract_id = await db.contracts.add_contract(
                user_id=message.from_user.id,
                contract_type=contract_slug,
                template_topic=contract_topic,
                language=lang_code,
                data=field_data,
                rendered_text=rendered_text,
                status="draft",
            )
            await state.update_data(contract_id=contract_id)
        except Exception:
            logger.exception("Failed to persist contract draft before send")
            await message.answer(get_text("error.request.invalid", lang_code))
            return
        if not contract_id:
            await message.answer(get_text("error.request.invalid", lang_code))
            return

    sender_name = (user_row.full_name if user_row else None) or message.from_user.full_name
    party_keyboard = _build_contract_party_keyboard(int(contract_id), lang_code)
    try:
        if len(rendered_text) <= 3500:
            await message.bot.send_message(
                chat_id=recipient_id,
                text=get_text(
                    "contracts.flow.send_other.message",
                    lang_code,
                    sender=sender_name,
                )
                + "\n\n"
                + rendered_text,
                reply_markup=party_keyboard,
            )
        else:
            await message.bot.send_message(
                chat_id=recipient_id,
                text=get_text(
                    "contracts.flow.send_other.message",
                    lang_code,
                    sender=sender_name,
                ),
                reply_markup=party_keyboard,
            )
            buffer = BufferedInputFile(rendered_text.encode("utf-8"), filename=f"{contract_slug}.txt")
            await message.bot.send_document(
                chat_id=recipient_id,
                document=buffer,
                caption=contract_title,
            )
    except Exception:
        logger.exception("Failed to send contract to shared recipient")
        try:
            contract_data = dict(field_data)
            contract_data.update(
                {
                    "recipient": str(recipient_id),
                    "recipient_id": recipient_id,
                    "invite_pending": True,
                }
            )
            await db.contracts.update_contract(
                contract_id=int(contract_id),
                status="sent_to_party",
                rendered_text=rendered_text,
                data=contract_data,
            )
        except Exception:
            logger.exception("Failed to update contract status for invite")
        await _send_contract_invite(message, db=db, contract_id=int(contract_id), lang_code=lang_code)
        await state.set_state(ContractTemplateFlow.preview)
        await _show_contract_actions(message, lang_code, db=db, state=state)
        return

    await _ensure_contract_document(
        db,
        user_id=recipient_id,
        contract_id=int(contract_id),
        title=contract_title,
        rendered_text=rendered_text,
    )

    contract_data = dict(field_data)
    contract_data.update({"recipient": str(recipient_id), "recipient_id": recipient_id})
    try:
        await db.contracts.update_contract(
            contract_id=int(contract_id),
            status="sent_to_party",
            rendered_text=rendered_text,
            data=contract_data,
        )
    except Exception:
        logger.exception("Failed to update contract status to sent")

    await message.answer(
        get_text("contracts.flow.send_other.sent", lang_code, recipient=str(recipient_id)),
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(ContractTemplateFlow.preview)
    await _show_contract_actions(message, lang_code, db=db, state=state)


@router.callback_query(F.data.startswith("contract_party_approve:"))
async def handle_contract_party_approve(
    callback: CallbackQuery,
    db: DB,
) -> None:
    contract_id = (callback.data or "").split(":", 1)[-1].strip()
    if not contract_id.isdigit():
        await callback.answer()
        return
    contract = await db.contracts.get_contract(contract_id=int(contract_id))
    if not contract:
        await callback.answer()
        return
    data = contract.get("data") or {}
    recipient_id = data.get("recipient_id")
    if recipient_id and int(recipient_id) != callback.from_user.id:
        await callback.answer(get_text("error.request.invalid", resolve_language(callback.from_user.language_code)), show_alert=True)
        return

    data["party_status"] = "approved"
    data["party_id"] = callback.from_user.id
    await db.contracts.update_status(
        contract_id=int(contract_id),
        status="party_approved",
        data=data,
    )
    owner_id = contract.get("user_id")
    if owner_id:
        owner_lang = resolve_language(contract.get("language"))
        try:
            await callback.bot.send_message(
                chat_id=int(owner_id),
                text=get_text(
                    "contracts.flow.party.approved.notice",
                    owner_lang,
                    party=callback.from_user.full_name,
                ),
            )
        except Exception:
            logger.exception("Failed to notify contract owner about approval")
    await callback.answer(get_text("contracts.flow.party.thanks", resolve_language(callback.from_user.language_code)))


@router.callback_query(F.data.startswith("contract_party_changes:"))
async def handle_contract_party_changes(
    callback: CallbackQuery,
    state: FSMContext,
    db: DB,
) -> None:
    contract_id = (callback.data or "").split(":", 1)[-1].strip()
    if not contract_id.isdigit():
        await callback.answer()
        return
    contract = await db.contracts.get_contract(contract_id=int(contract_id))
    if not contract:
        await callback.answer()
        return
    data = contract.get("data") or {}
    recipient_id = data.get("recipient_id")
    if recipient_id and int(recipient_id) != callback.from_user.id:
        await callback.answer(get_text("error.request.invalid", resolve_language(callback.from_user.language_code)), show_alert=True)
        return
    await state.set_state(ContractAgreementFlow.waiting_for_comment)
    await state.update_data(contract_id=int(contract_id))
    await callback.answer()
    await callback.message.answer(
        get_text("contracts.flow.party.comment.prompt", resolve_language(callback.from_user.language_code))
    )


@router.callback_query(F.data.startswith("contract_party_sign:"))
async def handle_contract_party_sign(
    callback: CallbackQuery,
    db: DB,
) -> None:
    contract_id = (callback.data or "").split(":", 1)[-1].strip()
    if not contract_id.isdigit():
        await callback.answer()
        return
    contract = await db.contracts.get_contract(contract_id=int(contract_id))
    if not contract:
        await callback.answer()
        return
    data = contract.get("data") or {}
    recipient_id = data.get("recipient_id")
    if recipient_id and int(recipient_id) != callback.from_user.id:
        await callback.answer(get_text("error.request.invalid", resolve_language(callback.from_user.language_code)), show_alert=True)
        return

    data["party_status"] = "signed"
    data["party_id"] = callback.from_user.id
    await db.contracts.update_status(
        contract_id=int(contract_id),
        status="signed",
        data=data,
    )
    rendered_text = str(contract.get("rendered_text") or "")
    contract_slug = str(contract.get("type") or "contract")
    title = (
        data.get("contract_title")
        or contract.get("template_topic")
        or _contract_title(contract_slug, resolve_language(callback.from_user.language_code))
        or get_text("contracts.title.unknown", resolve_language(callback.from_user.language_code))
    )
    await _ensure_contract_document(
        db,
        user_id=callback.from_user.id,
        contract_id=int(contract_id),
        title=str(title),
        rendered_text=rendered_text,
    )
    owner_id = contract.get("user_id")
    if owner_id:
        owner_lang = resolve_language(contract.get("language"))
        try:
            await callback.bot.send_message(
                chat_id=int(owner_id),
                text=get_text("contracts.flow.party.signed.notice", owner_lang, party=callback.from_user.full_name),
            )
        except Exception:
            logger.exception("Failed to notify contract owner about signing")
    await callback.answer(get_text("contracts.flow.party.thanks", resolve_language(callback.from_user.language_code)))


@router.message(ContractAgreementFlow.waiting_for_comment)
async def handle_contract_party_comment(
    message: Message,
    state: FSMContext,
    db: DB,
) -> None:
    comment = (message.text or "").strip()
    data = await state.get_data()
    contract_id = data.get("contract_id")
    if not contract_id:
        await state.clear()
        return
    contract = await db.contracts.get_contract(contract_id=int(contract_id))
    if not contract:
        await state.clear()
        return
    contract_data = contract.get("data") or {}
    contract_data["party_status"] = "changes_requested"
    contract_data["party_id"] = message.from_user.id
    contract_data["party_comment"] = comment
    await db.contracts.update_status(
        contract_id=int(contract_id),
        status="party_changes_requested",
        data=contract_data,
    )
    owner_id = contract.get("user_id")
    if owner_id:
        owner_lang = resolve_language(contract.get("language"))
        try:
            await message.bot.send_message(
                chat_id=int(owner_id),
                text=get_text(
                    "contracts.flow.party.changes.notice",
                    owner_lang,
                    party=message.from_user.full_name,
                    comment=comment or "-",
                ),
            )
        except Exception:
            logger.exception("Failed to notify contract owner about changes request")
    await message.answer(
        get_text("contracts.flow.party.thanks", resolve_language(message.from_user.language_code))
    )
    await state.clear()


@router.callback_query(F.data == "contract_send_scholar")
async def handle_contract_send_scholar(
    callback: CallbackQuery,
    state: FSMContext,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    data = await state.get_data()
    rendered_text = str(data.get("rendered_text") or "")
    contract_slug = str(data.get("contract_type") or "contract")
    contract_title = str(data.get("contract_title") or contract_slug)
    contract_id = data.get("contract_id")
    if not rendered_text:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return

    from app.services.scholar_requests.service import (
        ScholarAttachment,
        ScholarRequestDraft,
        build_forward_text,
        build_request_payload,
        build_request_summary,
        forward_request_to_group,
        persist_request_to_documents,
    )

    pdf_bytes = b""
    try:
        pdf_bytes = _build_contract_pdf(rendered_text, contract_title)
    except Exception:
        logger.exception("Failed to build PDF for scholar request")

    attachments = [
        ScholarAttachment(
            content=rendered_text.encode("utf-8"),
            filename=f"{contract_slug}.txt",
            content_type="text/plain",
        )
    ]
    if pdf_bytes:
        attachments.append(
            ScholarAttachment(
                content=pdf_bytes,
                filename=f"{contract_slug}.pdf",
                content_type="application/pdf",
            )
        )

    request_id = uuid.uuid4().int % 100000
    draft = ScholarRequestDraft(
        request_type="docs",
        data={"ask_docs_description": contract_title, "context": "contracts"},
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
        logger.exception("Failed to persist contract scholar request")

    ok = await forward_request_to_group(
        callback.bot,
        request_id=request_id,
        user_id=callback.from_user.id,
        text=forward_text,
        attachments=attachments,
    )
    await callback.message.answer(
        get_text("contracts.flow.send_scholar.sent", lang_code)
        if ok
        else get_text("contracts.flow.send_scholar.failed", lang_code)
    )

    if contract_id:
        contract_payload = dict(data.get("field_data") or {})
        contract_payload["scholar_request_id"] = request_id
        contract_payload["scholar_sent_at"] = datetime.now(timezone.utc).isoformat()
        contract_payload["scholar_send_ok"] = bool(ok)
        contract_payload["scholar_summary"] = summary
        contract_payload["scholar_forward_text"] = forward_text
        contract_status = "sent_to_scholar" if ok else "scholar_send_failed"
        try:
            await db.contracts.update_contract(
                contract_id=int(contract_id),
                status=contract_status,
                rendered_text=rendered_text,
                data=contract_payload,
            )
        except Exception:
            logger.exception("Failed to update contract status for scholar send")
        if ok:
            await create_work_item(
                db,
                topic="contracts",
                kind="scholar_request",
                target_user_id=callback.from_user.id,
                created_by_user_id=callback.from_user.id,
                payload={
                    "contract_id": int(contract_id),
                    "contract_title": contract_title,
                    "contract_type": contract_slug,
                    "status": contract_status,
                    "request_id": request_id,
                },
            )

    await _show_contract_actions(callback.message, lang_code, db=db, state=state)


@router.callback_query(F.data == "contract_delete")
async def handle_contract_delete(
    callback: CallbackQuery,
    state: FSMContext,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    data = await state.get_data()
    contract_id = data.get("contract_id")
    if not contract_id:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    contract = await db.contracts.get_contract(contract_id=int(contract_id))
    if _is_contract_counterparty_signed(contract):
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    try:
        await db.documents.delete_by_contract_id(contract_id=int(contract_id))
        await db.contracts.delete_contract(contract_id=int(contract_id))
    except Exception:
        logger.exception("Failed to delete contract %s", contract_id)
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    await state.clear()
    await callback.message.answer(
        get_text("contracts.delete.done", lang_code),
        reply_markup=build_inline_keyboard(INLINE_MENU_BY_KEY["menu.contracts"], lang_code),
    )


@router.callback_query(F.data.startswith("contract_list_send_other:"))
async def handle_contract_list_send_other(
    callback: CallbackQuery,
    state: FSMContext,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    contract_id = (callback.data or "").split(":", 1)[-1].strip()
    await callback.answer()
    if not contract_id.isdigit():
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    contract = await db.contracts.get_contract(contract_id=int(contract_id))
    if not contract:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    if int(contract.get("user_id") or 0) != callback.from_user.id:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    rendered_text = str(contract.get("rendered_text") or "")
    if not rendered_text:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    contract_slug = str(contract.get("type") or "contract")
    contract_title = (
        str(contract.get("template_topic") or "")
        or _contract_title(contract_slug, lang_code)
        or get_text("contracts.title.unknown", lang_code)
    )
    await state.set_state(ContractTemplateFlow.waiting_for_recipient)
    await state.update_data(
        rendered_text=rendered_text,
        contract_type=contract_slug,
        contract_title=contract_title,
        contract_id=int(contract_id),
        field_data=dict(contract.get("data") or {}),
    )
    await callback.message.answer(get_text("contracts.flow.send_other.prompt", lang_code))
    await callback.message.answer(
        get_text("contracts.flow.send_other.pick_contact", lang_code),
        reply_markup=_build_contract_recipient_keyboard(lang_code),
    )


@router.callback_query(F.data.startswith("contract_list_send_scholar:"))
async def handle_contract_list_send_scholar(
    callback: CallbackQuery,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    contract_id = (callback.data or "").split(":", 1)[-1].strip()
    await callback.answer()
    if not contract_id.isdigit():
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    contract = await db.contracts.get_contract(contract_id=int(contract_id))
    if not contract:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    rendered_text = str(contract.get("rendered_text") or "")
    if not rendered_text:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return

    contract_slug = str(contract.get("type") or "contract")
    contract_title = (
        str(contract.get("template_topic") or "")
        or _contract_title(contract_slug, lang_code)
        or get_text("contracts.title.unknown", lang_code)
    )

    from app.services.scholar_requests.service import (
        ScholarAttachment,
        ScholarRequestDraft,
        build_forward_text,
        build_request_payload,
        build_request_summary,
        forward_request_to_group,
        persist_request_to_documents,
    )

    pdf_bytes = b""
    try:
        pdf_bytes = _build_contract_pdf(rendered_text, contract_title)
    except Exception:
        logger.exception("Failed to build PDF for scholar request")

    attachments = [
        ScholarAttachment(
            content=rendered_text.encode("utf-8"),
            filename=f"{contract_slug}.txt",
            content_type="text/plain",
        )
    ]
    if pdf_bytes:
        attachments.append(
            ScholarAttachment(
                content=pdf_bytes,
                filename=f"{contract_slug}.pdf",
                content_type="application/pdf",
            )
        )

    request_id = uuid.uuid4().int % 100000
    draft = ScholarRequestDraft(
        request_type="docs",
        data={"ask_docs_description": contract_title, "context": "contracts"},
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
        logger.exception("Failed to persist contract scholar request")

    ok = await forward_request_to_group(
        callback.bot,
        request_id=request_id,
        user_id=callback.from_user.id,
        text=forward_text,
        attachments=attachments,
    )
    await callback.message.answer(
        get_text("contracts.flow.send_scholar.sent", lang_code)
        if ok
        else get_text("contracts.flow.send_scholar.failed", lang_code)
    )

    contract_payload = dict(contract.get("data") or {})
    contract_payload["scholar_request_id"] = request_id
    contract_payload["scholar_sent_at"] = datetime.now(timezone.utc).isoformat()
    contract_payload["scholar_send_ok"] = bool(ok)
    contract_payload["scholar_summary"] = summary
    contract_payload["scholar_forward_text"] = forward_text
    contract_status = "sent_to_scholar" if ok else "scholar_send_failed"
    try:
        await db.contracts.update_contract(
            contract_id=int(contract_id),
            status=contract_status,
            rendered_text=rendered_text,
            data=contract_payload,
        )
    except Exception:
        logger.exception("Failed to update contract status for scholar send")
    if ok:
        await create_work_item(
            db,
            topic="contracts",
            kind="scholar_request",
            target_user_id=callback.from_user.id,
            created_by_user_id=callback.from_user.id,
            payload={
                "contract_id": int(contract_id),
                "contract_title": contract_title,
                "contract_type": contract_slug,
                "status": contract_status,
                "request_id": request_id,
            },
        )


@router.callback_query(F.data.startswith("contract_list_edit:"))
async def handle_contract_list_edit(
    callback: CallbackQuery,
    state: FSMContext,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    contract_id = (callback.data or "").split(":", 1)[-1].strip()
    await callback.answer()
    if not contract_id.isdigit():
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    contract = await db.contracts.get_contract(contract_id=int(contract_id))
    if not contract:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    contract_slug = str(contract.get("type") or "contract")
    definition = CONTRACT_FLOW_DEFINITIONS.get(contract_slug)
    if not definition:
        await callback.message.answer(get_text("error.request.invalid", lang_code))
        return
    rendered_text = str(contract.get("rendered_text") or "")
    await state.set_state(ContractTemplateFlow.preview)
    await state.update_data(
        contract_type=contract_slug,
        contract_title=(
            (contract.get("data") or {}).get("contract_title")
            or _contract_title(contract_slug, lang_code)
        ),
        contract_topic=str(definition.get("topic") or ""),
        contract_fields=definition.get("fields") or [],
        field_index=0,
        field_data=dict(contract.get("data") or {}),
        rendered_text=rendered_text,
        contract_id=int(contract_id),
    )
    await _show_contract_actions(callback.message, lang_code, db=db, state=state)


@router.callback_query(F.data == "contract_cancel")
async def handle_contract_cancel(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await state.clear()
    await callback.message.answer(
        get_text("menu.contracts.title", lang_code),
        reply_markup=build_inline_keyboard(INLINE_MENU_BY_KEY["menu.contracts"], lang_code),
    )

@router.callback_query(F.data == "all_contracts")
async def handle_all_contracts(
    callback: CallbackQuery,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    contracts = await db.contracts.get_contracts_for_user(user_id=callback.from_user.id)
    documents = await db.documents.get_user_documents_by_type(
        user_id=callback.from_user.id, doc_type="Contract"
    )
    if not documents:
        await callback.message.answer(get_text("contracts.none", lang_code))
        await callback.message.answer(
            get_text("contracts.sent", lang_code),
            reply_markup=build_inline_keyboard(INLINE_MENU_BY_KEY["menu.contracts"], lang_code),
        )
        return

    await callback.message.answer(get_text("contracts.list.title", lang_code))
    contract_index: dict[str, dict[str, object]] = {}
    contract_id_index: dict[int, dict[str, object]] = {}
    counterparty_name_cache: dict[int, str | None] = {}
    for contract in contracts:
        data = contract.get("data") or {}
        contract_slug = str(contract.get("type") or "contract")
        title = (
            data.get("contract_title")
            or contract.get("template_topic")
            or _contract_title(contract_slug, lang_code)
            or get_text("contracts.title.unknown", lang_code)
        )
        if title:
            contract_index[title.strip().lower()] = contract
        contract_id_value = contract.get("id")
        if isinstance(contract_id_value, int):
            contract_id_index[contract_id_value] = contract

    for doc in documents:
        content = doc.get("content")
        name = (doc.get("name") or "").strip()
        if not content:
            continue
        contract = None
        doc_contract_id = doc.get("contract_id")
        if isinstance(doc_contract_id, int):
            contract = contract_id_index.get(doc_contract_id)
        if contract is None and name:
            contract = contract_index.get(name.lower())
        if contract:
            data = contract.get("data") or {}
            status_text = _format_contract_status(contract.get("status"), lang_code)
            created_at = _format_contract_date(contract.get("created_at"))
            party = (
                data.get("recipient_name")
                or _extract_contract_defendant_name(data)
            )
            if not party:
                recipient_id = _extract_contract_recipient_id(data)
                if recipient_id:
                    if recipient_id not in counterparty_name_cache:
                        try:
                            recipient_user = await db.users.get_user(user_id=recipient_id)
                            full_name = (
                                (recipient_user.full_name or "").strip() if recipient_user else ""
                            )
                            counterparty_name_cache[recipient_id] = full_name or None
                        except Exception:
                            counterparty_name_cache[recipient_id] = None
                    party = counterparty_name_cache.get(recipient_id)
            if not party:
                party = data.get("recipient")
            if not party:
                party = get_text("contracts.list.party.unknown", lang_code)
            caption = get_text(
                "contracts.list.item",
                lang_code,
                title=name or get_text("contracts.title.unknown", lang_code),
                status=status_text,
                date=created_at,
                party=party,
            )
            can_edit = int(contract.get("user_id") or 0) == callback.from_user.id
            reply_markup = _build_contract_edit_keyboard(
                int(contract.get("id") or 0),
                lang_code,
                can_edit=can_edit,
            )
        else:
            caption = get_text(
                "contracts.list.item",
                lang_code,
                title=name or get_text("contracts.title.unknown", lang_code),
                status=get_text("contracts.status.draft", lang_code),
                date="-",
                party=get_text("contracts.list.party.unknown", lang_code),
            )
            reply_markup = None
        try:
            buffer = BufferedInputFile(bytes(content), filename=f"{name or 'contract'}.pdf")
            await callback.message.answer_document(
                document=buffer,
                caption=caption,
                reply_markup=reply_markup,
            )
        except Exception:
            logger.exception("Failed to send document '%s'", name)
            await callback.message.answer(get_text("error.document.send", lang_code, name=name))
    await callback.message.answer(
        get_text("contracts.sent", lang_code),
        reply_markup=build_inline_keyboard(INLINE_MENU_BY_KEY["menu.contracts"], lang_code),
    )


@router.callback_query(F.data == "find_contract")
async def handle_find_contract(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await state.set_state(ContractSearch.waiting_for_search_query)
    await callback.message.edit_text(
        get_text("contracts.search.prompt", lang_code),
        reply_markup=build_inline_keyboard(
            InlineMenu(
                key="menu.contracts.search",
                title_key="contracts.search.prompt",
                buttons=[
                    [InlineButton(key="button.contracts.all", callback="all_contracts")],
                    [InlineButton(key="button.back", callback="back_to_contracts")],
                ],
            ),
            lang_code,
        ),
    )


@router.message(ContractSearch.waiting_for_search_query)
async def handle_contract_search_query(
    message: Message,
    state: FSMContext,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    query = (message.text or "").strip()
    if not query:
        await message.answer(get_text("error.contracts.search.empty", lang_code))
        return

    documents = await db.documents.get_user_documents_by_type(
        user_id=message.from_user.id,
        doc_type="Contract",
    )
    filtered = [doc for doc in documents if query.lower() in (doc.get("name", "") or "").lower()]

    if not filtered:
        await message.answer(get_text("contracts.search.none", lang_code, query=query))
    else:
        await message.answer(get_text("contracts.search.found", lang_code, count=len(filtered)))
        await send_documents(
            message,
            filtered,
            lang_code=lang_code,
            empty_text=get_text("contracts.none", lang_code),
        )

    await state.clear()
    await message.answer(
        get_text("menu.contracts.title", lang_code),
        reply_markup=build_inline_keyboard(INLINE_MENU_BY_KEY["menu.contracts"], lang_code),
    )


@router.callback_query(F.data == "create_contract")
async def handle_create_contract(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await state.clear()
    await _show_contract_creation_menu(callback.message, lang_code)


@router.callback_query(F.data == "contract_create_menu")
async def handle_contract_create_menu(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await state.clear()
    await _show_contract_creation_menu(callback.message, lang_code)


@router.callback_query(F.data == "contract_upload")
async def handle_contract_upload(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await state.set_state(ContractCreation.waiting_for_name)
    await edit_or_send_callback(
        callback,
        get_text("contracts.title.prompt", lang_code),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=get_text("button.back", lang_code),
                        callback_data="create_contract",
                    )
                ]
            ]
        ),
    )


@router.message(ContractCreation.waiting_for_name)
async def handle_contract_name(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    contract_name = (message.text or "").strip()
    if not contract_name:
        await message.answer(get_text("error.contracts.name.empty", lang_code))
        return
    if len(contract_name) > 100:
        await message.answer(get_text("error.contracts.name.too_long", lang_code))
        return

    await state.update_data(contract_name=contract_name)
    await state.set_state(ContractCreation.waiting_for_file)
    await message.answer(get_text("contracts.upload.prompt", lang_code, name=contract_name))


@router.message(ContractCreation.waiting_for_file)
async def handle_contract_file(
    message: Message,
    state: FSMContext,
    db: DB,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if not message.document:
        await message.answer(get_text("error.contracts.file.required_pdf", lang_code))
        return
    if message.document.mime_type != "application/pdf":
        await message.answer(get_text("error.contracts.file.only_pdf", lang_code))
        return
    if message.document.file_size and message.document.file_size > 50 * 1024 * 1024:
        await message.answer(get_text("error.contracts.file.too_large", lang_code))
        return

    data = await state.get_data()
    contract_name: Optional[str] = data.get("contract_name")
    if not contract_name:
        await message.answer(get_text("error.contracts.name.missing_state", lang_code))
        await state.clear()
        return

    file_info = await message.bot.get_file(message.document.file_id)
    file_stream = await message.bot.download_file(file_info.file_path)
    content = file_stream.read() if file_stream else b""

    filename = f"{uuid.uuid4()}.pdf"
    await db.documents.add_document(
        filename=filename,
        user_id=message.from_user.id,
        category="Contract",
        name=contract_name,
        content=content,
        doc_type="Contract",
        contract_id=None,
    )

    await state.clear()
    await message.answer(
        get_text("contracts.saved", lang_code, name=contract_name),
        reply_markup=build_inline_keyboard(INLINE_MENU_BY_KEY["menu.contracts"], lang_code),
    )


@router.callback_query(F.data == "contracts_stats")
async def handle_contracts_stats(
    callback: CallbackQuery,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await callback.message.edit_text(
        get_text("contracts.stats.info", lang_code),
        reply_markup=build_inline_keyboard(
            InlineMenu(
                key="menu.contracts.stats",
                title_key="contracts.stats.info",
                buttons=[[InlineButton(key="button.back", callback="back_to_contracts")]],
            ),
            lang_code,
        ),
    )


@router.callback_query(F.data == "back_to_contracts")
async def handle_back_to_contracts(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    await state.clear()
    lang_code = user_language(user_row, callback.from_user)
    await callback.answer()
    await callback.message.edit_text(
        get_text("menu.contracts.title", lang_code),
        reply_markup=build_inline_keyboard(INLINE_MENU_BY_KEY["menu.contracts"], lang_code),
    )

