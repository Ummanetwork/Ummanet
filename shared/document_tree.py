"""Document tree definitions shared across backend and bot."""

from __future__ import annotations

from typing import Dict, List

from .contract_templates import CONTRACT_TEMPLATE_TOPIC_LOOKUP

DOCUMENT_TREE: List[Dict[str, object]] = [
    {
        "category": "holidays",
        "titles": {"ru": "Исламские праздники", "en": "Islamic holidays"},
        "topics": [
            {
                "topic": "uraza",
                "titles": {"ru": "Ураза-байрам", "en": "Eid al-Fitr"},
            },
            {
                "topic": "kurban",
                "titles": {"ru": "Курбан-байрам", "en": "Eid al-Adha"},
            },
            {
                "topic": "ramadan",
                "titles": {"ru": "Рамадан", "en": "Ramadan"},
            },
            {
                "topic": "hajj",
                "titles": {"ru": "Хадж", "en": "Hajj"},
            },
        ],
    },
    {
        "category": "knowledge",
        "titles": {"ru": "Знания по шариату", "en": "Sharia knowledge"},
        "topics": [
            {
                "topic": "tauhid",
                "titles": {"ru": "Таухид", "en": "Tawhid"},
            },
            {
                "topic": "faith",
                "titles": {"ru": "Вера", "en": "Faith"},
            },
            {
                "topic": "fiqh",
                "titles": {"ru": "Фикх", "en": "Fiqh"},
            },
            {
                "topic": "culture",
                "titles": {"ru": "Культура", "en": "Culture"},
            },
        ],
    },
]


def build_topic_lookup() -> Dict[str, Dict[str, object]]:
    lookup: Dict[str, Dict[str, object]] = {}
    for category in DOCUMENT_TREE:
        for topic in category["topics"]:
            lookup[topic["topic"]] = {
                "category": category["category"],
                "topic": topic["topic"],
                "titles": topic["titles"],
            }
    return lookup


DOCUMENT_TOPIC_LOOKUP = build_topic_lookup()
ALL_DOCUMENT_TOPIC_LOOKUP = {**DOCUMENT_TOPIC_LOOKUP, **CONTRACT_TEMPLATE_TOPIC_LOOKUP}

