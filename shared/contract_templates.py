"""Contract template catalog shared between backend and bot."""

from __future__ import annotations

from typing import Dict, List

CONTRACT_TEMPLATES_TREE: List[Dict[str, object]] = [
    {
        "category": "exchange",
        "titles": {
            "ru": "💸 Обмен и торговля",
            "en": "💸 Exchange & trade",
        },
        "templates": [
            {
                "template": "bay",
                "topic": "contracts.exchange.bay",
                "titles": {
                    "ru": "Байʿ (купля-продажа)",
                    "en": "Bayʿ (sale)",
                },
            },
            {
                "template": "salam",
                "topic": "contracts.exchange.salam",
                "titles": {
                    "ru": "Салам (предоплата за будущий товар)",
                    "en": "Salam (advance payment)",
                },
            },
            {
                "template": "istisna",
                "topic": "contracts.exchange.istisna",
                "titles": {
                    "ru": "Истиснаʿ (договор изготовления)",
                    "en": "Istisnaʿ (manufacturing order)",
                },
            },
            {
                "template": "ijara",
                "topic": "contracts.exchange.ijara",
                "titles": {
                    "ru": "Иджāра (аренда/наём)",
                    "en": "Ijāra (lease/hiring)",
                },
            },
            {
                "template": "installment",
                "topic": "contracts.exchange.installment",
                "titles": {
                    "ru": "Продажа в рассрочку",
                    "en": "Installment sale",
                },
            },
            {
                "template": "murabaha",
                "topic": "contracts.exchange.murabaha",
                "titles": {
                    "ru": "Мурабаха (покупка с наценкой)",
                    "en": "Murābaḥa (markup sale)",
                },
            },
        ],
    },
    {
        "category": "finance",
        "titles": {
            "ru": "💵 Финансы и долги",
            "en": "💵 Finance & debt",
        },
        "templates": [
            {
                "template": "qard",
                "topic": "contracts.finance.qard",
                "titles": {
                    "ru": "Карḍ (заём без процентов)",
                    "en": "Qarḍ (interest-free loan)",
                },
            },
            {
                "template": "rahn",
                "topic": "contracts.finance.rahn",
                "titles": {
                    "ru": "Рахн (залог)",
                    "en": "Rahn (pledge)",
                },
            },
            {
                "template": "kafala",
                "topic": "contracts.finance.kafala",
                "titles": {
                    "ru": "Кафāла (поручительство)",
                    "en": "Kafāla (surety)",
                },
            },
            {
                "template": "hawala",
                "topic": "contracts.finance.hawala",
                "titles": {
                    "ru": "Хавāла (перевод долга)",
                    "en": "Ḥawāla (debt assignment)",
                },
            },
        ],
    },
    {
        "category": "partnership",
        "titles": {
            "ru": "👥 Партнёрство",
            "en": "👥 Partnerships",
        },
        "templates": [
            {
                "template": "musharaka",
                "topic": "contracts.partnership.musharaka",
                "titles": {
                    "ru": "Мушāрака (совместный бизнес)",
                    "en": "Mushāraka (equity partnership)",
                },
            },
            {
                "template": "mudaraba",
                "topic": "contracts.partnership.mudaraba",
                "titles": {
                    "ru": "Муḍāraba (капитал + труд)",
                    "en": "Muḍāraba (capital + labour)",
                },
            },
            {
                "template": "inan",
                "topic": "contracts.partnership.inan",
                "titles": {
                    "ru": "ʿИнāн (общее участие)",
                    "en": "ʿInān (joint participation)",
                },
            },
            {
                "template": "wakala",
                "topic": "contracts.partnership.wakala",
                "titles": {
                    "ru": "Викāла (доверенность)",
                    "en": "Wakāla (agency)",
                },
            },
        ],
    },
    {
        "category": "gratis",
        "titles": {
            "ru": "🎁 Безвозмездные договоры",
            "en": "🎁 Gratuitous contracts",
        },
        "templates": [
            {
                "template": "hiba",
                "topic": "contracts.gratis.hiba",
                "titles": {
                    "ru": "Хиба (дарение)",
                    "en": "Hiba (gift)",
                },
            },
            {
                "template": "sadaqa",
                "topic": "contracts.gratis.sadaqa",
                "titles": {
                    "ru": "Садака (милостыня)",
                    "en": "Ṣadaqa (charity)",
                },
            },
            {
                "template": "ariya",
                "topic": "contracts.gratis.ariya",
                "titles": {
                    "ru": "ʿАриya (временное пользование вещью)",
                    "en": "ʿĀriya (temporary use)",
                },
            },
            {
                "template": "waqf",
                "topic": "contracts.gratis.waqf",
                "titles": {
                    "ru": "Вакф (пожертвование на вечное благо)",
                    "en": "Waqf (endowment)",
                },
            },
            {
                "template": "wasiya",
                "topic": "contracts.gratis.wasiya",
                "titles": {
                    "ru": "Васия (завещание)",
                    "en": "Waṣiyya (bequest)",
                },
            },
        ],
    },
    {
        "category": "family",
        "titles": {
            "ru": "💑 Семейные договоры",
            "en": "💑 Family contracts",
        },
        "templates": [
            {
                "template": "nikah",
                "topic": "contracts.family.nikah",
                "titles": {
                    "ru": "Никаḥ (брак)",
                    "en": "Nikāḥ (marriage)",
                },
            },
            {
                "template": "talaq",
                "topic": "contracts.family.talaq",
                "titles": {
                    "ru": "Талāк (развод мужем)",
                    "en": "Ṭalāq (divorce by husband)",
                },
            },
            {
                "template": "khul",
                "topic": "contracts.family.khul",
                "titles": {
                    "ru": "Хулʿ (развод по инициативе жены)",
                    "en": "Khulʿ (divorce by wife)",
                },
            },
            {
                "template": "ridaa",
                "topic": "contracts.family.ridaa",
                "titles": {
                    "ru": "Риḍāʿ (договор вскармливания)",
                    "en": "Riḍāʿ (nursing contract)",
                },
            },
        ],
    },
    {
        "category": "settlement",
        "titles": {
            "ru": "🤝 Примирение и доверие",
            "en": "🤝 Settlement & trust",
        },
        "templates": [
            {
                "template": "sulh",
                "topic": "contracts.settlement.sulh",
                "titles": {
                    "ru": "Сульḥ (примирение)",
                    "en": "Ṣulḥ (settlement)",
                },
            },
            {
                "template": "amana",
                "topic": "contracts.settlement.amana",
                "titles": {
                    "ru": "Амāна (хранение)",
                    "en": "Amāna (safekeeping)",
                },
            },
            {
                "template": "uaria",
                "topic": "contracts.settlement.uaria",
                "titles": {
                    "ru": "ʿУāрия (временное пользование вещью)",
                    "en": "ʿĀriyya (temporary loan of property)",
                },
            },
        ],
    },
]


def build_template_lookup() -> Dict[str, Dict[str, object]]:
    lookup: Dict[str, Dict[str, object]] = {}
    for category in CONTRACT_TEMPLATES_TREE:
        category_slug = category["category"]
        category_titles = category["titles"]
        for template in category["templates"]:
            topic_key = template["topic"]
            lookup[topic_key] = {
                "category": category_slug,
                "template": template["template"],
                "titles": template["titles"],
                "category_titles": category_titles,
            }
    return lookup


CONTRACT_TEMPLATE_TOPIC_LOOKUP = build_template_lookup()

