from __future__ import annotations

from typing import Iterable, Dict

from app.infrastructure.database.db import DB
from app.services.i18n.localization import set_runtime_language_texts


async def ensure_languages(
    db: DB,
    locales: Iterable[str],
    default_locale: str | None = None,
) -> None:
    normalized_codes: list[str] = []
    for code in locales:
        normalized = (code or "").strip().lower()
        if not normalized:
            continue
        if normalized not in normalized_codes:
            normalized_codes.append(normalized)

    default_code = (default_locale or "").strip().lower()
    if default_code == "dev":
        default_code = None

    if default_code and default_code not in normalized_codes:
        normalized_codes.append(default_code)

    if "dev" not in normalized_codes:
        normalized_codes.append("dev")

    target_codes = set(normalized_codes)
    if not target_codes:
        return

    existing = await db.languages.list_all()
    existing_codes = {language.code for language in existing}
    existing_default_code = next(
        (language.code for language in existing if language.is_default), None
    )

    for code in sorted(target_codes):
        if code in existing_codes:
            continue

        is_default = code == default_code and existing_default_code is None
        await db.languages.create(
            code=code,
            is_default=is_default,
        )
        existing_codes.add(code)
        if is_default:
            existing_default_code = code

    if default_code and (
        existing_default_code is None or existing_default_code != default_code
    ):
        language = await db.languages.get_by_code(default_code)
        if language is not None:
            await db.languages.set_default(language.id)


async def load_translations(db: DB) -> None:
    """Load translations from DB into runtime cache for quick access.

    This reads all languages, then fetches translation_keys and translations
    and builds a {lang_code: {identifier: value}} mapping.
    """
    languages = await db.languages.list_all()
    if not languages:
        return

    # Map key_id -> identifier
    keys = await db.translation_keys.list_all()
    key_id_to_ident: Dict[int, str] = {k.id: k.identifier for k in keys}
    ident_to_key_id: Dict[str, int] = {k.identifier: k.id for k in keys}

    for lang in languages:
        rows = await db.translations.list_by_language(lang.id)
        mapping: Dict[str, str] = {}
        for tr in rows:
            ident = key_id_to_ident.get(tr.key_id)
            if not ident:
                continue
            if tr.value is None:
                continue
            mapping[ident] = tr.value
        # Patch legacy contract action label if it still uses the old text.
        if lang.code == "ru":
            if mapping.get("contracts.flow.button.edit") == "Изменить данные":
                mapping["contracts.flow.button.edit"] = "Подробнее"
                key_id = ident_to_key_id.get("contracts.flow.button.edit")
                if key_id:
                    await db.translations.upsert(
                        language_id=lang.id,
                        key_id=key_id,
                        value="Подробнее",
                    )
        elif lang.code == "en":
            if mapping.get("contracts.flow.button.edit") == "Edit data":
                mapping["contracts.flow.button.edit"] = "Details"
                key_id = ident_to_key_id.get("contracts.flow.button.edit")
                if key_id:
                    await db.translations.upsert(
                        language_id=lang.id,
                        key_id=key_id,
                        value="Details",
                    )
        set_runtime_language_texts(lang.code, mapping)
