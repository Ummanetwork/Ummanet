from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from fluent_compiler.bundle import FluentBundle
from fluentogram import FluentTranslator, TranslatorHub

from app.services.i18n.localization import DEFAULT_LANGUAGE, resolve_language
from config.config import settings

_LOCALES_DIR = Path(__file__).resolve().parents[3] / "locales"


def _dedupe(sequence: Iterable[str]) -> Tuple[str, ...]:
    seen: List[str] = []
    for item in sequence:
        if item not in seen:
            seen.append(item)
    return tuple(seen)


def _bundle_locale(locale_code: str) -> str:
    overrides = {
        "ru": "ru-RU",
        "en": "en-US",
        "ar": "ar-SA",
        "de": "de-DE",
        "tr": "tr-TR",
    }
    return overrides.get(locale_code, f"{locale_code}-{locale_code.upper()}")


def _fallback_chain(locale_code: str) -> Tuple[str, ...]:
    if locale_code == "ru":
        chain = ("ru", "en")
    elif locale_code == "en":
        chain = ("en", "ru")
    elif locale_code == "ar":
        chain = ("ar", "en", "ru")
    else:
        chain = (locale_code, "en", "ru")
    return _dedupe(chain)


def _normalized_locales() -> List[str]:
    raw = getattr(getattr(settings, "i18n", {}), "locales", []) or []
    locales: List[str] = []
    for code in raw:
        normalized = (code or "").strip().lower()
        if not normalized or normalized == "dev":
            continue
        if normalized not in locales:
            locales.append(normalized)
    for base in ("ru", "en"):
        if base not in locales:
            locales.append(base)
    return locales


def _translation_file(locale_code: str) -> Path:
    candidate = _LOCALES_DIR / locale_code / "LC_MESSAGES" / "txt.ftl"
    if candidate.exists():
        return candidate
    fallback = _LOCALES_DIR / "en" / "LC_MESSAGES" / "txt.ftl"
    if not fallback.exists():
        raise FileNotFoundError(f"Missing translation files for {locale_code!r} and fallback 'en'")
    return fallback


def _build_translator(locale_code: str) -> FluentTranslator:
    filenames = [str(_translation_file(locale_code))]
    bundle_locale = _bundle_locale(locale_code)
    translator = FluentBundle.from_files(
        locale=bundle_locale,
        filenames=filenames,
        use_isolating=False,
    )
    return FluentTranslator(locale=locale_code, translator=translator)


def create_translator_hub() -> TranslatorHub:
    locales = _normalized_locales()
    root_locale = resolve_language(
        getattr(getattr(settings, "i18n", {}), "default_locale", None),
        DEFAULT_LANGUAGE,
    )
    if root_locale not in locales and root_locale != "dev":
        locales.append(root_locale)

    fallback_map: Dict[str, Tuple[str, ...]] = {}
    for locale_code in locales:
        fallback_map[locale_code] = _fallback_chain(locale_code)
    if root_locale not in fallback_map:
        fallback_map[root_locale] = _fallback_chain(root_locale)

    translators = [_build_translator(locale_code) for locale_code in sorted(fallback_map)]

    return TranslatorHub(
        fallback_map,
        translators,
        root_locale=root_locale,
    )
