from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Iterable, Optional

from app.infrastructure.database.tables.base import BaseTable
from app.infrastructure.database.query.results import MultipleQueryResult, SingleQueryResult


class CourtCasesTable(BaseTable):
    __tablename__ = "court_cases"

    async def ensure_schema(self) -> None:
        await self.connection.execute(
            sql="""
            CREATE TABLE IF NOT EXISTS court_cases (
                id SERIAL PRIMARY KEY,
                case_number TEXT UNIQUE,
                user_id BIGINT NOT NULL,
                plaintiff_id BIGINT NOT NULL,
                defendant_id BIGINT NULL,
                participants BIGINT[] NOT NULL DEFAULT '{}'::bigint[],
                invite_code TEXT NULL,
                category TEXT NOT NULL,
                plaintiff TEXT NOT NULL,
                defendant TEXT NOT NULL,
                claim TEXT NOT NULL,
                amount NUMERIC NULL,
                evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
                mediate_log JSONB NOT NULL DEFAULT '[]'::jsonb,
                status TEXT NOT NULL,
                sent_to_scholar BOOLEAN NOT NULL DEFAULT FALSE,
                responsible_admin_id INTEGER NULL,
                scholar_id TEXT NULL,
                scholar_name TEXT NULL,
                scholar_contact TEXT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_court_cases_user ON court_cases(user_id);
            CREATE INDEX IF NOT EXISTS idx_court_cases_status ON court_cases(status);
            """
        )
        await self.connection.execute(
            sql="ALTER TABLE court_cases ADD COLUMN IF NOT EXISTS case_number TEXT"
        )
        await self.connection.execute(
            sql="ALTER TABLE court_cases ADD COLUMN IF NOT EXISTS plaintiff_id BIGINT"
        )
        await self.connection.execute(
            sql="ALTER TABLE court_cases ADD COLUMN IF NOT EXISTS defendant_id BIGINT"
        )
        await self.connection.execute(
            sql="ALTER TABLE court_cases ADD COLUMN IF NOT EXISTS participants BIGINT[] DEFAULT '{}'::bigint[]"
        )
        await self.connection.execute(
            sql="ALTER TABLE court_cases ADD COLUMN IF NOT EXISTS invite_code TEXT"
        )
        await self.connection.execute(
            sql="ALTER TABLE court_cases ADD COLUMN IF NOT EXISTS scholar_name TEXT"
        )
        await self.connection.execute(
            sql="ALTER TABLE court_cases ADD COLUMN IF NOT EXISTS scholar_contact TEXT"
        )
        await self.connection.execute(
            sql="ALTER TABLE court_cases ADD COLUMN IF NOT EXISTS sent_to_scholar BOOLEAN DEFAULT FALSE"
        )
        await self.connection.execute(
            sql="ALTER TABLE court_cases ADD COLUMN IF NOT EXISTS responsible_admin_id INTEGER"
        )
        await self.connection.execute(
            sql="ALTER TABLE court_cases ADD COLUMN IF NOT EXISTS evidence JSONB DEFAULT '[]'::jsonb"
        )
        await self.connection.execute(
            sql="ALTER TABLE court_cases ADD COLUMN IF NOT EXISTS mediate_log JSONB DEFAULT '[]'::jsonb"
        )
        await self.connection.execute(
            sql="CREATE INDEX IF NOT EXISTS idx_court_cases_invite_code ON court_cases(invite_code)"
        )
        await self.connection.execute(
            sql=(
                """
                UPDATE court_cases
                SET plaintiff_id = user_id
                WHERE plaintiff_id IS NULL
                """
            )
        )
        await self.connection.execute(
            sql=(
                """
                UPDATE court_cases
                SET participants = ARRAY[user_id]
                WHERE participants IS NULL
                   OR array_length(participants, 1) IS NULL
                """
            )
        )

    async def create_case(
        self,
        *,
        user_id: int,
        plaintiff_id: int,
        invite_code: str | None,
        category: str,
        plaintiff: str,
        defendant: str,
        claim: str,
        amount: Optional[Decimal],
        evidence: list[dict[str, Any]],
        status: str = "open",
        scholar_id: str | None = None,
        sent_to_scholar: bool = False,
    ) -> dict[str, Any]:
        result: SingleQueryResult = await self.connection.insert_and_fetchone(
            sql=(
                """
                INSERT INTO court_cases(
                    case_number, user_id, plaintiff_id, defendant_id, participants, invite_code,
                    category, plaintiff, defendant, claim, amount, evidence, status,
                    sent_to_scholar, scholar_id
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id, created_at
                """
            ),
            params=(
                None,
                user_id,
                plaintiff_id,
                None,
                [plaintiff_id],
                invite_code,
                category,
                plaintiff,
                defendant,
                claim,
                amount,
                json.dumps(evidence, ensure_ascii=False),
                status,
                sent_to_scholar,
                scholar_id,
            ),
        )
        row = result.as_dict()
        case_id = int(row.get("id") or 0)
        year = datetime.utcnow().year
        case_number = f"{year}-{case_id:06d}" if case_id else f"{year}-000000"
        updated: SingleQueryResult = await self.connection.update_and_fetchone(
            sql=(
                """
                UPDATE court_cases
                SET case_number = %s, updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """
            ),
            params=(case_number, case_id),
        )
        return updated.as_dict()

    async def get_case_by_id(
        self,
        *,
        case_id: int,
        user_id: Optional[int] = None,
    ) -> dict[str, Any] | None:
        if user_id is None:
            result: SingleQueryResult = await self.connection.fetchone(
                sql="SELECT * FROM court_cases WHERE id = %s",
                params=(case_id,),
            )
        else:
            result = await self.connection.fetchone(
                sql=(
                    """
                    SELECT *
                    FROM court_cases
                    WHERE id = %s
                      AND (
                        %s = ANY(COALESCE(participants, '{}'::bigint[]))
                        OR user_id = %s
                        OR plaintiff_id = %s
                        OR defendant_id = %s
                      )
                    """
                ),
                params=(case_id, user_id, user_id, user_id, user_id),
            )
        if result.is_empty():
            return None
        return result.as_dict()

    async def list_cases_by_status(
        self,
        *,
        user_id: int,
        statuses: Iterable[str],
    ) -> list[dict[str, Any]]:
        status_list = list(statuses)
        if not status_list:
            return []
        result: MultipleQueryResult = await self.connection.fetchmany(
            sql=(
                """
                SELECT *
                FROM court_cases
                WHERE status = ANY(%s)
                  AND (
                    %s = ANY(COALESCE(participants, '{}'::bigint[]))
                    OR user_id = %s
                    OR plaintiff_id = %s
                    OR defendant_id = %s
                  )
                ORDER BY created_at DESC
                """
            ),
            params=(status_list, user_id, user_id, user_id, user_id),
        )
        return result.as_dicts()

    async def get_case_by_invite_code(self, *, invite_code: str) -> dict[str, Any] | None:
        result: SingleQueryResult = await self.connection.fetchone(
            sql="SELECT * FROM court_cases WHERE invite_code = %s",
            params=(invite_code,),
        )
        if result.is_empty():
            return None
        return result.as_dict()

    async def attach_defendant(
        self,
        *,
        case_id: int,
        defendant_id: int,
    ) -> dict[str, Any] | None:
        result: SingleQueryResult = await self.connection.update_and_fetchone(
            sql=(
                """
                UPDATE court_cases
                SET defendant_id = %s,
                    participants = CASE
                        WHEN %s = ANY(COALESCE(participants, '{}'::bigint[]))
                            THEN COALESCE(participants, '{}'::bigint[])
                        ELSE array_append(COALESCE(participants, '{}'::bigint[]), %s)
                    END,
                    updated_at = NOW()
                WHERE id = %s AND defendant_id IS NULL
                RETURNING *
                """
            ),
            params=(defendant_id, defendant_id, defendant_id, case_id),
        )
        if result.is_empty():
            return None
        return result.as_dict()

    async def update_claim(
        self,
        *,
        case_id: int,
        claim: str,
    ) -> dict[str, Any] | None:
        result: SingleQueryResult = await self.connection.update_and_fetchone(
            sql=(
                """
                UPDATE court_cases
                SET claim = %s, updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """
            ),
            params=(claim, case_id),
        )
        if result.is_empty():
            return None
        return result.as_dict()

    async def update_category(
        self,
        *,
        case_id: int,
        category: str,
    ) -> dict[str, Any] | None:
        result: SingleQueryResult = await self.connection.update_and_fetchone(
            sql=(
                """
                UPDATE court_cases
                SET category = %s, updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """
            ),
            params=(category, case_id),
        )
        if result.is_empty():
            return None
        return result.as_dict()

    async def update_status(
        self,
        *,
        case_id: int,
        status: str,
    ) -> dict[str, Any] | None:
        result: SingleQueryResult = await self.connection.update_and_fetchone(
            sql=(
                """
                UPDATE court_cases
                SET status = %s, updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """
            ),
            params=(status, case_id),
        )
        if result.is_empty():
            return None
        return result.as_dict()

    async def mark_sent_to_scholar(
        self,
        *,
        case_id: int,
        sent: bool = True,
    ) -> dict[str, Any] | None:
        result: SingleQueryResult = await self.connection.update_and_fetchone(
            sql=(
                """
                UPDATE court_cases
                SET sent_to_scholar = %s, updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """
            ),
            params=(sent, case_id),
        )
        if result.is_empty():
            return None
        return result.as_dict()

    async def append_evidence(
        self,
        *,
        case_id: int,
        evidence_item: dict[str, Any],
    ) -> dict[str, Any] | None:
        payload = json.dumps([evidence_item], ensure_ascii=False)
        result: SingleQueryResult = await self.connection.update_and_fetchone(
            sql=(
                """
                UPDATE court_cases
                SET evidence = COALESCE(evidence, '[]'::jsonb) || %s::jsonb,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """
            ),
            params=(payload, case_id),
        )
        if result.is_empty():
            return None
        return result.as_dict()

    async def append_mediate_log(
        self,
        *,
        case_id: int,
        entry: dict[str, Any],
    ) -> None:
        payload = json.dumps([entry], ensure_ascii=False)
        await self.connection.execute(
            sql=(
                """
                UPDATE court_cases
                SET mediate_log = COALESCE(mediate_log, '[]'::jsonb) || %s::jsonb,
                    updated_at = NOW()
                WHERE id = %s
                """
            ),
            params=(payload, case_id),
        )

    async def get_mediate_log(self, *, case_id: int) -> list[dict[str, Any]]:
        result: SingleQueryResult = await self.connection.fetchone(
            sql="SELECT mediate_log FROM court_cases WHERE id = %s",
            params=(case_id,),
        )
        if result.is_empty():
            return []
        row = result.as_dict()
        raw = row.get("mediate_log")
        if raw is None:
            return []
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]
        if isinstance(raw, dict):
            return [raw]
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
            except Exception:
                return []
            if isinstance(parsed, list):
                return [item for item in parsed if isinstance(item, dict)]
            if isinstance(parsed, dict):
                return [parsed]
        return []

    async def clear_mediate_log(self, *, case_id: int) -> None:
        await self.connection.execute(
            sql=(
                """
                UPDATE court_cases
                SET mediate_log = '[]'::jsonb,
                    updated_at = NOW()
                WHERE id = %s
                """
            ),
            params=(case_id,),
        )
