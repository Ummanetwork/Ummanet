from __future__ import annotations

import json
from typing import Any

from app.bot.enums.roles import UserRole
from app.infrastructure.database.query.results import MultipleQueryResult, SingleQueryResult
from app.infrastructure.database.tables.base import BaseTable


class MeetingsTable(BaseTable):
    __tablename__ = "proposals"

    async def ensure_schema(self) -> None:
        await self.connection.execute(
            sql="""
            CREATE TABLE IF NOT EXISTS admins (
                id SERIAL PRIMARY KEY,
                user_id BIGINT UNIQUE NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                created_by BIGINT
            );
            CREATE INDEX IF NOT EXISTS idx_admins_user_id ON admins(user_id);

            CREATE TABLE IF NOT EXISTS proposals (
                id SERIAL PRIMARY KEY,
                author_id BIGINT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                goal TEXT NOT NULL,
                shariah_basis TEXT NOT NULL,
                shariah_text TEXT,
                conditions TEXT,
                terms TEXT,
                status TEXT NOT NULL DEFAULT 'pending_review',
                admin_comment TEXT,
                admin_reason TEXT,
                reviewed_by BIGINT,
                voting_started_at TIMESTAMPTZ,
                voting_ends_at TIMESTAMPTZ,
                voting_result TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status);
            CREATE INDEX IF NOT EXISTS idx_proposals_author ON proposals(author_id);
            CREATE INDEX IF NOT EXISTS idx_proposals_voting_ends_at ON proposals(voting_ends_at);

            CREATE TABLE IF NOT EXISTS votes (
                id SERIAL PRIMARY KEY,
                proposal_id INT NOT NULL REFERENCES proposals(id) ON DELETE CASCADE,
                user_id BIGINT NOT NULL,
                vote_type TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE (proposal_id, user_id)
            );
            CREATE INDEX IF NOT EXISTS idx_votes_proposal ON votes(proposal_id);
            CREATE INDEX IF NOT EXISTS idx_votes_user ON votes(user_id);

            CREATE TABLE IF NOT EXISTS executions (
                id SERIAL PRIMARY KEY,
                proposal_id INT NOT NULL REFERENCES proposals(id) ON DELETE CASCADE,
                responsible_id BIGINT,
                status TEXT NOT NULL DEFAULT 'in_progress',
                deadline TIMESTAMPTZ,
                proof TEXT,
                comment TEXT,
                rejected_reason TEXT,
                confirmed_by BIGINT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_executions_status ON executions(status);
            CREATE INDEX IF NOT EXISTS idx_executions_responsible ON executions(responsible_id);
            """
        )

    async def is_admin(self, *, user_id: int) -> bool:
        admin_row: SingleQueryResult = await self.connection.fetchone(
            sql="SELECT 1 FROM admins WHERE user_id = %s LIMIT 1",
            params=(user_id,),
        )
        if not admin_row.is_empty():
            return True

        user_row: SingleQueryResult = await self.connection.fetchone(
            sql="SELECT 1 FROM users WHERE user_id = %s AND role = %s LIMIT 1",
            params=(user_id, UserRole.ADMIN),
        )
        return not user_row.is_empty()

    async def create_proposal(
        self,
        *,
        author_id: int,
        title: str,
        description: str,
        goal: str,
        shariah_basis: str,
        shariah_text: str | None,
        conditions: str | None,
        terms: str | None,
    ) -> int | None:
        result = await self.connection.insert_and_fetchone(
            sql=(
                """
                INSERT INTO proposals(
                    author_id,
                    title,
                    description,
                    goal,
                    shariah_basis,
                    shariah_text,
                    conditions,
                    terms,
                    status
                )
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
                """
            ),
            params=(
                author_id,
                title,
                description,
                goal,
                shariah_basis,
                shariah_text,
                conditions,
                terms,
                "pending_review",
            ),
        )
        if result.is_empty():
            return None
        return int(result.as_dict().get("id") or 0)

    async def list_pending_proposals(self, *, limit: int = 25) -> list[dict[str, Any]]:
        rows: MultipleQueryResult = await self.connection.fetchmany(
            sql=(
                """
                SELECT id, author_id, title, description, goal, shariah_basis,
                       shariah_text, conditions, terms, created_at
                FROM proposals
                WHERE status = %s
                ORDER BY created_at ASC
                LIMIT %s
                """
            ),
            params=("pending_review", limit),
        )
        return rows.as_dicts()

    async def get_proposal(self, *, proposal_id: int) -> dict[str, Any] | None:
        row: SingleQueryResult = await self.connection.fetchone(
            sql=(
                """
                SELECT *
                FROM proposals
                WHERE id = %s
                LIMIT 1
                """
            ),
            params=(proposal_id,),
        )
        if row.is_empty():
            return None
        return row.as_dict()

    async def update_proposal_status(
        self,
        *,
        proposal_id: int,
        status: str,
        reviewed_by: int | None = None,
        admin_comment: str | None = None,
        admin_reason: str | None = None,
    ) -> None:
        await self.connection.execute(
            sql=(
                """
                UPDATE proposals
                SET status = %s,
                    reviewed_by = COALESCE(%s, reviewed_by),
                    admin_comment = %s,
                    admin_reason = %s,
                    updated_at = NOW()
                WHERE id = %s
                """
            ),
            params=(status, reviewed_by, admin_comment, admin_reason, proposal_id),
        )

    async def start_voting(
        self,
        *,
        proposal_id: int,
        reviewed_by: int | None,
        ends_at: datetime,
    ) -> None:
        await self.connection.execute(
            sql=(
                """
                UPDATE proposals
                SET status = %s,
                    reviewed_by = COALESCE(%s, reviewed_by),
                    voting_started_at = NOW(),
                    voting_ends_at = %s,
                    updated_at = NOW()
                WHERE id = %s
                """
            ),
            params=("voting_active", reviewed_by, ends_at, proposal_id),
        )

    async def list_active_votings(self, *, limit: int = 25) -> list[dict[str, Any]]:
        rows: MultipleQueryResult = await self.connection.fetchmany(
            sql=(
                """
                SELECT id, title, description, goal, shariah_basis, shariah_text,
                       conditions, terms, voting_ends_at, created_at
                FROM proposals
                WHERE status IN ('approved', 'voting_active')
                  AND (voting_ends_at IS NULL OR voting_ends_at > NOW())
                ORDER BY created_at DESC
                LIMIT %s
                """
            ),
            params=(limit,),
        )
        return rows.as_dicts()

    async def add_vote(
        self,
        *,
        proposal_id: int,
        user_id: int,
        vote_type: str,
    ) -> bool:
        result = await self.connection.insert_and_fetchone(
            sql=(
                """
                INSERT INTO votes(proposal_id, user_id, vote_type)
                VALUES(%s, %s, %s)
                ON CONFLICT (proposal_id, user_id) DO NOTHING
                RETURNING id
                """
            ),
            params=(proposal_id, user_id, vote_type),
        )
        return not result.is_empty()

    async def get_vote_counts(self, *, proposal_id: int) -> dict[str, int]:
        rows: MultipleQueryResult = await self.connection.fetchmany(
            sql=(
                """
                SELECT vote_type, COUNT(*) AS cnt
                FROM votes
                WHERE proposal_id = %s
                GROUP BY vote_type
                """
            ),
            params=(proposal_id,),
        )
        counts = {"for": 0, "against": 0, "abstain": 0}
        for row in rows.as_dicts():
            vote_type = str(row.get("vote_type") or "")
            counts[vote_type] = int(row.get("cnt") or 0)
        return counts

    async def list_executions(
        self,
        *,
        statuses: tuple[str, ...] | None = None,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        if statuses:
            rows: MultipleQueryResult = await self.connection.fetchmany(
                sql=(
                    """
                    SELECT e.id, e.proposal_id, e.responsible_id, e.status, e.deadline,
                           e.proof, e.comment, e.rejected_reason, e.created_at, e.updated_at,
                           p.title
                    FROM executions AS e
                    JOIN proposals AS p ON p.id = e.proposal_id
                    WHERE e.status = ANY(%s)
                    ORDER BY e.created_at DESC
                    LIMIT %s
                    """
                ),
                params=(list(statuses), limit),
            )
        else:
            rows = await self.connection.fetchmany(
                sql=(
                    """
                    SELECT e.id, e.proposal_id, e.responsible_id, e.status, e.deadline,
                           e.proof, e.comment, e.rejected_reason, e.created_at, e.updated_at,
                           p.title
                    FROM executions AS e
                    JOIN proposals AS p ON p.id = e.proposal_id
                    ORDER BY e.created_at DESC
                    LIMIT %s
                    """
                ),
                params=(limit,),
            )
        return rows.as_dicts()

    async def get_execution(self, *, execution_id: int) -> dict[str, Any] | None:
        row: SingleQueryResult = await self.connection.fetchone(
            sql=(
                """
                SELECT e.id, e.proposal_id, e.responsible_id, e.status, e.deadline,
                       e.proof, e.comment, e.rejected_reason, e.created_at, e.updated_at,
                       p.title
                FROM executions AS e
                JOIN proposals AS p ON p.id = e.proposal_id
                WHERE e.id = %s
                LIMIT 1
                """
            ),
            params=(execution_id,),
        )
        if row.is_empty():
            return None
        return row.as_dict()

    async def update_execution_report(
        self,
        *,
        execution_id: int,
        comment: str | None,
        proof: str | None,
    ) -> None:
        await self.connection.execute(
            sql=(
                """
                UPDATE executions
                SET comment = %s,
                    proof = %s,
                    updated_at = NOW()
                WHERE id = %s
                """
            ),
            params=(comment, proof, execution_id),
        )

    async def confirm_execution(self, *, execution_id: int, admin_id: int) -> None:
        await self.connection.execute(
            sql=(
                """
                UPDATE executions
                SET status = %s,
                    confirmed_by = %s,
                    updated_at = NOW()
                WHERE id = %s
                """
            ),
            params=("completed", admin_id, execution_id),
        )

    async def reject_execution(
        self,
        *,
        execution_id: int,
        admin_id: int,
        reason: str,
    ) -> None:
        await self.connection.execute(
            sql=(
                """
                UPDATE executions
                SET status = %s,
                    rejected_reason = %s,
                    confirmed_by = %s,
                    updated_at = NOW()
                WHERE id = %s
                """
            ),
            params=("failed", reason, admin_id, execution_id),
        )

    async def close_expired_votings(self, *, limit: int = 25) -> list[dict[str, Any]]:
        rows: MultipleQueryResult = await self.connection.fetchmany(
            sql=(
                """
                SELECT id, reviewed_by, voting_ends_at
                FROM proposals
                WHERE status IN ('approved', 'voting_active')
                  AND voting_result IS NULL
                  AND voting_ends_at IS NOT NULL
                  AND voting_ends_at <= NOW()
                ORDER BY voting_ends_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT %s
                """
            ),
            params=(limit,),
        )
        closed: list[dict[str, Any]] = []
        for row in rows.as_dicts():
            proposal_id = int(row.get("id") or 0)
            if proposal_id <= 0:
                continue
            counts = await self.get_vote_counts(proposal_id=proposal_id)
            result = "accepted" if counts["for"] > counts["against"] else "rejected"
            await self.connection.execute(
                sql=(
                    """
                    UPDATE proposals
                    SET status = %s,
                        voting_result = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """
                ),
                params=(result, result, proposal_id),
            )
            if result == "accepted":
                existing: SingleQueryResult = await self.connection.fetchone(
                    sql="SELECT 1 FROM executions WHERE proposal_id = %s LIMIT 1",
                    params=(proposal_id,),
                )
                if existing.is_empty():
                    await self.connection.execute(
                        sql=(
                            """
                            INSERT INTO executions(
                                proposal_id,
                                responsible_id,
                                status
                            )
                            VALUES(%s, %s, %s)
                            """
                        ),
                        params=(proposal_id, row.get("reviewed_by"), "in_progress"),
                    )
            closed.append(
                {
                    "proposal_id": proposal_id,
                    "result": result,
                    "counts": counts,
                }
            )
        return closed

    @staticmethod
    def serialize_proof(*, file_id: str | None, filename: str | None, link: str | None) -> str | None:
        if not file_id and not link:
            return None
        payload = {"file_id": file_id, "filename": filename, "link": link}
        return json.dumps(payload, ensure_ascii=False)
