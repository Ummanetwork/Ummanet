import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Update
from psycopg_pool import AsyncConnectionPool

from app.infrastructure.database.db import DB
from app.infrastructure.database.connection.psycopg_connection import PsycopgConnection

logger = logging.getLogger(__name__)


class DataBaseMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Update, dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict[str, Any],
    ) -> Any:
        db_pool: AsyncConnectionPool = data.get("db_pool")

        if db_pool is None:
            logger.error("Database pool is not provided in middleware data.")
            raise RuntimeError("Missing db_pool in middleware context.")

        async with db_pool.connection() as raw_connection:
            try:
                # Enabling autocommit avoids long transactions that blocked the pool during network awaits.
                autocommit_changed = False
                if (
                    hasattr(raw_connection, "info")
                    and getattr(raw_connection.info, "autocommit", None) is False
                ):
                    await raw_connection.set_autocommit(True)
                    autocommit_changed = True
                connection = PsycopgConnection(raw_connection)
                data["db"] = DB(connection)
                return await handler(event, data)
            except Exception as exc:
                logger.exception("Database middleware handler raised error: %s", exc)
                raise
            finally:
                try:
                    if autocommit_changed:
                        await raw_connection.set_autocommit(False)
                except Exception:
                    logger.exception("Failed to restore autocommit flag")
                data.pop("db", None)
