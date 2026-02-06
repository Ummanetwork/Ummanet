from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot.states.comitee import (
    ExecutionReportFlow,
    ExecutionReviewFlow,
    ProposalCreateFlow,
    ProposalReviewFlow,
)
from app.infrastructure.database.db import DB
from app.infrastructure.database.models.user import UserModel
from app.infrastructure.database.tables.meetings import MeetingsTable
from app.services.i18n.localization import get_text, resolve_language
from config.config import settings

from .comitee_common import is_cancel_command, user_language

logger = logging.getLogger(__name__)

router = Router(name="comitee.meetings")

PROPOSAL_BASIS_HAS = "has_basis"
PROPOSAL_BASIS_NO = "no_conflict"
VOTE_TYPES = {"for", "against", "abstain"}


def _optional_input_value(text: Optional[str]) -> Optional[str]:
    cleaned = (text or "").strip()
    if not cleaned:
        return None
    lowered = cleaned.lower()
    if lowered in {"-", "skip", "no"}:
        return None
    return cleaned


def _format_datetime(value: Optional[datetime]) -> str:
    if not value:
        return "-"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _shorten(text: str, limit: int = 200) -> str:
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 3)].rstrip()}..."


def _voting_days() -> int:
    for attr in ("MEETINGS_VOTING_DAYS", "meetings_voting_days"):
        try:
            value = getattr(settings.bot, attr)
        except AttributeError:
            value = getattr(settings, attr, None)
        if value is None:
            continue
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            continue
    return 7


async def _is_admin(user_id: int, db: DB) -> bool:
    try:
        return await db.meetings.is_admin(user_id=user_id)
    except Exception:
        logger.exception("Failed to check admin status for %s", user_id)
        return False


def _proposal_summary(payload: dict[str, object], lang_code: str) -> str:
    empty = get_text("meetings.field.empty", lang_code)
    shariah_basis = payload.get("shariah_basis")
    if shariah_basis == PROPOSAL_BASIS_HAS:
        shariah_text = payload.get("shariah_text") or empty
    else:
        shariah_text = get_text("meetings.field.shariah.no_conflict", lang_code)
    conditions = payload.get("conditions") or empty
    terms = payload.get("terms") or empty
    return get_text(
        "meetings.idea.summary",
        lang_code,
        title=payload.get("title") or empty,
        description=payload.get("description") or empty,
        goal=payload.get("goal") or empty,
        shariah=shariah_text,
        conditions=conditions,
        terms=terms,
    )


def _admin_proposal_card(proposal: dict[str, object], lang_code: str) -> str:
    empty = get_text("meetings.field.empty", lang_code)
    basis = proposal.get("shariah_basis")
    if basis == PROPOSAL_BASIS_HAS:
        shariah_text = proposal.get("shariah_text") or empty
    else:
        shariah_text = get_text("meetings.field.shariah.no_conflict", lang_code)
    created_at = proposal.get("created_at")
    created_str = _format_datetime(created_at if isinstance(created_at, datetime) else None)
    return get_text(
        "meetings.admin.card",
        lang_code,
        proposal_id=proposal.get("id"),
        title=proposal.get("title") or empty,
        author_id=proposal.get("author_id") or "-",
        created_at=created_str,
        description=proposal.get("description") or empty,
        goal=proposal.get("goal") or empty,
        shariah=shariah_text,
        conditions=proposal.get("conditions") or empty,
        terms=proposal.get("terms") or empty,
    )


def _vote_card(proposal: dict[str, object], lang_code: str) -> str:
    empty = get_text("meetings.field.empty", lang_code)
    basis = proposal.get("shariah_basis")
    if basis == PROPOSAL_BASIS_HAS:
        shariah_text = proposal.get("shariah_text") or empty
    else:
        shariah_text = get_text("meetings.field.shariah.no_conflict", lang_code)
    description = _shorten(str(proposal.get("description") or empty))
    ends_at = proposal.get("voting_ends_at")
    ends_str = _format_datetime(ends_at if isinstance(ends_at, datetime) else None)
    return get_text(
        "meetings.vote.card",
        lang_code,
        proposal_id=proposal.get("id"),
        title=proposal.get("title") or empty,
        description=description,
        shariah=shariah_text,
        conditions=proposal.get("conditions") or empty,
        ends_at=ends_str,
    )


def _execution_card(execution: dict[str, object], lang_code: str) -> str:
    empty = get_text("meetings.field.empty", lang_code)
    status_key = f"meetings.execution.status.{execution.get('status')}"
    status_text = get_text(status_key, lang_code)
    deadline = execution.get("deadline")
    deadline_str = _format_datetime(deadline if isinstance(deadline, datetime) else None)
    comment = execution.get("comment") or empty
    proof = execution.get("proof")
    proof_text = empty
    if proof:
        try:
            data = json.loads(proof)
            link = data.get("link")
            filename = data.get("filename")
            if link:
                proof_text = link
            elif filename:
                proof_text = filename
            else:
                proof_text = get_text("meetings.execution.proof.file", lang_code)
        except Exception:
            proof_text = str(proof)
    return get_text(
        "meetings.execution.card",
        lang_code,
        execution_id=execution.get("id"),
        proposal_id=execution.get("proposal_id"),
        title=execution.get("title") or empty,
        responsible_id=execution.get("responsible_id") or empty,
        deadline=deadline_str,
        status=status_text,
        comment=comment,
        proof=proof_text,
        rejected_reason=execution.get("rejected_reason") or empty,
    )


def _proposal_confirm_keyboard(lang_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("meetings.idea.submit", lang_code),
                    callback_data="meetings:submit",
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("meetings.idea.cancel", lang_code),
                    callback_data="meetings:cancel",
                )
            ],
        ]
    )


def _shariah_basis_keyboard(lang_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("meetings.idea.basis.has", lang_code),
                    callback_data="meetings:basis:has",
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("meetings.idea.basis.no", lang_code),
                    callback_data="meetings:basis:no",
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("meetings.idea.cancel", lang_code),
                    callback_data="meetings:cancel",
                )
            ],
        ]
    )


def _admin_actions_keyboard(lang_code: str, proposal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("meetings.admin.approve", lang_code),
                    callback_data=f"meetings:approve:{proposal_id}",
                ),
                InlineKeyboardButton(
                    text=get_text("meetings.admin.revise", lang_code),
                    callback_data=f"meetings:revise:{proposal_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=get_text("meetings.admin.reject", lang_code),
                    callback_data=f"meetings:reject:{proposal_id}",
                )
            ],
        ]
    )


def _vote_keyboard(lang_code: str, proposal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("meetings.vote.for", lang_code),
                    callback_data=f"meetings:vote:{proposal_id}:for",
                ),
                InlineKeyboardButton(
                    text=get_text("meetings.vote.against", lang_code),
                    callback_data=f"meetings:vote:{proposal_id}:against",
                ),
                InlineKeyboardButton(
                    text=get_text("meetings.vote.abstain", lang_code),
                    callback_data=f"meetings:vote:{proposal_id}:abstain",
                ),
            ]
        ]
    )


def _execution_actions_keyboard(
    lang_code: str,
    *,
    execution_id: int,
    can_report: bool,
    can_review: bool,
    is_closed: bool,
) -> Optional[InlineKeyboardMarkup]:
    rows = []
    if can_report and not is_closed:
        rows.append(
            [
                InlineKeyboardButton(
                    text=get_text("meetings.execution.report", lang_code),
                    callback_data=f"exec:report:{execution_id}",
                )
            ]
        )
    if can_review and not is_closed:
        rows.append(
            [
                InlineKeyboardButton(
                    text=get_text("meetings.execution.confirm", lang_code),
                    callback_data=f"exec:confirm:{execution_id}",
                ),
                InlineKeyboardButton(
                    text=get_text("meetings.execution.reject", lang_code),
                    callback_data=f"exec:reject:{execution_id}",
                ),
            ]
        )
    if not rows:
        return None
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "meetings:idea")
async def handle_meetings_idea(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    await state.clear()
    await state.set_state(ProposalCreateFlow.waiting_for_title)
    await state.update_data(payload={})
    await callback.message.answer(get_text("meetings.idea.prompt.title", lang_code))


@router.message(ProposalCreateFlow.waiting_for_title)
async def handle_proposal_title(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("meetings.idea.cancelled", lang_code))
        return
    title = _optional_input_value(message.text)
    if not title:
        await message.answer(get_text("meetings.idea.error.title", lang_code))
        return
    data = await state.get_data()
    payload = dict(data.get("payload") or {})
    payload["title"] = title
    await state.update_data(payload=payload)
    await state.set_state(ProposalCreateFlow.waiting_for_description)
    await message.answer(get_text("meetings.idea.prompt.description", lang_code))


@router.message(ProposalCreateFlow.waiting_for_description)
async def handle_proposal_description(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("meetings.idea.cancelled", lang_code))
        return
    description = _optional_input_value(message.text)
    if not description:
        await message.answer(get_text("meetings.idea.error.description", lang_code))
        return
    data = await state.get_data()
    payload = dict(data.get("payload") or {})
    payload["description"] = description
    await state.update_data(payload=payload)
    await state.set_state(ProposalCreateFlow.waiting_for_goal)
    await message.answer(get_text("meetings.idea.prompt.goal", lang_code))


@router.message(ProposalCreateFlow.waiting_for_goal)
async def handle_proposal_goal(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("meetings.idea.cancelled", lang_code))
        return
    goal = _optional_input_value(message.text)
    if not goal:
        await message.answer(get_text("meetings.idea.error.goal", lang_code))
        return
    data = await state.get_data()
    payload = dict(data.get("payload") or {})
    payload["goal"] = goal
    await state.update_data(payload=payload)
    await state.set_state(ProposalCreateFlow.waiting_for_shariah_basis)
    await message.answer(
        get_text("meetings.idea.prompt.shariah_basis", lang_code),
        reply_markup=_shariah_basis_keyboard(lang_code),
    )


@router.callback_query(F.data.startswith("meetings:basis:"))
async def handle_proposal_shariah_basis(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    basis = (callback.data or "").split(":", 2)[-1]
    data = await state.get_data()
    payload = dict(data.get("payload") or {})
    if basis == "has":
        payload["shariah_basis"] = PROPOSAL_BASIS_HAS
        await state.update_data(payload=payload)
        await state.set_state(ProposalCreateFlow.waiting_for_shariah_text)
        await callback.message.answer(get_text("meetings.idea.prompt.shariah_text", lang_code))
    else:
        payload["shariah_basis"] = PROPOSAL_BASIS_NO
        await state.update_data(payload=payload)
        await state.set_state(ProposalCreateFlow.waiting_for_conditions)
        await callback.message.answer(get_text("meetings.idea.prompt.conditions", lang_code))


@router.message(ProposalCreateFlow.waiting_for_shariah_text)
async def handle_proposal_shariah_text(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("meetings.idea.cancelled", lang_code))
        return
    shariah_text = _optional_input_value(message.text)
    if not shariah_text:
        await message.answer(get_text("meetings.idea.error.shariah_text", lang_code))
        return
    data = await state.get_data()
    payload = dict(data.get("payload") or {})
    payload["shariah_text"] = shariah_text
    await state.update_data(payload=payload)
    await state.set_state(ProposalCreateFlow.waiting_for_conditions)
    await message.answer(get_text("meetings.idea.prompt.conditions", lang_code))


@router.message(ProposalCreateFlow.waiting_for_conditions)
async def handle_proposal_conditions(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("meetings.idea.cancelled", lang_code))
        return
    conditions = _optional_input_value(message.text)
    data = await state.get_data()
    payload = dict(data.get("payload") or {})
    payload["conditions"] = conditions
    await state.update_data(payload=payload)
    await state.set_state(ProposalCreateFlow.waiting_for_terms)
    await message.answer(get_text("meetings.idea.prompt.terms", lang_code))


@router.message(ProposalCreateFlow.waiting_for_terms)
async def handle_proposal_terms(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("meetings.idea.cancelled", lang_code))
        return
    terms = _optional_input_value(message.text)
    data = await state.get_data()
    payload = dict(data.get("payload") or {})
    payload["terms"] = terms
    await state.update_data(payload=payload)
    await state.set_state(ProposalCreateFlow.waiting_for_confirm)
    await message.answer(
        _proposal_summary(payload, lang_code),
        reply_markup=_proposal_confirm_keyboard(lang_code),
    )


@router.callback_query(F.data == "meetings:submit")
async def handle_proposal_submit(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    data = await state.get_data()
    payload = dict(data.get("payload") or {})
    title = payload.get("title")
    description = payload.get("description")
    goal = payload.get("goal")
    shariah_basis = payload.get("shariah_basis")
    if not (title and description and goal and shariah_basis):
        await callback.message.answer(get_text("meetings.idea.error.generic", lang_code))
        return
    try:
        proposal_id = await db.meetings.create_proposal(
            author_id=callback.from_user.id,
            title=str(title),
            description=str(description),
            goal=str(goal),
            shariah_basis=str(shariah_basis),
            shariah_text=payload.get("shariah_text"),
            conditions=payload.get("conditions"),
            terms=payload.get("terms"),
        )
    except Exception:
        logger.exception("Failed to create proposal")
        await callback.message.answer(get_text("meetings.idea.error.generic", lang_code))
        return
    if not proposal_id:
        await callback.message.answer(get_text("meetings.idea.error.generic", lang_code))
        return
    await state.clear()
    logger.info("Proposal created: %s by %s", proposal_id, callback.from_user.id)
    await callback.message.answer(get_text("meetings.idea.submitted", lang_code))


@router.callback_query(F.data == "meetings:cancel")
async def handle_proposal_cancel(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    await state.clear()
    await callback.message.answer(get_text("meetings.idea.cancelled", lang_code))


@router.callback_query(F.data == "meetings:admin")
async def handle_meetings_admin(
    callback: CallbackQuery,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    if not await _is_admin(callback.from_user.id, db):
        await callback.message.answer(get_text("meetings.admin.denied", lang_code))
        return
    proposals = await db.meetings.list_pending_proposals()
    if not proposals:
        await callback.message.answer(get_text("meetings.admin.none", lang_code))
        return
    for proposal in proposals:
        text = _admin_proposal_card(proposal, lang_code)
        keyboard = _admin_actions_keyboard(lang_code, int(proposal.get("id") or 0))
        await callback.message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("meetings:approve:"))
async def handle_proposal_approve(
    callback: CallbackQuery,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    if not await _is_admin(callback.from_user.id, db):
        await callback.message.answer(get_text("meetings.admin.denied", lang_code))
        return
    try:
        proposal_id = int((callback.data or "").split(":")[-1])
    except ValueError:
        await callback.message.answer(get_text("meetings.admin.error", lang_code))
        return
    ends_at = datetime.now(timezone.utc) + timedelta(days=_voting_days())
    await db.meetings.start_voting(
        proposal_id=proposal_id,
        reviewed_by=callback.from_user.id,
        ends_at=ends_at,
    )
    logger.info("Proposal %s approved by %s", proposal_id, callback.from_user.id)
    await callback.message.answer(get_text("meetings.admin.approved", lang_code))


@router.callback_query(F.data.startswith("meetings:revise:"))
async def handle_proposal_revise(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    if not await _is_admin(callback.from_user.id, db):
        await callback.message.answer(get_text("meetings.admin.denied", lang_code))
        return
    try:
        proposal_id = int((callback.data or "").split(":")[-1])
    except ValueError:
        await callback.message.answer(get_text("meetings.admin.error", lang_code))
        return
    await state.clear()
    await state.set_state(ProposalReviewFlow.waiting_for_revision_comment)
    await state.update_data(review_action="revision", proposal_id=proposal_id)
    await callback.message.answer(get_text("meetings.admin.revision.prompt", lang_code))


@router.callback_query(F.data.startswith("meetings:reject:"))
async def handle_proposal_reject(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    if not await _is_admin(callback.from_user.id, db):
        await callback.message.answer(get_text("meetings.admin.denied", lang_code))
        return
    try:
        proposal_id = int((callback.data or "").split(":")[-1])
    except ValueError:
        await callback.message.answer(get_text("meetings.admin.error", lang_code))
        return
    await state.clear()
    await state.set_state(ProposalReviewFlow.waiting_for_rejection_reason)
    await state.update_data(review_action="reject", proposal_id=proposal_id)
    await callback.message.answer(get_text("meetings.admin.reject.prompt", lang_code))


@router.message(ProposalReviewFlow.waiting_for_revision_comment)
async def handle_revision_comment(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("meetings.idea.cancelled", lang_code))
        return
    comment = _optional_input_value(message.text)
    if not comment:
        await message.answer(get_text("meetings.admin.revision.error", lang_code))
        return
    data = await state.get_data()
    proposal_id = int(data.get("proposal_id") or 0)
    await db.meetings.update_proposal_status(
        proposal_id=proposal_id,
        status="revision_required",
        reviewed_by=message.from_user.id,
        admin_comment=comment,
        admin_reason=None,
    )
    proposal = await db.meetings.get_proposal(proposal_id=proposal_id)
    await state.clear()
    if proposal:
        author_id = int(proposal.get("author_id") or 0)
        if author_id:
            try:
                author_row = await db.users.get_user(user_id=author_id)
                author_lang = resolve_language(getattr(author_row, "language_code", None))
                await message.bot.send_message(
                    chat_id=author_id,
                    text=get_text(
                        "meetings.admin.notify.revision",
                        author_lang,
                        comment=comment,
                    ),
                )
            except Exception:
                logger.exception("Failed to notify author %s about revision", author_id)
    logger.info("Proposal %s revision requested by %s", proposal_id, message.from_user.id)
    await message.answer(get_text("meetings.admin.revision.sent", lang_code))


@router.message(ProposalReviewFlow.waiting_for_rejection_reason)
async def handle_reject_reason(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("meetings.idea.cancelled", lang_code))
        return
    reason = _optional_input_value(message.text)
    if not reason:
        await message.answer(get_text("meetings.admin.reject.error", lang_code))
        return
    data = await state.get_data()
    proposal_id = int(data.get("proposal_id") or 0)
    await db.meetings.update_proposal_status(
        proposal_id=proposal_id,
        status="rejected",
        reviewed_by=message.from_user.id,
        admin_comment=None,
        admin_reason=reason,
    )
    proposal = await db.meetings.get_proposal(proposal_id=proposal_id)
    await state.clear()
    if proposal:
        author_id = int(proposal.get("author_id") or 0)
        if author_id:
            try:
                author_row = await db.users.get_user(user_id=author_id)
                author_lang = resolve_language(getattr(author_row, "language_code", None))
                await message.bot.send_message(
                    chat_id=author_id,
                    text=get_text(
                        "meetings.admin.notify.rejected",
                        author_lang,
                        reason=reason,
                    ),
                )
            except Exception:
                logger.exception("Failed to notify author %s about rejection", author_id)
    logger.info("Proposal %s rejected by %s", proposal_id, message.from_user.id)
    await message.answer(get_text("meetings.admin.rejected", lang_code))


@router.callback_query(F.data == "meetings:vote")
async def handle_meetings_vote(
    callback: CallbackQuery,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    proposals = await db.meetings.list_active_votings()
    if not proposals:
        await callback.message.answer(get_text("meetings.vote.none", lang_code))
        return
    for proposal in proposals:
        text = _vote_card(proposal, lang_code)
        keyboard = _vote_keyboard(lang_code, int(proposal.get("id") or 0))
        await callback.message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("meetings:vote:"))
async def handle_vote_submit(
    callback: CallbackQuery,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    parts = (callback.data or "").split(":")
    if len(parts) < 4:
        await callback.message.answer(get_text("meetings.vote.invalid", lang_code))
        return
    try:
        proposal_id = int(parts[2])
    except ValueError:
        await callback.message.answer(get_text("meetings.vote.invalid", lang_code))
        return
    vote_type = parts[3]
    if vote_type not in VOTE_TYPES:
        await callback.message.answer(get_text("meetings.vote.invalid", lang_code))
        return
    proposal = await db.meetings.get_proposal(proposal_id=proposal_id)
    if not proposal:
        await callback.message.answer(get_text("meetings.vote.invalid", lang_code))
        return
    status = str(proposal.get("status") or "")
    if status not in {"approved", "voting_active"}:
        await callback.message.answer(get_text("meetings.vote.invalid", lang_code))
        return
    ends_at = proposal.get("voting_ends_at")
    if isinstance(ends_at, datetime) and ends_at <= datetime.now(timezone.utc):
        await callback.message.answer(get_text("meetings.vote.closed", lang_code))
        return
    inserted = await db.meetings.add_vote(
        proposal_id=proposal_id,
        user_id=callback.from_user.id,
        vote_type=vote_type,
    )
    if not inserted:
        await callback.message.answer(get_text("meetings.vote.already", lang_code))
        return
    logger.info(
        "Vote submitted: proposal=%s user=%s type=%s",
        proposal_id,
        callback.from_user.id,
        vote_type,
    )
    await callback.message.answer(get_text("meetings.vote.saved", lang_code))


@router.callback_query(F.data == "enforcement_open")
async def handle_enforcement_open(
    callback: CallbackQuery,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    executions = await db.meetings.list_executions()
    if not executions:
        await callback.message.answer(get_text("meetings.execution.none", lang_code))
        return
    is_admin = await _is_admin(callback.from_user.id, db)
    for execution in executions:
        status = str(execution.get("status") or "")
        is_closed = status in {"completed", "failed"}
        responsible_id = execution.get("responsible_id")
        can_report = bool(responsible_id) and int(responsible_id) == callback.from_user.id
        keyboard = _execution_actions_keyboard(
            lang_code,
            execution_id=int(execution.get("id") or 0),
            can_report=can_report,
            can_review=is_admin,
            is_closed=is_closed,
        )
        await callback.message.answer(
            _execution_card(execution, lang_code),
            reply_markup=keyboard,
        )


@router.callback_query(F.data.startswith("exec:report:"))
async def handle_execution_report_start(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    try:
        execution_id = int((callback.data or "").split(":")[-1])
    except ValueError:
        await callback.message.answer(get_text("meetings.execution.error", lang_code))
        return
    execution = await db.meetings.get_execution(execution_id=execution_id)
    if not execution:
        await callback.message.answer(get_text("meetings.execution.error", lang_code))
        return
    responsible_id = execution.get("responsible_id")
    is_admin = await _is_admin(callback.from_user.id, db)
    if not (is_admin or (responsible_id and int(responsible_id) == callback.from_user.id)):
        await callback.message.answer(get_text("meetings.admin.denied", lang_code))
        return
    await state.clear()
    await state.set_state(ExecutionReportFlow.waiting_for_comment)
    await state.update_data(execution_id=execution_id)
    await callback.message.answer(get_text("meetings.execution.report.prompt", lang_code))


@router.message(ExecutionReportFlow.waiting_for_comment)
async def handle_execution_report_comment(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("meetings.idea.cancelled", lang_code))
        return
    comment = _optional_input_value(message.text)
    if not comment:
        await message.answer(get_text("meetings.execution.report.error", lang_code))
        return
    data = await state.get_data()
    await state.set_state(ExecutionReportFlow.waiting_for_proof)
    await state.update_data(comment=comment, execution_id=data.get("execution_id"))
    await message.answer(get_text("meetings.execution.proof.prompt", lang_code))


@router.message(ExecutionReportFlow.waiting_for_proof)
async def handle_execution_report_proof(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("meetings.idea.cancelled", lang_code))
        return
    data = await state.get_data()
    execution_id = int(data.get("execution_id") or 0)
    comment = str(data.get("comment") or "")

    proof_payload: str | None = None
    if message.document:
        proof_payload = MeetingsTable.serialize_proof(
            file_id=message.document.file_id,
            filename=message.document.file_name,
            link=None,
        )
    elif message.photo:
        photo = message.photo[-1]
        proof_payload = MeetingsTable.serialize_proof(
            file_id=photo.file_id,
            filename="photo.jpg",
            link=None,
        )
    elif message.video:
        proof_payload = MeetingsTable.serialize_proof(
            file_id=message.video.file_id,
            filename=message.video.file_name or "video.mp4",
            link=None,
        )
    else:
        text = _optional_input_value(message.text)
        if text and text.startswith(("http://", "https://")):
            proof_payload = MeetingsTable.serialize_proof(
                file_id=None,
                filename=None,
                link=text,
            )
        elif text:
            proof_payload = MeetingsTable.serialize_proof(
                file_id=None,
                filename=None,
                link=text,
            )

    await db.meetings.update_execution_report(
        execution_id=execution_id,
        comment=comment,
        proof=proof_payload,
    )
    await state.clear()
    logger.info("Execution %s report updated by %s", execution_id, message.from_user.id)
    await message.answer(get_text("meetings.execution.report.saved", lang_code))


@router.callback_query(F.data.startswith("exec:confirm:"))
async def handle_execution_confirm(
    callback: CallbackQuery,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    if not await _is_admin(callback.from_user.id, db):
        await callback.message.answer(get_text("meetings.admin.denied", lang_code))
        return
    try:
        execution_id = int((callback.data or "").split(":")[-1])
    except ValueError:
        await callback.message.answer(get_text("meetings.execution.error", lang_code))
        return
    await db.meetings.confirm_execution(
        execution_id=execution_id,
        admin_id=callback.from_user.id,
    )
    logger.info("Execution %s confirmed by %s", execution_id, callback.from_user.id)
    await callback.message.answer(get_text("meetings.execution.confirmed", lang_code))


@router.callback_query(F.data.startswith("exec:reject:"))
async def handle_execution_reject_start(
    callback: CallbackQuery,
    state: FSMContext,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    await callback.answer()
    lang_code = user_language(user_row, callback.from_user)
    if not await _is_admin(callback.from_user.id, db):
        await callback.message.answer(get_text("meetings.admin.denied", lang_code))
        return
    try:
        execution_id = int((callback.data or "").split(":")[-1])
    except ValueError:
        await callback.message.answer(get_text("meetings.execution.error", lang_code))
        return
    await state.clear()
    await state.set_state(ExecutionReviewFlow.waiting_for_reject_reason)
    await state.update_data(execution_id=execution_id)
    await callback.message.answer(get_text("meetings.execution.reject.prompt", lang_code))


@router.message(ExecutionReviewFlow.waiting_for_reject_reason)
async def handle_execution_reject_reason(
    message: Message,
    state: FSMContext,
    user_row: Optional[UserModel],
    db: DB,
) -> None:
    lang_code = user_language(user_row, message.from_user)
    if is_cancel_command(message.text):
        await state.clear()
        await message.answer(get_text("meetings.idea.cancelled", lang_code))
        return
    reason = _optional_input_value(message.text)
    if not reason:
        await message.answer(get_text("meetings.execution.reject.error", lang_code))
        return
    data = await state.get_data()
    execution_id = int(data.get("execution_id") or 0)
    await db.meetings.reject_execution(
        execution_id=execution_id,
        admin_id=message.from_user.id,
        reason=reason,
    )
    await state.clear()
    logger.info("Execution %s rejected by %s", execution_id, message.from_user.id)
    await message.answer(get_text("meetings.execution.rejected", lang_code))
