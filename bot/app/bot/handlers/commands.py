import asyncio
import re
from typing import Optional, Set

from aiogram import Bot, F, Router
from aiogram.enums import BotCommandScopeType
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (BotCommandScopeChat, CallbackQuery, Message, ReplyKeyboardMarkup, KeyboardButton)
from aiogram_dialog import DialogManager

from app.bot.dialogs.flows.settings.states import SettingsSG
from app.bot.enums.roles import UserRole
from app.bot.filters.dialog_filters import DialogStateFilter, DialogStateGroupFilter
from app.bot.keyboards.menu_button import get_main_menu_commands
from app.bot.states import RegistrationSG
from app.bot.states import UnbanAppealSG
from app.infrastructure.database.db import DB
from app.infrastructure.database.models.user import UserModel
from app.bot.handlers.comitee import show_welcome_menu
from app.bot.services.registration import (
    REGISTRATION_CALLBACK_PREFIX,
    REGISTRATION_GREETING,
    build_registration_keyboard,
)
from app.services.i18n.localization import get_text, resolve_language
from app.bot.services.invite_flow import normalize_invite_payload, try_attach_invite
from config.config import settings

commands_router = Router()


def _admin_id_set() -> Set[int]:
    raw_ids = getattr(settings, "ADMIN_IDS", [])
    if isinstance(raw_ids, (list, tuple, set)):
        values = raw_ids
    elif raw_ids is None:
        values = []
    else:
        values = str(raw_ids).replace(";", ",").split(",")

    result: Set[int] = set()
    for item in values:
        if item is None:
            continue
        text = str(item).strip()
        if not text:
            continue
        try:
            result.add(int(text))
        except ValueError:
            continue
    return result


def _admins_chat_id() -> int:
    raw = getattr(settings, "ADMINS_CHAT", None)
    try:
        return int(str(raw).strip()) if raw is not None and str(raw).strip() else 0
    except Exception:
        return 0


async def _notify_admins_chat(bot: Bot, text: str) -> None:
    chat_id = _admins_chat_id()
    if not chat_id:
        return

    async def _send() -> None:
        try:
            await bot.send_message(chat_id=chat_id, text=text)
        except Exception:
            pass

    try:
        asyncio.get_running_loop().create_task(_send())
    except RuntimeError:
        await _send()


def _normalize_name(raw_name: Optional[str]) -> Optional[str]:
    if not raw_name:
        return None
    candidate = re.sub(r"\s+", " ", raw_name.strip())
    if len(candidate) < 2:
        return None
    allowed_non_letters = {" ", "-", "'", "’"}
    letters = []
    for char in candidate:
        if char.isalpha():
            letters.append(char)
            continue
        if char in allowed_non_letters:
            continue
        return None
    if len(letters) < 2:
        return None
    lowered = [char.casefold() for char in letters]
    if len(set(lowered)) < 2:
        return None
    return candidate


EMAIL_REGEX = re.compile(
    r"^(?P<local>[A-Z0-9._%+-]+)@(?P<domain>[A-Z0-9.-]+\.[A-Z]{2,})$",
    re.IGNORECASE,
)


def _normalize_email(raw_email: Optional[str]) -> Optional[str]:
    if not raw_email:
        return None
    candidate = raw_email.strip()
    if len(candidate) > 254:
        return None
    if EMAIL_REGEX.match(candidate) is None:
        return None
    return candidate.lower()


def _normalize_phone(raw_phone: Optional[str]) -> Optional[str]:
    if not raw_phone:
        return None
    cleaned = raw_phone.strip()
    cleaned = re.sub(r"[ \-\(\)\.]", "", cleaned)
    if not cleaned:
        return None
    prefix = ""
    number = cleaned
    if cleaned.startswith("+"):
        prefix = "+"
        number = cleaned[1:]
    if not number.isdigit():
        return None
    if len(number) < 9 or len(number) > 14:
        return None
    return prefix + number


def _digits_only(value: Optional[str]) -> str:
    """Return only digits from a phone string (for comparison)."""
    return re.sub(r"\D", "", value or "")


def _map_ru_8_to_7(digits: str) -> str:
    """Normalize Russian phone digits: leading '8' -> '7' when length is 11.

    This helps match numbers like 8XXXXXXXXXX with +7XXXXXXXXXX.
    """
    if len(digits) == 11 and digits.startswith("8"):
        return "7" + digits[1:]
    return digits


async def _send_registration_prompt(message: Message) -> None:
    await message.answer(
        REGISTRATION_GREETING,
        reply_markup=build_registration_keyboard(),
    )


@commands_router.message(CommandStart())
async def process_start_command(
    message: Message,
    dialog_manager: DialogManager,
    bot: Bot,
    db: DB,
    user_row: Optional[UserModel],
    state: FSMContext,
) -> None:
    payload = ""
    if message.text:
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1:
            payload = parts[1].strip()
    invite_code = normalize_invite_payload(payload)

    if user_row is None:
        await state.clear()
        if invite_code:
            await state.update_data(invite_code=invite_code)
        await _send_registration_prompt(message)
        return

    await state.clear()

    lang_code = resolve_language(
        user_row.language_code if user_row else None,
        message.from_user.language_code,
    )
    version = getattr(settings, "BOT_VERSION", "0.0.0")
    await message.answer(
        get_text("bot.version.info", lang_code, version=version),
    )

    admin_ids = _admin_id_set()
    desired_role = (
        UserRole.ADMIN if message.from_user.id in admin_ids else UserRole.USER
    )

    if user_row.role != desired_role:
        await db.users.set_role(user_id=message.from_user.id, role=desired_role)
        try:
            user_row = user_row.model_copy(update={"role": desired_role})
            dialog_manager.middleware_data["user_row"] = user_row
        except AttributeError:
            pass

    # Avoid updating Telegram commands on every /start to prevent user-facing
    # "Main menu updated" system notifications in clients.

    try:
        await dialog_manager.reset_stack()
    except AttributeError:
        pass

    if invite_code:
        await try_attach_invite(
            bot=bot,
            db=db,
            user_id=message.from_user.id,
            invite_code=invite_code,
            lang_code=lang_code,
        )

    await show_welcome_menu(
        message,
        is_new_user=False,
        lang_code=lang_code,
    )


@commands_router.callback_query(F.data.startswith(REGISTRATION_CALLBACK_PREFIX))
async def process_registration_language(
    callback: CallbackQuery,
    dialog_manager: DialogManager,
    bot: Bot,
    db: DB,
    user_row: Optional[UserModel],
    state: FSMContext,
) -> None:
    data = callback.data or ""
    selected_lang = data[len(REGISTRATION_CALLBACK_PREFIX) :].strip().lower()

    if not selected_lang:
        await callback.answer()
        return

    if user_row is not None:
        lang_code = resolve_language(
            user_row.language_code,
            callback.from_user.language_code,
        )
        await callback.answer(
            get_text("registration.already", lang_code),
            show_alert=True,
        )
        return

    admin_ids = _admin_id_set()
    desired_role = (
        UserRole.ADMIN if callback.from_user.id in admin_ids else UserRole.USER
    )

    resolved_lang = resolve_language(selected_lang, callback.from_user.language_code)

    await state.clear()
    await state.set_state(RegistrationSG.waiting_for_name)
    await state.update_data(
        registration_language=selected_lang,
        desired_role=desired_role.value,
    )

    await callback.answer()

    if callback.message is not None:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await callback.message.answer(
            get_text("registration.intro", resolved_lang),
        )
        await callback.message.answer(
            get_text("registration.prompt.name", resolved_lang),
        )
    else:
        await bot.send_message(
            chat_id=callback.from_user.id,
            text=get_text("registration.intro", resolved_lang),
        )
        await bot.send_message(
            chat_id=callback.from_user.id,
            text=get_text("registration.prompt.name", resolved_lang),
        )


@commands_router.message(StateFilter(RegistrationSG.waiting_for_name))
async def handle_registration_name(
    message: Message,
    state: FSMContext,
) -> None:
    state_data = await state.get_data()
    lang_code = resolve_language(
        state_data.get("registration_language"),
        message.from_user.language_code,
    )

    normalized_name = _normalize_name(message.text)
    if normalized_name is None:
        await message.answer(get_text("registration.error.name_invalid", lang_code))
        return

    await state.update_data(full_name=normalized_name)
    await state.set_state(RegistrationSG.waiting_for_email)
    await message.answer(get_text("registration.prompt.email", lang_code))


@commands_router.message(StateFilter(RegistrationSG.waiting_for_email))
async def handle_registration_email(
    message: Message,
    state: FSMContext,
) -> None:
    state_data = await state.get_data()
    lang_code = resolve_language(
        state_data.get("registration_language"),
        message.from_user.language_code,
    )

    normalized_email = _normalize_email(message.text)
    if normalized_email is None:
        await message.answer(get_text("registration.error.email_invalid", lang_code))
        return

    await state.update_data(email=normalized_email)
    await state.set_state(RegistrationSG.waiting_for_phone)
    await message.answer(get_text("registration.prompt.phone", lang_code))


@commands_router.message(StateFilter(RegistrationSG.waiting_for_phone))
async def handle_registration_phone(
    message: Message,
    state: FSMContext,
    dialog_manager: DialogManager,
    bot: Bot,
    db: DB,
) -> None:
    state_data = await state.get_data()
    lang_code = resolve_language(
        state_data.get("registration_language"),
        message.from_user.language_code,
    )

    normalized_phone = _normalize_phone(message.text)
    if normalized_phone is None:
        await message.answer(get_text("registration.error.phone_invalid", lang_code))
        return

    await state.update_data(phone_typed=normalized_phone)
    kb = ReplyKeyboardMarkup(
        resize_keyboard=True,
        one_time_keyboard=True,
        keyboard=[[KeyboardButton(text=get_text("registration.button.share_contact", lang_code), request_contact=True)]],
    )
    await state.set_state(RegistrationSG.waiting_for_phone_contact)
    await message.answer(get_text("registration.prompt.phone_contact", lang_code), reply_markup=kb)


@commands_router.message(StateFilter(RegistrationSG.waiting_for_phone_contact), F.contact)
async def handle_registration_phone_contact(
    message: Message,
    state: FSMContext,
    dialog_manager: DialogManager,
    bot: Bot,
    db: DB,
) -> None:
    data = await state.get_data()
    lang_code = resolve_language(
        data.get("registration_language"),
        message.from_user.language_code,
    )
    contact = getattr(message, "contact", None)
    contact_phone = None
    if contact is not None and getattr(contact, "phone_number", None):
        contact_phone = _normalize_phone(contact.phone_number)
    typed_phone = _normalize_phone(data.get("phone_typed")) if data.get("phone_typed") else None

    digits_contact = _map_ru_8_to_7(_digits_only(contact_phone))
    digits_typed = _map_ru_8_to_7(_digits_only(typed_phone))

    if not digits_contact:
        await message.answer(get_text("registration.error.phone_contact_missing", lang_code))
        if typed_phone:
            await message.answer(
                get_text(
                    "registration.error.phone_debug_mismatch",
                    lang_code,
                    typed=typed_phone or "-",
                    contact=contact_phone or "-",
                )
            )
        return

    if digits_typed and digits_contact != digits_typed:
        await message.answer(get_text("registration.error.phone_mismatch", lang_code))
        await message.answer(
            get_text(
                "registration.error.phone_debug_mismatch",
                lang_code,
                typed=typed_phone or "-",
                contact=contact_phone or "-",
            )
        )
        # Ask user to re-enter phone number; remove contact keyboard
        from aiogram.types import ReplyKeyboardRemove
        await state.set_state(RegistrationSG.waiting_for_phone)
        await state.update_data(phone_typed=None)
        await message.answer(
            get_text("registration.prompt.phone_retry", lang_code),
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    await _notify_admins_chat(
        bot,
        f"Регистрация: подтверждён телефон {contact_phone or typed_phone or '-'} у пользователя {message.from_user.id}",
    )

    selected_lang = data.get("registration_language")
    desired_role_value = data.get("desired_role", UserRole.USER.value)
    full_name = data.get("full_name")
    email = data.get("email")
    phone_number = contact_phone or typed_phone
    invite_code = normalize_invite_payload(data.get("invite_code"))
    if not selected_lang or not full_name or not phone_number:
        await state.clear()
        await _send_registration_prompt(message)
        return

    desired_role = UserRole(desired_role_value)
    await db.users.add(
        user_id=message.from_user.id,
        language_code=selected_lang,
        role=desired_role,
        full_name=full_name,
        email=email,
        phone_number=phone_number,
    )
    await _notify_admins_chat(
        bot,
        f"Регистрация: создан пользователь в БД (id={message.from_user.id}, язык={selected_lang}, роль={desired_role.value})",
    )
    await db.users.set_phone_verified(user_id=message.from_user.id, verified=True)
    await _notify_admins_chat(
        bot,
        f"Регистрация: телефон помечен подтверждённым (id={message.from_user.id})",
    )

    backend_client = getattr(message.bot, "backend_documents_client", None)
    if backend_client is not None:

        async def _sync_backend_user() -> None:
            try:
                await backend_client.create_user(
                    telegram_user_id=message.from_user.id,
                    full_name=full_name,
                    email=email,
                    phone_number=phone_number,
                    language_code=selected_lang,
                    role=desired_role.value,
                )
                await _notify_admins_chat(
                    bot,
                    f"Регистрация: профиль создан в бэкенде (id={message.from_user.id})",
                )
            except Exception:
                await _notify_admins_chat(
                    bot,
                    f"Регистрация: ошибка создания профиля в бэкенде (id={message.from_user.id})",
                )

        asyncio.create_task(_sync_backend_user())

    new_user = await db.users.get_user(user_id=message.from_user.id)
    if new_user is not None:
        try:
            dialog_manager.middleware_data["user_row"] = new_user
        except AttributeError:
            pass

    # Avoid updating Telegram commands here to prevent user-facing "Main menu updated"
    # system notifications in clients.

    # Hide keyboard
    from aiogram.types import ReplyKeyboardRemove
    await message.answer(
        get_text("registration.success", lang_code),
        reply_markup=ReplyKeyboardRemove(),
    )

    try:
        await dialog_manager.reset_stack()
    except AttributeError:
        pass

    await show_welcome_menu(message, is_new_user=True, lang_code=lang_code)
    if invite_code:
        await try_attach_invite(
            bot=bot,
            db=db,
            user_id=message.from_user.id,
            invite_code=invite_code,
            lang_code=lang_code,
        )
    await _notify_admins_chat(
        bot,
        f"Регистрация завершена: пользователь {message.from_user.id} ({full_name or '-'}), язык={selected_lang}",
    )
    await state.clear()


@commands_router.message(StateFilter(RegistrationSG.waiting_for_phone_contact))
async def handle_registration_phone_contact_text(
    message: Message,
    state: FSMContext,
) -> None:
    # Intercept any non-contact messages while waiting for contact
    data = await state.get_data()
    lang_code = resolve_language(
        data.get("registration_language"),
        message.from_user.language_code,
    )
    kb = ReplyKeyboardMarkup(
        resize_keyboard=True,
        one_time_keyboard=True,
        keyboard=[[KeyboardButton(text=get_text("registration.button.share_contact", lang_code), request_contact=True)]],
    )
    await message.answer(get_text("registration.error.contact_expected", lang_code))
    await message.answer(get_text("registration.prompt.phone_contact", lang_code), reply_markup=kb)



def _scheduler_unavailable_message(user_row: Optional[UserModel], message: Message) -> str:
    lang_code = resolve_language(
        getattr(user_row, "language_code", None),
        message.from_user.language_code,
    )
    return get_text("command.scheduler.unavailable", lang_code)


@commands_router.message(Command("del"))
async def send_and_del_message(
    message: Message,
    user_row: Optional[UserModel],
) -> None:
    await message.answer(_scheduler_unavailable_message(user_row, message))


@commands_router.message(Command("simple"))
async def task_handler(
    message: Message,
    user_row: Optional[UserModel],
) -> None:
    await message.answer(_scheduler_unavailable_message(user_row, message))


@commands_router.message(Command("delay"))
async def delay_task_handler(
    message: Message,
    user_row: Optional[UserModel],
) -> None:
    await message.answer(_scheduler_unavailable_message(user_row, message))


@commands_router.message(Command("periodic"))
async def dynamic_periodic_task_handler(
    message: Message,
    user_row: Optional[UserModel],
) -> None:
    await message.answer(_scheduler_unavailable_message(user_row, message))


@commands_router.message(Command("del_periodic"))
async def delete_all_periodic_tasks_handler(
    message: Message,
    user_row: Optional[UserModel],
) -> None:
    await message.answer(_scheduler_unavailable_message(user_row, message))


@commands_router.message(
    ~DialogStateGroupFilter(state_group=SettingsSG),
    Command("lang"),
)
async def process_lang_command_sg(
    message: Message,
    dialog_manager: DialogManager,
) -> None:
    await dialog_manager.start(state=SettingsSG.lang)


@commands_router.message(
    DialogStateGroupFilter(state_group=SettingsSG),
    ~DialogStateFilter(state=SettingsSG.lang),
    Command("lang"),
)
async def process_lang_command(
    message: Message,
    dialog_manager: DialogManager,
) -> None:
    await dialog_manager.switch_to(state=SettingsSG.lang)


@commands_router.message(Command("help"))
async def process_help_command(
    message: Message,
    user_row: Optional[UserModel],
) -> None:
    lang_code = resolve_language(
        getattr(user_row, "language_code", None),
        message.from_user.language_code,
    )
    await message.answer(get_text("help.message", lang_code))

# Unban request flow
UNBAN_CALLBACK_PREFIX = "unban"


@commands_router.callback_query(F.data == f"{UNBAN_CALLBACK_PREFIX}:request")
async def handle_unban_request_click(callback: CallbackQuery, state: FSMContext) -> None:
    user = callback.from_user
    lang_code = resolve_language(getattr(user, "language_code", None))
    await state.set_state(UnbanAppealSG.waiting_for_reason)
    await callback.message.answer(get_text("unban.request.prompt", lang_code))
    await callback.answer()


@commands_router.message(StateFilter(UnbanAppealSG.waiting_for_reason))
async def handle_unban_reason(message: Message, state: FSMContext, db: DB, bot: Bot) -> None:
    user = message.from_user
    text = (message.text or "").strip()
    lang_code = resolve_language(getattr(user, "language_code", None))
    if not text:
        await message.answer(get_text("unban.request.prompt", lang_code))
        return

    # Save request in DB
    await db.users.set_unban_request(user_id=user.id, reason=text)

    # Notify admins (ADMIN_IDS) or fallback to scholars group if configured
    from_user_id = user.id
    notice = get_text("notify.unban.request.admin", lang_code).format(user_id=from_user_id, reason=text)
    admin_ids = _admin_id_set()
    if admin_ids:
        for admin_id in admin_ids:
            try:
                await bot.send_message(chat_id=admin_id, text=notice)
            except Exception:
                continue
    else:
        try:
            group_id = int(getattr(getattr(settings, "bot", object()), "scholars_group_id", 0) or 0)
        except Exception:
            group_id = 0
        if group_id:
            try:
                await bot.send_message(chat_id=group_id, text=notice)
            except Exception:
                pass

    await message.answer(get_text("unban.request.sent", lang_code))
    await state.clear()
