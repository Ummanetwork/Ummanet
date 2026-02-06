from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

REGISTRATION_CALLBACK_PREFIX = "register_lang:"

_LANGUAGE_BUTTONS = [
    ("Русский", "ru"),
    ("English", "en"),
    ("العربية", "ar"),
]

REGISTRATION_GREETING = (
    "Привет незнакомец!\n\n"
    "Ассаламу алейкум ва рахматуллахи ва баракатуху!\n"
    "Добро пожаловать в Шариатский бот — ваш помощник в разрешении споров по шариату "
    "с поддержкой искусственного интеллекта.\n"
    "Для продолжения общения выбери язык.\n\n"
    "Hello stranger!\n\n"
    "As-salamu alaikum wa rahmatullahi wa barakatuh!\n"
    "Welcome to the Sharia bot — your assistant for resolving disputes according to Sharia "
    "with the support of artificial intelligence.\n"
    "To continue, please choose your language.\n\n"
    "مرحباً أيها الغريب!\n\n"
    "السلام عليكم ورحمة الله وبركاته!\n"
    "مرحباً بك في بوت الشريعة — مساعدك في حل النزاعات وفقاً للشريعة بدعم من الذكاء الاصطناعي.\n"
    "للمتابعة، اختر لغتك."
)


def build_registration_keyboard() -> InlineKeyboardMarkup:
    """Construct inline keyboard with available registration languages."""
    buttons = [
        [
            InlineKeyboardButton(
                text=label, callback_data=f"{REGISTRATION_CALLBACK_PREFIX}{code}"
            )
        ]
        for label, code in _LANGUAGE_BUTTONS
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


__all__ = [
    "REGISTRATION_CALLBACK_PREFIX",
    "REGISTRATION_GREETING",
    "build_registration_keyboard",
]
