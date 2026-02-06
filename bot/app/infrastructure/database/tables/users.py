import asyncio
import logging
from datetime import datetime, timezone
from typing import ClassVar

from app.bot.enums.roles import UserRole
from app.infrastructure.database.connection.base import BaseConnection
from app.infrastructure.database.models.user import UserModel
from app.infrastructure.database.query.results import SingleQueryResult
from app.infrastructure.database.tables.base import BaseTable
from app.infrastructure.database.tables.enums.users import UsersTableAction

logger = logging.getLogger(__name__)


class UsersTable(BaseTable):
    __tablename__ = "users"
    _unban_columns_ready: ClassVar[bool] = False
    _unban_columns_lock: ClassVar[asyncio.Lock | None] = None

    def __init__(self, connection: BaseConnection):
        self.connection = connection

    @classmethod
    def _get_unban_lock(cls) -> asyncio.Lock:
        lock = cls._unban_columns_lock
        if lock is None:
            lock = asyncio.Lock()
            cls._unban_columns_lock = lock
        return lock

    async def _ensure_unban_columns(self) -> None:
        cls = self.__class__

        if cls._unban_columns_ready:
            return

        lock = cls._get_unban_lock()
        async with lock:
            if cls._unban_columns_ready:
                return
            await self.connection.execute(
                sql="ALTER TABLE users ADD COLUMN IF NOT EXISTS unban_request_text TEXT"
            )
            await self.connection.execute(
                sql="ALTER TABLE users ADD COLUMN IF NOT EXISTS unban_requested_at TIMESTAMPTZ"
            )
            cls._unban_columns_ready = True

    async def add(
        self,
        *,
        user_id: int,
        language_code: str | None,
        role: UserRole,
        full_name: str | None,
        email: str | None,
        phone_number: str | None,
        is_alive: bool = True,
        banned: bool = False,
    ) -> None:
        await self.connection.execute(
            sql="""
                INSERT INTO users(
                    user_id,
                    language_id,
                    role,
                    is_alive,
                    banned,
                    full_name,
                    email,
                    phone_number
                )
                VALUES(
                    %s,
                    COALESCE(
                        (SELECT id FROM languages WHERE code = %s),
                        (SELECT id FROM languages WHERE is_default = TRUE LIMIT 1)
                    ),
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                ON CONFLICT DO NOTHING;
            """,
            params=(
                user_id,
                language_code,
                role,
                is_alive,
                banned,
                full_name,
                email,
                phone_number,
            ),
        )
        self._log(
            UsersTableAction.ADD,
            user_id=user_id,
            created_at=datetime.now(timezone.utc),
            language_code=language_code,
            role=role,
            is_alive=is_alive,
            banned=banned,
            full_name=full_name,
            email=email,
            phone_number=phone_number,
        )

    async def delete(self, *, user_id: int) -> None:
        await self.connection.execute(
            sql="""
                DELETE FROM users WHERE user_id = %s;
            """,
            params=(user_id,),
        )
        self._log(UsersTableAction.DELETE, user_id=user_id)

    async def get_user(self, *, user_id: int) -> UserModel | None:
        data: SingleQueryResult = await self.connection.fetchone(
            sql="""
                SELECT 
                    u.id,
                    u.user_id,
                    COALESCE(u.created_at, NOW()) AS created_at,
                    NULL::text AS tz_region,
                    NULL::text AS tz_offset,
                    NULL::double precision AS longitude,
                    NULL::double precision AS latitude,
                    u.full_name,
                    u.email,
                    u.phone_number,
COALESCE(u.email_verified, FALSE) AS email_verified,
COALESCE(u.phone_verified, FALSE) AS phone_verified,
                    u.language_id,
                    l.code AS language_code,
                    u.role,
                    u.is_alive,
                    u.banned
                FROM users AS u
                LEFT JOIN languages AS l ON u.language_id = l.id
                WHERE u.user_id = %s
            """,
            params=(user_id,),
        )
        user_model: UserModel | None = data.to_model(model=UserModel)

        self._log(UsersTableAction.GET_USER, user_id=user_id)

        return user_model

    async def find_users_by_full_name(
        self,
        *,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, object]]:
        pattern = f"%{query.strip()}%"
        result = await self.connection.fetchmany(
            sql="""
                SELECT user_id, full_name
                FROM users
                WHERE full_name ILIKE %s
                ORDER BY full_name
                LIMIT %s
            """,
            params=(pattern, limit),
        )
        return result.as_dicts()

    async def update_alive_status(self, *, user_id: int, is_alive: bool = True) -> None:
        await self.connection.execute(
            sql="""
                UPDATE users
                SET is_alive = %s
                WHERE user_id = %s
            """,
            params=(is_alive, user_id),
        )
        self._log(
            UsersTableAction.UPDATE_ALIVE_STATUS, user_id=user_id, is_alive=is_alive
        )

    async def update_user_lang(self, *, user_id: int, user_lang: str) -> None:
        await self.connection.execute(
            sql="""
                INSERT INTO languages(code, is_default)
                VALUES (%s, FALSE)
                ON CONFLICT (code) DO NOTHING
            """,
            params=(user_lang,),
        )
        await self.connection.execute(
            sql="""
                UPDATE users
                SET language_id = COALESCE(
                    (SELECT id FROM languages WHERE code = %s),
                    (SELECT id FROM languages WHERE is_default = TRUE LIMIT 1)
                )
                WHERE user_id = %s
            """,
            params=(user_lang, user_id),
        )
        self._log(
            UsersTableAction.UPDATE_USER_LANG, user_id=user_id, user_lang=user_lang
        )

    async def update_banned_status(self, *, user_id: int, banned: bool = False) -> None:
        await self.connection.execute(
            sql="""
                UPDATE users
                SET banned = %s
                WHERE user_id = %s
            """,
            params=(banned, user_id),
        )
        self._log(UsersTableAction.UPDATE_BANNED_STATUS, user_id=user_id, banned=banned)

    async def set_role(self, *, user_id: int, role: UserRole) -> None:
        await self.connection.execute(
            sql="""
                UPDATE users
                SET role = %s
                WHERE user_id = %s
            """,
            params=(role, user_id),
        )
        
    async def set_phone_verified(self, *, user_id: int, verified: bool = True) -> None:
        await self.connection.execute(
            sql="""
                UPDATE users
                SET phone_verified = %s
                WHERE user_id = %s
            """,
            params=(verified, user_id),
        )
        self._log(UsersTableAction.UPDATE_ALIVE_STATUS, user_id=user_id)

    async def set_unban_request(self, *, user_id: int, reason: str) -> None:
        await self._ensure_unban_columns()
        await self.connection.execute(
            sql="""
                UPDATE users
                SET unban_request_text = %s,
                    unban_requested_at = NOW()
                WHERE user_id = %s
            """,
            params=(reason, user_id),
        )
        logger.info("Unban request saved for user_id=%s", user_id)



