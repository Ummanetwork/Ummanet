import os


DEFAULT_MATERIALS_URL = os.getenv(
    "UMMANET_MATERIALS_URL",
    "https://t.me/Ummanetwork",
)
DEFAULT_COMMUNITY_SUPPORT_URL = os.getenv(
    "UMMANET_COMMUNITY_SUPPORT_URL",
    DEFAULT_MATERIALS_URL,
)
DEFAULT_MEN_CHAT_URL = os.getenv(
    "UMMANET_MEN_CHAT_URL",
    DEFAULT_MATERIALS_URL,
)
DEFAULT_WOMEN_CHAT_URL = os.getenv(
    "UMMANET_WOMEN_CHAT_URL",
    DEFAULT_MATERIALS_URL,
)

LINK_SLOTS = [
    {
        "slug": "button.docs.portal",
        "titles": {"ru": "Портал знаний", "en": "Knowledge portal"},
    },
    {
        "slug": "button.meetings.idea",
        "titles": {"ru": "Идея встречи", "en": "Meetings idea"},
    },
    {
        "slug": "button.meetings.vote",
        "titles": {"ru": "Голосование по встрече", "en": "Meetings vote"},
    },
    {
        "slug": "button.good.plan",
        "titles": {"ru": "План добрых дел", "en": "Good deeds plan"},
    },
    {
        "slug": "button.good.cities",
        "titles": {"ru": "Города добрых дел", "en": "Good deeds cities"},
    },
    {
        "slug": "button.inheritance.calc",
        "titles": {"ru": "Калькулятор наследства", "en": "Inheritance calculator"},
    },
    {
        "slug": "button.inheritance.guardian",
        "titles": {"ru": "Опекун", "en": "Guardian"},
    },
    {
        "slug": "button.inheritance.document",
        "titles": {"ru": "Документы по наследству", "en": "Inheritance documents"},
    },
    {
        "slug": "button.inheritance.ask",
        "titles": {"ru": "Вопрос по наследству", "en": "Ask about inheritance"},
    },
    {
        "slug": "button.nikah.start",
        "titles": {"ru": "Начать оформление никаха", "en": "Start nikah process"},
    },
    {
        "slug": "button.zakat.account",
        "titles": {"ru": "Учёт закята", "en": "Zakat ledger"},
    },
    {
        "slug": "button.zakat.vote",
        "titles": {"ru": "Голосование по закяту", "en": "Zakat vote"},
    },
    {
        "slug": "button.zakat.info",
        "titles": {"ru": "Памятка по закяту", "en": "Zakat guide"},
    },
    {
        "slug": "button.committee.scholars",
        "titles": {"ru": "Совет учёных", "en": "Committee scholars"},
    },
    {
        "slug": "button.committee.leaders",
        "titles": {"ru": "Лидеры общины", "en": "Community leaders"},
    },
    {
        "slug": "button.committee.elders",
        "titles": {"ru": "Совет старейшин", "en": "Committee elders"},
    },
    {
        "slug": "button.committee.general",
        "titles": {"ru": "Общий чат совета", "en": "Committee general chat"},
    },
    {
        "slug": "button.community.support",
        "titles": {"ru": "Поддержка общины", "en": "Support chat"},
    },
    {
        "slug": "button.materials",
        "titles": {"ru": "Материалы", "en": "Materials"},
    },
]

DEFAULT_LINKS = {
    slot["slug"]: {
        "ru": DEFAULT_MATERIALS_URL,
        "en": DEFAULT_MATERIALS_URL,
    }
    for slot in LINK_SLOTS
}

DEFAULT_LINKS["button.community.support"] = {
    "ru": DEFAULT_COMMUNITY_SUPPORT_URL,
    "en": DEFAULT_COMMUNITY_SUPPORT_URL,
}
