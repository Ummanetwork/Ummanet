import argparse
import asyncio
import os
import sys
from typing import Any

from dynaconf import Dynaconf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOT_PATH = os.path.join(ROOT, "bot")
if BOT_PATH not in sys.path:
    sys.path.insert(0, BOT_PATH)

from app.infrastructure.database.connection.connect_to_pg import get_pg_connection

KEYS_BY_LANG = {
    "ru": {
        "contracts.list.title": "Ваши договоры:",
        "contracts.title.unknown": "Договор",
        "contracts.list.item": "📄 {title}\nСтатус: {status}\nДата: {date}\nКонтрагент: {party}",
        "contracts.list.party.unknown": "Не указан",
        "contracts.status.draft": "Черновик",
        "contracts.status.confirmed": "Сформирован",
        "contracts.status.sent_to_party": "Отправлен стороне",
        "contracts.status.party_approved": "Подтверждён стороной",
        "contracts.status.party_changes_requested": "Запрошены правки",
        "contracts.status.sent_to_scholar": "Отправлен учёному",
        "contracts.status.scholar_send_failed": "Ошибка отправки учёному",
        "contracts.status.sent": "Отправлен",
    },
    "en": {
        "contracts.list.title": "Your contracts:",
        "contracts.title.unknown": "Contract",
        "contracts.list.item": "📄 {title}\nStatus: {status}\nDate: {date}\nCounterparty: {party}",
        "contracts.list.party.unknown": "Not specified",
        "contracts.status.draft": "Draft",
        "contracts.status.confirmed": "Generated",
        "contracts.status.sent_to_party": "Sent to party",
        "contracts.status.party_approved": "Approved by party",
        "contracts.status.party_changes_requested": "Changes requested",
        "contracts.status.sent_to_scholar": "Sent to scholar",
        "contracts.status.scholar_send_failed": "Scholar send failed",
        "contracts.status.sent": "Sent",
    },
    "ar": {
        "contracts.list.title": "عقودك:",
        "contracts.title.unknown": "عقد",
        "contracts.list.item": "📄 {title}\nالحالة: {status}\nالتاريخ: {date}\nالطرف المقابل: {party}",
        "contracts.list.party.unknown": "غير محدد",
        "contracts.status.draft": "مسودة",
        "contracts.status.confirmed": "تم الإنشاء",
        "contracts.status.sent_to_party": "تم الإرسال للطرف",
        "contracts.status.party_approved": "تمت الموافقة من الطرف",
        "contracts.status.party_changes_requested": "تم طلب تعديلات",
        "contracts.status.sent_to_scholar": "أُرسل إلى العالِم",
        "contracts.status.scholar_send_failed": "فشل الإرسال إلى العالِم",
        "contracts.status.sent": "تم الإرسال",
    },
}


def _load_settings() -> Any:
    return Dynaconf(
        envvar_prefix=False,
        environments=True,
        env_switcher="ENV_FOR_DYNACONF",
        settings_files=[
            "bot/config/settings.toml",
            "bot/config/.secrets.toml",
        ],
        load_dotenv=True,
    )


async def _run_sync(apply: bool) -> None:
    settings = _load_settings()
    pg = settings.get("postgres") or {}
    if not pg:
        raise RuntimeError("Postgres settings not found in bot/config/settings.toml")

    connection = await get_pg_connection(
        db_name=pg.get("NAME"),
        host=pg.get("HOST"),
        port=int(pg.get("PORT")),
        user=pg.get("USER"),
        password=pg.get("PASSWORD"),
    )

    async with connection.cursor() as cur:
        await cur.execute("SELECT id, code FROM languages")
        languages = {row["code"]: int(row["id"]) for row in await cur.fetchall()}

    pending = 0
    for code, mapping in KEYS_BY_LANG.items():
        if code not in languages:
            continue
        pending += len(mapping)

    if not apply:
        print(f"Will upsert {pending} translation(s). Run with --apply to update.")
        await connection.close()
        return

    async with connection.cursor() as cur:
        for code, mapping in KEYS_BY_LANG.items():
            lang_id = languages.get(code)
            if not lang_id:
                continue
            for key, value in mapping.items():
                await cur.execute(
                    """
                    INSERT INTO translation_keys(identifier)
                    VALUES(%s)
                    ON CONFLICT (identifier) DO NOTHING
                    """,
                    (key,),
                )
                await cur.execute(
                    "SELECT id FROM translation_keys WHERE identifier = %s",
                    (key,),
                )
                key_row = await cur.fetchone()
                if not key_row:
                    continue
                key_id = int(key_row["id"])
                await cur.execute(
                    """
                    INSERT INTO translations(language_id, key_id, value)
                    VALUES(%s, %s, %s)
                    ON CONFLICT(language_id, key_id)
                    DO UPDATE SET value = EXCLUDED.value
                    """,
                    (lang_id, key_id, value),
                )
        await connection.commit()

    print(f"Upserted {pending} translation(s).")
    await connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync contract list translations into DB"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply updates (default is dry-run)",
    )
    args = parser.parse_args()

    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_run_sync(apply=args.apply))


if __name__ == "__main__":
    main()
