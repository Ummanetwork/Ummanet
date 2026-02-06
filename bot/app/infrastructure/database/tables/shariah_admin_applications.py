from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from app.infrastructure.database.query.results import MultipleQueryResult, SingleQueryResult
from app.infrastructure.database.tables.base import BaseTable


class ShariahAdminApplicationsTable(BaseTable):
    __tablename__ = "shariah_admin_applications"

    async def ensure_schema(self) -> None:
        await self.connection.execute(
            sql="""
            CREATE TABLE IF NOT EXISTS shariah_admin_applications (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                full_name TEXT NOT NULL,
                country TEXT NOT NULL,
                city TEXT NOT NULL,
                education_place TEXT NOT NULL,
                education_completed BOOLEAN NOT NULL DEFAULT FALSE,
                education_details TEXT NULL,
                knowledge_areas JSONB NULL,
                experience TEXT NULL,
                responsibility_accepted BOOLEAN NOT NULL DEFAULT FALSE,
                status TEXT NOT NULL DEFAULT 'pending_intro',
                meeting_type TEXT NULL,
                meeting_link TEXT NULL,
                meeting_at TIMESTAMPTZ NULL,
                decision_comment TEXT NULL,
                decision_by_admin_id INTEGER NULL,
                assigned_roles JSONB NULL,
                history JSONB NOT NULL DEFAULT '[]'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_shariah_admin_user ON shariah_admin_applications(user_id);
            CREATE INDEX IF NOT EXISTS idx_shariah_admin_status ON shariah_admin_applications(status);
            """
        )
        await self.connection.execute(
            sql="ALTER TABLE shariah_admin_applications ADD COLUMN IF NOT EXISTS knowledge_areas JSONB"
        )
        await self.connection.execute(
            sql="ALTER TABLE shariah_admin_applications ADD COLUMN IF NOT EXISTS assigned_roles JSONB"
        )
        await self.connection.execute(
            sql="ALTER TABLE shariah_admin_applications ADD COLUMN IF NOT EXISTS history JSONB DEFAULT '[]'::jsonb"
        )

    async def create_application(
        self,
        *,
        user_id: int,
        full_name: str,
        country: str,
        city: str,
        education_place: str,
        education_completed: bool,
        education_details: Optional[str],
        knowledge_areas: list[str],
        experience: Optional[str],
        responsibility_accepted: bool,
        status: str,
        history_event: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        history_payload = json.dumps([history_event], ensure_ascii=False) if history_event else None
        areas_payload = json.dumps(knowledge_areas, ensure_ascii=False)
        result: SingleQueryResult = await self.connection.insert_and_fetchone(
            sql=(
                """
                INSERT INTO shariah_admin_applications(
                    user_id,
                    full_name,
                    country,
                    city,
                    education_place,
                    education_completed,
                    education_details,
                    knowledge_areas,
                    experience,
                    responsibility_accepted,
                    status,
                    history
                )
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,COALESCE(%s::jsonb, '[]'::jsonb))
                RETURNING *
                """
            ),
            params=(
                user_id,
                full_name,
                country,
                city,
                education_place,
                education_completed,
                education_details,
                areas_payload,
                experience,
                responsibility_accepted,
                status,
                history_payload,
            ),
        )
        return result.as_dict()

    async def update_application_status(
        self,
        *,
        application_id: int,
        status: str,
        decision_comment: Optional[str] = None,
    ) -> None:
        await self.connection.execute(
            sql=(
                """
                UPDATE shariah_admin_applications
                SET status = %s,
                    decision_comment = %s,
                    updated_at = NOW()
                WHERE id = %s
                """
            ),
            params=(status, decision_comment, application_id),
        )

    async def append_history(self, *, application_id: int, event: dict[str, Any]) -> None:
        payload = json.dumps([event], ensure_ascii=False)
        await self.connection.execute(
            sql=(
                """
                UPDATE shariah_admin_applications
                SET history = COALESCE(history, '[]'::jsonb) || %s::jsonb,
                    updated_at = NOW()
                WHERE id = %s
                """
            ),
            params=(payload, application_id),
        )

    async def get_latest_by_user(self, *, user_id: int) -> dict[str, Any] | None:
        result: SingleQueryResult = await self.connection.fetchone(
            sql=(
                """
                SELECT *
                FROM shariah_admin_applications
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            params=(user_id,),
        )
        if result.is_empty():
            return None
        return result.as_dict()

    async def get_by_id(self, *, application_id: int) -> dict[str, Any] | None:
        result: SingleQueryResult = await self.connection.fetchone(
            sql="SELECT * FROM shariah_admin_applications WHERE id = %s",
            params=(application_id,),
        )
        if result.is_empty():
            return None
        return result.as_dict()

    async def list_by_user(self, *, user_id: int, limit: int = 20) -> list[dict[str, Any]]:
        rows: MultipleQueryResult = await self.connection.fetchmany(
            sql=(
                """
                SELECT *
                FROM shariah_admin_applications
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """
            ),
            params=(user_id, limit),
        )
        return rows.as_dicts()

    @staticmethod
    def now_ts() -> datetime:
        return datetime.now(timezone.utc)
