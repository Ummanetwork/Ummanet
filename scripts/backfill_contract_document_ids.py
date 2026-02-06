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


async def _run_backfill(apply: bool) -> None:
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
        await cur.execute(
            """
            WITH candidates AS (
                SELECT d.id AS document_id, c.id AS contract_id
                FROM documents d
                JOIN contracts c ON c.user_id = d.user_id
                WHERE d.contract_id IS NULL
                  AND d.type = 'Contract'
                  AND (
                      d.name = c.data->>'contract_title'
                      OR d.name = c.template_topic
                      OR d.name = c.type
                  )
            )
            SELECT COUNT(*) AS total
            FROM candidates
            """
        )
        row = await cur.fetchone()
        total = int(row["total"] or 0)

    if not apply:
        print(f"Matched {total} document(s). Run with --apply to update.")
        await connection.close()
        return

    async with connection.cursor() as cur:
        await cur.execute(
            """
            WITH candidates AS (
                SELECT d.id AS document_id, c.id AS contract_id
                FROM documents d
                JOIN contracts c ON c.user_id = d.user_id
                WHERE d.contract_id IS NULL
                  AND d.type = 'Contract'
                  AND (
                      d.name = c.data->>'contract_title'
                      OR d.name = c.template_topic
                      OR d.name = c.type
                  )
            )
            UPDATE documents d
            SET contract_id = c.contract_id
            FROM candidates c
            WHERE d.id = c.document_id
            """
        )
        await connection.commit()

    print(f"Updated {total} document(s) with contract_id.")
    await connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill documents.contract_id for contract PDFs"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply updates (default is dry-run)",
    )
    args = parser.parse_args()

    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_run_backfill(apply=args.apply))


if __name__ == "__main__":
    main()
