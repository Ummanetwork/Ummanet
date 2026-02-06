from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Optional

from app.infrastructure.database.query.results import MultipleQueryResult, SingleQueryResult
from app.infrastructure.database.tables.base import BaseTable


class GoodDeedsTable(BaseTable):
    __tablename__ = "good_deeds"

    async def ensure_schema(self) -> None:
        await self.connection.execute(
            sql="""
            CREATE TABLE IF NOT EXISTS good_deeds (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                city TEXT NOT NULL,
                country TEXT NOT NULL,
                help_type TEXT NOT NULL,
                amount NUMERIC NULL,
                comment TEXT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                approved_category TEXT NULL,
                review_comment TEXT NULL,
                reviewed_by_admin_id INTEGER NULL,
                clarification_text TEXT NULL,
                clarification_attachment JSONB NULL,
                history JSONB NOT NULL DEFAULT '[]'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                approved_at TIMESTAMPTZ NULL,
                completed_at TIMESTAMPTZ NULL
            );
            CREATE INDEX IF NOT EXISTS idx_good_deeds_user ON good_deeds(user_id);
            CREATE INDEX IF NOT EXISTS idx_good_deeds_status ON good_deeds(status);
            CREATE INDEX IF NOT EXISTS idx_good_deeds_city ON good_deeds(city);
            CREATE INDEX IF NOT EXISTS idx_good_deeds_country ON good_deeds(country);

            CREATE TABLE IF NOT EXISTS good_deed_needy (
                id SERIAL PRIMARY KEY,
                created_by_user_id BIGINT NOT NULL,
                person_type TEXT NOT NULL,
                city TEXT NOT NULL,
                country TEXT NOT NULL,
                reason TEXT NOT NULL,
                allow_zakat BOOLEAN NOT NULL DEFAULT FALSE,
                allow_fitr BOOLEAN NOT NULL DEFAULT FALSE,
                sadaqa_only BOOLEAN NOT NULL DEFAULT FALSE,
                comment TEXT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                review_comment TEXT NULL,
                reviewed_by_admin_id INTEGER NULL,
                history JSONB NOT NULL DEFAULT '[]'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                approved_at TIMESTAMPTZ NULL
            );
            CREATE INDEX IF NOT EXISTS idx_good_deed_needy_status ON good_deed_needy(status);
            CREATE INDEX IF NOT EXISTS idx_good_deed_needy_city ON good_deed_needy(city);
            CREATE INDEX IF NOT EXISTS idx_good_deed_needy_country ON good_deed_needy(country);

            CREATE TABLE IF NOT EXISTS good_deed_confirmations (
                id SERIAL PRIMARY KEY,
                good_deed_id INTEGER NOT NULL REFERENCES good_deeds(id) ON DELETE CASCADE,
                created_by_user_id BIGINT NOT NULL,
                text TEXT NULL,
                attachment JSONB NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                review_comment TEXT NULL,
                reviewed_by_admin_id INTEGER NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                reviewed_at TIMESTAMPTZ NULL
            );
            CREATE INDEX IF NOT EXISTS idx_good_deed_confirmations_deed ON good_deed_confirmations(good_deed_id);
            CREATE INDEX IF NOT EXISTS idx_good_deed_confirmations_status ON good_deed_confirmations(status);
            """
        )
        await self.connection.execute(
            sql="ALTER TABLE good_deeds ADD COLUMN IF NOT EXISTS clarification_text TEXT"
        )
        await self.connection.execute(
            sql="ALTER TABLE good_deeds ADD COLUMN IF NOT EXISTS clarification_attachment JSONB"
        )
        await self.connection.execute(
            sql="ALTER TABLE good_deeds ADD COLUMN IF NOT EXISTS history JSONB DEFAULT '[]'::jsonb"
        )
        await self.connection.execute(
            sql="ALTER TABLE good_deed_needy ADD COLUMN IF NOT EXISTS history JSONB DEFAULT '[]'::jsonb"
        )
        await self.connection.execute(
            sql="ALTER TABLE good_deed_confirmations ADD COLUMN IF NOT EXISTS attachment JSONB"
        )

    async def create_good_deed(
        self,
        *,
        user_id: int,
        title: str,
        description: str,
        city: str,
        country: str,
        help_type: str,
        amount: Optional[Decimal],
        comment: Optional[str],
        status: str = "pending",
        history_event: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        history_payload = json.dumps([history_event], ensure_ascii=False) if history_event else None
        result: SingleQueryResult = await self.connection.insert_and_fetchone(
            sql=(
                """
                INSERT INTO good_deeds(
                    user_id, title, description, city, country, help_type, amount, comment, status, history
                )
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,COALESCE(%s::jsonb, '[]'::jsonb))
                RETURNING *
                """
            ),
            params=(
                user_id,
                title,
                description,
                city,
                country,
                help_type,
                amount,
                comment,
                status,
                history_payload,
            ),
        )
        return result.as_dict()

    async def update_good_deed(
        self,
        *,
        good_deed_id: int,
        title: str,
        description: str,
        city: str,
        country: str,
        help_type: str,
        amount: Optional[Decimal],
        comment: Optional[str],
    ) -> dict[str, Any] | None:
        result: SingleQueryResult = await self.connection.update_and_fetchone(
            sql=(
                """
                UPDATE good_deeds
                SET title = %s,
                    description = %s,
                    city = %s,
                    country = %s,
                    help_type = %s,
                    amount = %s,
                    comment = %s,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """
            ),
            params=(title, description, city, country, help_type, amount, comment, good_deed_id),
        )
        if result.is_empty():
            return None
        return result.as_dict()

    async def update_good_deed_status(
        self,
        *,
        good_deed_id: int,
        status: str,
        approved_category: Optional[str] = None,
        review_comment: Optional[str] = None,
        reviewed_by_admin_id: Optional[int] = None,
        approved_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> dict[str, Any] | None:
        result: SingleQueryResult = await self.connection.update_and_fetchone(
            sql=(
                """
                UPDATE good_deeds
                SET status = %s,
                    approved_category = COALESCE(%s, approved_category),
                    review_comment = %s,
                    reviewed_by_admin_id = COALESCE(%s, reviewed_by_admin_id),
                    approved_at = COALESCE(%s, approved_at),
                    completed_at = COALESCE(%s, completed_at),
                    updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """
            ),
            params=(
                status,
                approved_category,
                review_comment,
                reviewed_by_admin_id,
                approved_at,
                completed_at,
                good_deed_id,
            ),
        )
        if result.is_empty():
            return None
        return result.as_dict()

    async def update_good_deed_clarification(
        self,
        *,
        good_deed_id: int,
        text: str | None,
        attachment: dict[str, Any] | None,
    ) -> None:
        payload = json.dumps(attachment, ensure_ascii=False) if attachment else None
        await self.connection.execute(
            sql=(
                """
                UPDATE good_deeds
                SET clarification_text = %s,
                    clarification_attachment = %s::jsonb,
                    updated_at = NOW()
                WHERE id = %s
                """
            ),
            params=(text, payload, good_deed_id),
        )

    async def append_good_deed_history(
        self,
        *,
        good_deed_id: int,
        event: dict[str, Any],
    ) -> None:
        payload = json.dumps([event], ensure_ascii=False)
        await self.connection.execute(
            sql=(
                """
                UPDATE good_deeds
                SET history = COALESCE(history, '[]'::jsonb) || %s::jsonb,
                    updated_at = NOW()
                WHERE id = %s
                """
            ),
            params=(payload, good_deed_id),
        )

    async def get_good_deed_by_id(self, *, good_deed_id: int) -> dict[str, Any] | None:
        result: SingleQueryResult = await self.connection.fetchone(
            sql="SELECT * FROM good_deeds WHERE id = %s",
            params=(good_deed_id,),
        )
        if result.is_empty():
            return None
        return result.as_dict()

    async def list_good_deeds_by_user(
        self,
        *,
        user_id: int,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        rows: MultipleQueryResult = await self.connection.fetchmany(
            sql=(
                """
                SELECT *
                FROM good_deeds
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """
            ),
            params=(user_id, limit),
        )
        return rows.as_dicts()

    async def list_public_good_deeds(
        self,
        *,
        statuses: Iterable[str],
        city: Optional[str] = None,
        country: Optional[str] = None,
        approved_category: Optional[str] = None,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        filters = ["status = ANY(%s)"]
        params: list[Any] = [list(statuses)]
        if city:
            filters.append("LOWER(city) LIKE LOWER(%s)")
            params.append(f"%{city}%")
        if country:
            filters.append("LOWER(country) LIKE LOWER(%s)")
            params.append(f"%{country}%")
        if approved_category:
            filters.append("approved_category = %s")
            params.append(approved_category)
        sql = "SELECT * FROM good_deeds"
        if filters:
            sql += " WHERE " + " AND ".join(filters)
        sql += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        rows: MultipleQueryResult = await self.connection.fetchmany(sql=sql, params=tuple(params))
        return rows.as_dicts()

    async def search_public_good_deeds_by_location(
        self,
        *,
        statuses: Iterable[str],
        query: str,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        trimmed = (query or "").strip()
        if not trimmed:
            return []
        rows: MultipleQueryResult = await self.connection.fetchmany(
            sql=(
                """
                SELECT *
                FROM good_deeds
                WHERE status = ANY(%s)
                  AND (
                    LOWER(city) LIKE LOWER(%s)
                    OR LOWER(country) LIKE LOWER(%s)
                  )
                ORDER BY created_at DESC
                LIMIT %s
                """
            ),
            params=(list(statuses), f"%{trimmed}%", f"%{trimmed}%", limit),
        )
        return rows.as_dicts()

    async def create_needy(
        self,
        *,
        created_by_user_id: int,
        person_type: str,
        city: str,
        country: str,
        reason: str,
        allow_zakat: bool,
        allow_fitr: bool,
        sadaqa_only: bool,
        comment: Optional[str],
        status: str = "pending",
        history_event: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        history_payload = json.dumps([history_event], ensure_ascii=False) if history_event else None
        result: SingleQueryResult = await self.connection.insert_and_fetchone(
            sql=(
                """
                INSERT INTO good_deed_needy(
                    created_by_user_id, person_type, city, country, reason,
                    allow_zakat, allow_fitr, sadaqa_only, comment, status, history
                )
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,COALESCE(%s::jsonb, '[]'::jsonb))
                RETURNING *
                """
            ),
            params=(
                created_by_user_id,
                person_type,
                city,
                country,
                reason,
                allow_zakat,
                allow_fitr,
                sadaqa_only,
                comment,
                status,
                history_payload,
            ),
        )
        return result.as_dict()

    async def list_needy(
        self,
        *,
        statuses: Iterable[str],
        city: Optional[str] = None,
        country: Optional[str] = None,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        filters = ["status = ANY(%s)"]
        params: list[Any] = [list(statuses)]
        if city:
            filters.append("LOWER(city) LIKE LOWER(%s)")
            params.append(f"%{city}%")
        if country:
            filters.append("LOWER(country) LIKE LOWER(%s)")
            params.append(f"%{country}%")
        sql = "SELECT * FROM good_deed_needy"
        if filters:
            sql += " WHERE " + " AND ".join(filters)
        sql += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        rows: MultipleQueryResult = await self.connection.fetchmany(sql=sql, params=tuple(params))
        return rows.as_dicts()

    async def get_needy_by_id(self, *, needy_id: int) -> dict[str, Any] | None:
        result: SingleQueryResult = await self.connection.fetchone(
            sql="SELECT * FROM good_deed_needy WHERE id = %s",
            params=(needy_id,),
        )
        if result.is_empty():
            return None
        return result.as_dict()

    async def update_needy_status(
        self,
        *,
        needy_id: int,
        status: str,
        review_comment: Optional[str] = None,
        reviewed_by_admin_id: Optional[int] = None,
        approved_at: Optional[datetime] = None,
    ) -> dict[str, Any] | None:
        result: SingleQueryResult = await self.connection.update_and_fetchone(
            sql=(
                """
                UPDATE good_deed_needy
                SET status = %s,
                    review_comment = %s,
                    reviewed_by_admin_id = COALESCE(%s, reviewed_by_admin_id),
                    approved_at = COALESCE(%s, approved_at),
                    updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """
            ),
            params=(status, review_comment, reviewed_by_admin_id, approved_at, needy_id),
        )
        if result.is_empty():
            return None
        return result.as_dict()

    async def append_needy_history(self, *, needy_id: int, event: dict[str, Any]) -> None:
        payload = json.dumps([event], ensure_ascii=False)
        await self.connection.execute(
            sql=(
                """
                UPDATE good_deed_needy
                SET history = COALESCE(history, '[]'::jsonb) || %s::jsonb,
                    updated_at = NOW()
                WHERE id = %s
                """
            ),
            params=(payload, needy_id),
        )

    async def create_confirmation(
        self,
        *,
        good_deed_id: int,
        created_by_user_id: int,
        text: Optional[str],
        attachment: dict[str, Any] | None,
        status: str = "pending",
    ) -> dict[str, Any]:
        payload = json.dumps(attachment, ensure_ascii=False) if attachment else None
        result: SingleQueryResult = await self.connection.insert_and_fetchone(
            sql=(
                """
                INSERT INTO good_deed_confirmations(
                    good_deed_id, created_by_user_id, text, attachment, status
                )
                VALUES(%s,%s,%s,%s::jsonb,%s)
                RETURNING *
                """
            ),
            params=(good_deed_id, created_by_user_id, text, payload, status),
        )
        return result.as_dict()

    async def list_confirmations(
        self,
        *,
        statuses: Iterable[str],
        good_deed_id: Optional[int] = None,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        filters = ["status = ANY(%s)"]
        params: list[Any] = [list(statuses)]
        if good_deed_id:
            filters.append("good_deed_id = %s")
            params.append(good_deed_id)
        sql = "SELECT * FROM good_deed_confirmations"
        if filters:
            sql += " WHERE " + " AND ".join(filters)
        sql += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        rows: MultipleQueryResult = await self.connection.fetchmany(sql=sql, params=tuple(params))
        return rows.as_dicts()

    async def get_confirmation_by_id(self, *, confirmation_id: int) -> dict[str, Any] | None:
        result: SingleQueryResult = await self.connection.fetchone(
            sql="SELECT * FROM good_deed_confirmations WHERE id = %s",
            params=(confirmation_id,),
        )
        if result.is_empty():
            return None
        return result.as_dict()

    async def update_confirmation_status(
        self,
        *,
        confirmation_id: int,
        status: str,
        review_comment: Optional[str] = None,
        reviewed_by_admin_id: Optional[int] = None,
        reviewed_at: Optional[datetime] = None,
    ) -> dict[str, Any] | None:
        result: SingleQueryResult = await self.connection.update_and_fetchone(
            sql=(
                """
                UPDATE good_deed_confirmations
                SET status = %s,
                    review_comment = %s,
                    reviewed_by_admin_id = COALESCE(%s, reviewed_by_admin_id),
                    reviewed_at = COALESCE(%s, reviewed_at),
                    updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """
            ),
            params=(status, review_comment, reviewed_by_admin_id, reviewed_at, confirmation_id),
        )
        if result.is_empty():
            return None
        return result.as_dict()

    @staticmethod
    def serialize_attachment(
        *,
        file_id: str | None,
        filename: str | None,
        mime_type: str | None,
        link: str | None,
        caption: str | None = None,
    ) -> dict[str, Any] | None:
        if not file_id and not link and not caption:
            return None
        return {
            "file_id": file_id,
            "filename": filename,
            "mime_type": mime_type,
            "link": link,
            "caption": caption,
        }

    @staticmethod
    def now_ts() -> datetime:
        return datetime.now(timezone.utc)
