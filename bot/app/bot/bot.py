import asyncio
import json
import logging
import time

import psycopg_pool
import redis
from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import ExceptionTypeFilter
from aiogram.fsm.storage.base import DefaultKeyBuilder
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update
from aiogram_dialog import setup_dialogs
from aiogram_dialog.api.entities import DIALOG_EVENT_NAME
from aiogram_dialog.api.exceptions import UnknownIntent, UnknownState
from app.bot.dialogs.flows import dialogs
from app.bot.handlers import routers
from app.bot.handlers.errors import on_unknown_intent, on_unknown_state
from app.bot.middlewares.database import DataBaseMiddleware
from app.bot.middlewares.get_user import GetUserMiddleware
from app.bot.middlewares.shadow_ban import ShadowBanMiddleware
from app.bot.middlewares.i18n import TranslatorRunnerMiddleware
from app.bot.middlewares.registration_guard import RegistrationGuardMiddleware
from app.bot.i18n.translator_hub import create_translator_hub
from fluentogram import TranslatorHub
from app.infrastructure.cache.connect_to_redis import get_redis_pool
from app.infrastructure.database.connection.psycopg_connection import PsycopgConnection
from app.infrastructure.database.db import DB
from app.infrastructure.database.connection.connect_to_pg import get_pg_pool
from app.infrastructure.storage.nats_connect import connect_to_nats
from app.infrastructure.storage.storage.nats_storage import NatsStorage
from app.services.backend import BackendDocumentsClient
from app.services.delay_service.start_consumer import start_delayed_consumer
from app.services.scheduler.taskiq_broker import broker, redis_source
from app.services.i18n.bootstrap import ensure_languages, load_translations
from app.bot.handlers.comitee import rebuild_menu_texts
from app.bot.keyboards.menu_button import get_main_menu_commands
from config.config import settings
from app.bot.enums.roles import UserRole
from app.services.i18n.localization import get_text

logger = logging.getLogger(__name__)


def _as_int(value: object, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except Exception:
        return default


def _as_float(value: object, default: float) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except Exception:
        return default


class RuntimeProbeMiddleware(BaseMiddleware):
    def __init__(self, runtime_state: dict[str, float | int]) -> None:
        super().__init__()
        self._runtime_state = runtime_state

    async def __call__(self, handler, event: Update, data):
        self._runtime_state["last_update_monotonic"] = time.monotonic()
        updates_total = int(self._runtime_state.get("updates_total", 0)) + 1
        self._runtime_state["updates_total"] = updates_total
        if updates_total % 100 == 0:
            logger.info("Processed %s updates", updates_total)
        return await handler(event, data)


async def _init_db_pool_with_retry() -> psycopg_pool.AsyncConnectionPool:
    retry_delay = 5
    max_retry_delay = 60
    pool_min_size = _as_int(getattr(settings, "postgres_pool_min_size", 2), 2)
    pool_max_size = _as_int(getattr(settings, "postgres_pool_max_size", 12), 12)
    pool_timeout = _as_float(getattr(settings, "postgres_pool_timeout", 30.0), 30.0)

    logger.info(
        "Initializing PostgreSQL pool (min_size=%s, max_size=%s, timeout=%ss)",
        pool_min_size,
        pool_max_size,
        pool_timeout,
    )

    while True:
        try:
            return await get_pg_pool(
                db_name=settings.postgres.name,
                host=settings.postgres.host,
                port=settings.postgres.port,
                user=settings.postgres_user,
                password=settings.postgres_password,
                min_size=pool_min_size,
                max_size=pool_max_size,
                timeout=pool_timeout,
            )
        except Exception:
            logger.exception(
                "Failed to initialize PostgreSQL pool. Retrying in %s seconds...",
                retry_delay,
            )
            await asyncio.sleep(retry_delay)
            retry_delay = min(max_retry_delay, retry_delay * 2)


async def main():
    logger.info("Starting bot")

    nc = None
    js = None
    cache_pool: redis.asyncio.Redis | None = None
    backend_client: BackendDocumentsClient | None = None

    if settings.features.enable_nats:
        nc, js = await connect_to_nats(servers=settings.nats.servers)
        storage = await NatsStorage(
            nc=nc, js=js, key_builder=DefaultKeyBuilder(with_destiny=True, separator=".")
        ).create_storage()
    else:
        storage = MemoryStorage()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode(settings.bot.parse_mode)),
    )
    dp = Dispatcher(storage=storage)
    runtime_state: dict[str, float | int] = {
        "started_monotonic": time.monotonic(),
        "last_update_monotonic": time.monotonic(),
        "updates_total": 0,
    }
    if settings.cache.use_cache:
        cache_pool = await get_redis_pool(
            db=settings.redis.database,
            host=settings.redis.host,
            port=settings.redis.port,
            username=settings.redis_username,
            password=settings.redis_password,
        )
        dp.workflow_data.update(_cache_pool=cache_pool)

    raw_locales = getattr(settings.i18n, "locales", [])
    configured_locales: list[str] = []
    for code in raw_locales:
        normalized = (code or "").strip().lower()
        if not normalized:
            continue
        if normalized not in configured_locales:
            configured_locales.append(normalized)
    if "dev" not in configured_locales:
        configured_locales.append("dev")

    db_pool: psycopg_pool.AsyncConnectionPool = await _init_db_pool_with_retry()

    async with db_pool.connection() as raw_connection:
        async with raw_connection.transaction():
            connection = PsycopgConnection(raw_connection)
            db = DB(connection=connection)
            await db.documents.ensure_schema()
            await db.contracts.ensure_schema()
            await db.court_cases.ensure_schema()
            await db.meetings.ensure_schema()
            await db.good_deeds.ensure_schema()
            await db.shariah_admin_applications.ensure_schema()
            await ensure_languages(
                db=db,
                locales=configured_locales,
                default_locale=getattr(settings.i18n, "default_locale", None),
            )
            await load_translations(db=db)
            # Rebuild menu labels with DB-backed translations
            try:
                rebuild_menu_texts(configured_locales)
            except Exception:
                logger.exception("Failed to rebuild menu texts")

            # Ensure ADMIN_IDS are present as admin users
            try:
                raw_ids = getattr(settings, "ADMIN_IDS", [])
                if not isinstance(raw_ids, (list, tuple, set)):
                    raw_ids = str(raw_ids).replace(";", ",").split(",") if raw_ids else []
                admin_ids: list[int] = []
                for item in raw_ids:
                    try:
                        admin_ids.append(int(str(item).strip()))
                    except Exception:
                        continue
                # Seed/update each admin user (idempotent: check existence first)
                for admin_id in admin_ids:
                    try:
                        existing = await db.users.get_user(user_id=admin_id)
                        if existing is None:
                            await db.users.add(
                                user_id=admin_id,
                                language_code=None,
                                role=UserRole.ADMIN,
                                full_name=None,
                                email=None,
                                phone_number=None,
                                is_alive=True,
                                banned=False,
                            )
                        # Ensure role/flags on every start
                        await db.users.set_role(user_id=admin_id, role=UserRole.ADMIN)
                        await db.users.update_alive_status(user_id=admin_id, is_alive=True)
                        await db.users.update_banned_status(user_id=admin_id, banned=False)
                    except Exception:
                        logger.exception("Failed to ensure admin user %s", admin_id)
            except Exception:
                logger.exception("Failed to process ADMIN_IDS seeding")

    async def _set_main_menu_commands() -> None:
        languages = [code for code in configured_locales if code != "dev"]
        default_locale = getattr(settings.i18n, "default_locale", None)
        default_lang = (default_locale or "ru").strip().lower()
        if default_lang == "dev":
            default_lang = "ru"
        if default_lang not in languages:
            languages.append(default_lang)

        try:
            await bot.set_my_commands(get_main_menu_commands(default_lang))
        except Exception:
            logger.exception("Failed to set default bot commands")

        for lang in languages:
            try:
                await bot.set_my_commands(
                    get_main_menu_commands(lang),
                    language_code=lang,
                )
            except Exception:
                logger.exception("Failed to set bot commands for %s", lang)

    await _set_main_menu_commands()

    backend_settings = getattr(settings, "backend", None)
    if backend_settings is not None:
        base_url = getattr(backend_settings, "base_url", None)
        admin_email = getattr(backend_settings, "admin_email", None)
        admin_password = getattr(backend_settings, "admin_password", None)
        if base_url and admin_email and admin_password:
            try:
                backend_client = BackendDocumentsClient(
                    base_url=base_url,
                    admin_email=admin_email,
                    admin_password=admin_password,
                )
                bot.backend_documents_client = backend_client  # type: ignore[attr-defined]
            except ValueError as exc:
                logger.warning("Backend documents client disabled: %s", exc)
        else:
            logger.warning(
                "Backend documents client disabled due to missing configuration."
            )

    translator_hub: TranslatorHub = create_translator_hub()

    workflow_context = {
        "bot_locales": configured_locales,
        "translator_hub": translator_hub,
        "db_pool": db_pool,
    }
    if backend_client is not None:
        workflow_context["backend_documents_client"] = backend_client
    if redis_source is not None:
        workflow_context["redis_source"] = redis_source

    dp.workflow_data.update(workflow_context)

    logger.info("Registering error handlers")
    dp.errors.register(
        on_unknown_intent,
        ExceptionTypeFilter(UnknownIntent),
    )
    dp.errors.register(
        on_unknown_state,
        ExceptionTypeFilter(UnknownState),
    )

    logger.info("Including routers")
    dp.include_routers(*routers)

    logger.info("Including dialogs")
    dp.include_routers(*dialogs)

    logger.info("Including middlewares")
    dp.update.middleware(RuntimeProbeMiddleware(runtime_state))
    dp.update.middleware(DataBaseMiddleware())
    dp.update.middleware(GetUserMiddleware())
    dp.update.middleware(RegistrationGuardMiddleware())
    dp.update.middleware(ShadowBanMiddleware())
    dp.update.middleware(TranslatorRunnerMiddleware())

    logger.info("Including error middlewares")
    dp.errors.middleware(DataBaseMiddleware())
    dp.errors.middleware(GetUserMiddleware())
    dp.errors.middleware(RegistrationGuardMiddleware())
    dp.errors.middleware(ShadowBanMiddleware())
    dp.errors.middleware(TranslatorRunnerMiddleware())

    logger.info("Setting up dialogs")
    bg_factory = setup_dialogs(dp)

    logger.info("Including observers middlewares")
    dp.observers[DIALOG_EVENT_NAME].outer_middleware(DataBaseMiddleware())
    dp.observers[DIALOG_EVENT_NAME].outer_middleware(GetUserMiddleware())
    dp.observers[DIALOG_EVENT_NAME].outer_middleware(RegistrationGuardMiddleware())
    dp.observers[DIALOG_EVENT_NAME].outer_middleware(ShadowBanMiddleware())
    dp.observers[DIALOG_EVENT_NAME].outer_middleware(TranslatorRunnerMiddleware())

    logger.info("Starting taskiq broker")
    await broker.startup()

    # Launch polling and delayed message consumer
    try:
        polling_kwargs = {"bg_factory": bg_factory}
        if js is not None:
            polling_kwargs.update(
                js=js,
                delay_del_subject=settings.nats.delayed_consumer_subject,
            )

        watchdog_interval_sec = _as_int(getattr(settings, "bot_watchdog_interval_sec", 30), 30)
        watchdog_max_failures = _as_int(getattr(settings, "bot_watchdog_max_failures", 4), 4)
        stale_updates_warning_sec = _as_int(
            getattr(settings, "bot_stale_updates_warning_sec", 900),
            900,
        )
        watchdog_timeout_sec = _as_float(getattr(settings, "bot_watchdog_timeout_sec", 10), 10)

        async def _ping_database() -> None:
            async with db_pool.connection() as _raw:
                conn = PsycopgConnection(_raw)
                await conn.fetchone(sql="SELECT 1")

        async def polling_worker() -> None:
            restart_delay = 1
            max_restart_delay = 30
            while True:
                try:
                    # Polling mode must clear webhook mode explicitly.
                    await bot.delete_webhook(drop_pending_updates=False)
                    logger.info("Webhook disabled. Starting Telegram long polling.")
                    await dp.start_polling(
                        bot,
                        **polling_kwargs,
                    )
                    logger.warning(
                        "Polling loop finished without exception. Restarting in %s seconds.",
                        restart_delay,
                    )
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception(
                        "Polling loop crashed. Restarting in %s seconds.",
                        restart_delay,
                    )
                await asyncio.sleep(restart_delay)
                restart_delay = min(max_restart_delay, restart_delay * 2)

        async def liveness_watchdog_worker() -> None:
            tg_failures = 0
            db_failures = 0
            while True:
                since_last_update = time.monotonic() - float(
                    runtime_state.get("last_update_monotonic", time.monotonic())
                )
                updates_total = int(runtime_state.get("updates_total", 0))

                try:
                    await asyncio.wait_for(bot.get_me(), timeout=watchdog_timeout_sec)
                    tg_failures = 0
                except asyncio.CancelledError:
                    raise
                except Exception:
                    tg_failures += 1
                    logger.exception(
                        "Watchdog: Telegram API check failed (%s/%s).",
                        tg_failures,
                        watchdog_max_failures,
                    )

                try:
                    await asyncio.wait_for(_ping_database(), timeout=watchdog_timeout_sec)
                    db_failures = 0
                except asyncio.CancelledError:
                    raise
                except Exception:
                    db_failures += 1
                    logger.exception(
                        "Watchdog: database check failed (%s/%s).",
                        db_failures,
                        watchdog_max_failures,
                    )

                if since_last_update >= stale_updates_warning_sec:
                    logger.warning(
                        "Watchdog: no updates for %.0f sec (processed=%s).",
                        since_last_update,
                        updates_total,
                    )
                else:
                    logger.info(
                        "Watchdog heartbeat: processed=%s, last_update_ago=%.0fs.",
                        updates_total,
                        since_last_update,
                    )

                if tg_failures >= watchdog_max_failures or db_failures >= watchdog_max_failures:
                    raise RuntimeError(
                        "Watchdog triggered restart due to repeated Telegram/DB connectivity failures."
                    )

                await asyncio.sleep(watchdog_interval_sec)

        async def notifications_worker():
            # Periodically poll backend.notifications and send messages
            while True:
                notifications: list[dict[str, object]] = []
                try:
                    async with db_pool.connection() as _raw:
                        async with _raw.transaction():
                            conn = PsycopgConnection(_raw)
                            rows = await conn.fetchmany(
                                sql=(
                                    """
                                    SELECT
                                        n.id,
                                        n.user_id,
                                        n.kind,
                                        n.payload,
                                        (
                                            SELECT l.code
                                            FROM users AS u
                                            LEFT JOIN languages AS l ON l.id = u.language_id
                                            WHERE u.user_id = n.user_id
                                        ) AS language_code
                                    FROM notifications AS n
                                    WHERE n.sent_at IS NULL
                                    ORDER BY n.created_at ASC
                                    FOR UPDATE SKIP LOCKED
                                    LIMIT 50
                                    """
                                )
                            )
                            notifications = rows.as_dicts()
                            ids_to_mark = [
                                int(row["id"])
                                for row in notifications
                                if row.get("id") is not None
                            ]
                            if ids_to_mark:
                                await conn.execute(
                                    sql="UPDATE notifications SET sent_at = NOW() WHERE id = ANY(%s)",
                                    params=(ids_to_mark,),
                                )
                except Exception:
                    logger.exception("notifications_worker cycle failed")
                    notifications = []

                for row in notifications:
                    uid = row.get("user_id")
                    lang = (row.get("language_code") or "ru").strip().lower()
                    kind = (row.get("kind") or "").strip()
                    raw_payload = row.get("payload")
                    text = None
                    if kind == "user_unbanned":
                        text = get_text("notify.unban.user", lang)
                    elif kind in {"admin_tasks_reminder", "admin_message"}:
                        if isinstance(raw_payload, str) and raw_payload.strip():
                            try:
                                payload_obj = json.loads(raw_payload)
                                if isinstance(payload_obj, dict):
                                    text = str(payload_obj.get("text") or "").strip() or raw_payload
                                else:
                                    text = raw_payload
                            except Exception:
                                text = raw_payload
                    if text and uid:
                        try:
                            await bot.send_message(chat_id=int(uid), text=text)
                        except Exception as send_error:
                            logger.debug("Failed to send notification to %s: %s", uid, send_error)
                await asyncio.sleep(5)

        async def voting_close_worker():
            # Close expired votings and create execution cards.
            while True:
                closed_count = 0
                try:
                    async with db_pool.connection() as _raw:
                        async with _raw.transaction():
                            conn = PsycopgConnection(_raw)
                            db = DB(connection=conn)
                            closed = await db.meetings.close_expired_votings()
                            closed_count = len(closed)
                except Exception:
                    logger.exception("voting_close_worker cycle failed")
                if closed_count:
                    logger.info("Closed %s expired votings", closed_count)
                await asyncio.sleep(60)

        async def admin_tasks_reminder_worker():
            # Create periodic reminders for admins (every 6 hours) if they have open work items.
            open_statuses = ("new", "assigned", "in_progress", "waiting_user", "waiting_scholar")
            while True:
                try:
                    async with db_pool.connection() as _raw:
                        async with _raw.transaction():
                            conn = PsycopgConnection(_raw)
                            admin_rows = await conn.fetchmany(
                                sql=(
                                    """
                                    SELECT
                                        a.id AS admin_id,
                                        a.username,
                                        a.telegram_id,
                                        ARRAY_REMOVE(ARRAY_AGG(r.slug), NULL) AS roles
                                    FROM admin_accounts AS a
                                    LEFT JOIN admin_account_roles AS ar ON ar.admin_account_id = a.id
                                    LEFT JOIN roles AS r ON r.id = ar.role_id
                                    WHERE COALESCE(a.is_active, TRUE) = TRUE AND a.telegram_id IS NOT NULL
                                    GROUP BY a.id
                                    """
                                )
                            )
                            admins = admin_rows.as_dicts()
                            for admin in admins:
                                telegram_id = admin.get("telegram_id")
                                admin_id = admin.get("admin_id")
                                roles = admin.get("roles") or []
                                if not telegram_id or not admin_id:
                                    continue
                                role_set = set(str(r).strip() for r in roles if r)
                                if not ({"owner", "superadmin", "admin_work_items_view"} & role_set):
                                    continue
                                topics: list[str] = []
                                if {"owner", "superadmin"} & role_set:
                                    topics = ["nikah", "inheritance", "spouse_search", "courts"]
                                else:
                                    if "tz_nikah" in role_set:
                                        topics.append("nikah")
                                    if "tz_inheritance" in role_set:
                                        topics.append("inheritance")
                                    if "tz_spouse_search" in role_set:
                                        topics.append("spouse_search")
                                    if "tz_courts" in role_set:
                                        topics.append("courts")
                                if not topics:
                                    continue

                                recent = await conn.fetchone(
                                    sql=(
                                        """
                                        SELECT 1
                                        FROM notifications
                                        WHERE user_id = %s
                                          AND kind = 'admin_tasks_reminder'
                                          AND created_at > NOW() - INTERVAL '6 hours'
                                        LIMIT 1
                                        """
                                    ),
                                    params=(int(telegram_id),),
                                )
                                if not recent.is_empty():
                                    continue

                                total_row = await conn.fetchone(
                                    sql=(
                                        """
                                        SELECT COUNT(*) AS cnt
                                        FROM work_items
                                        WHERE status = ANY(%s)
                                          AND (
                                            assignee_admin_id = %s
                                            OR (assignee_admin_id IS NULL AND topic = ANY(%s))
                                          )
                                        """
                                    ),
                                    params=(list(open_statuses), int(admin_id), topics),
                                )
                                total = int((total_row.as_dict().get("cnt") if not total_row.is_empty() else 0) or 0)
                                if total <= 0:
                                    continue

                                per_topic_rows = await conn.fetchmany(
                                    sql=(
                                        """
                                        SELECT topic, COUNT(*) AS cnt
                                        FROM work_items
                                        WHERE status = ANY(%s)
                                          AND (
                                            assignee_admin_id = %s
                                            OR (assignee_admin_id IS NULL AND topic = ANY(%s))
                                          )
                                        GROUP BY topic
                                        """
                                    ),
                                    params=(list(open_statuses), int(admin_id), topics),
                                )
                                per_topic = {str(r.get("topic")): int(r.get("cnt") or 0) for r in per_topic_rows.as_dicts()}
                                parts = [
                                    f"🛠 У вас есть задания: {total}",
                                    f"- 👰🤵 Никях: {per_topic.get('nikah', 0)}",
                                    f"- 🪙 Наследство: {per_topic.get('inheritance', 0)}",
                                    f"- 🌿 Знакомство: {per_topic.get('spouse_search', 0)}",
                                    f"- ⚖️ Суд: {per_topic.get('courts', 0)}",
                                    "",
                                    "Откройте админ-панель → вкладка Tasks/Задания.",
                                ]
                                payload = json.dumps({"text": "\n".join(parts)}, ensure_ascii=False)
                                await conn.execute(
                                    sql="INSERT INTO notifications(user_id, kind, payload) VALUES(%s,%s,%s)",
                                    params=(int(telegram_id), "admin_tasks_reminder", payload),
                                )
                except Exception:
                    logger.exception("admin_tasks_reminder_worker cycle failed")
                await asyncio.sleep(21600)

        tasks = [
            polling_worker(),
            liveness_watchdog_worker(),
            notifications_worker(),
            voting_close_worker(),
            admin_tasks_reminder_worker(),
        ]

        if js is not None and nc is not None and settings.features.enable_nats:
            tasks.append(
                start_delayed_consumer(
                    nc=nc,
                    js=js,
                    bot=bot,
                    subject=settings.nats.delayed_consumer_subject,
                    stream=settings.nats.delayed_consumer_stream,
                    durable_name=settings.nats.delayed_consumer_durable_name,
                )
            )

        await asyncio.gather(*tasks)
    except Exception:
        logger.exception("Bot main loop terminated with an error")
    finally:
        if backend_client is not None:
            await backend_client.close()
            logger.info("Backend documents client closed")
        if nc is not None:
            await nc.close()
            logger.info("Connection to NATS closed")
        await db_pool.close()
        logger.info("Connection to Postgres closed")
        await broker.shutdown()
        logger.info("Connection to taskiq-broker closed")
        if cache_pool is not None:
            await cache_pool.close()
            logger.info("Connection to Redis closed")
