import json
from typing import Any

from app.infrastructure.database.tables.base import BaseTable


class ContractsTable(BaseTable):
    async def ensure_schema(self) -> None:
        await self.connection.execute(
            sql="""
            CREATE TABLE IF NOT EXISTS contracts (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                type TEXT NOT NULL,
                template_topic TEXT,
                language TEXT,
                data JSONB,
                rendered_text TEXT,
                status TEXT,
                invite_code TEXT,
                responsible_admin_id INTEGER,
                scholar_id TEXT,
                scholar_name TEXT,
                scholar_contact TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_contracts_user ON contracts(user_id);
            CREATE INDEX IF NOT EXISTS idx_contracts_type ON contracts(type);
            CREATE INDEX IF NOT EXISTS idx_contracts_status ON contracts(status);
            CREATE INDEX IF NOT EXISTS idx_contracts_invite_code ON contracts(invite_code);
            """
        )
        await self.connection.execute(
            sql="ALTER TABLE contracts ADD COLUMN IF NOT EXISTS invite_code TEXT"
        )
        await self.connection.execute(
            sql="ALTER TABLE contracts ADD COLUMN IF NOT EXISTS responsible_admin_id INTEGER"
        )
        await self.connection.execute(
            sql="ALTER TABLE contracts ADD COLUMN IF NOT EXISTS scholar_id TEXT"
        )
        await self.connection.execute(
            sql="ALTER TABLE contracts ADD COLUMN IF NOT EXISTS scholar_name TEXT"
        )
        await self.connection.execute(
            sql="ALTER TABLE contracts ADD COLUMN IF NOT EXISTS scholar_contact TEXT"
        )
        await self.connection.execute(
            sql="CREATE INDEX IF NOT EXISTS idx_contracts_invite_code ON contracts(invite_code)"
        )

    async def add_contract(
        self,
        *,
        user_id: int,
        contract_type: str,
        template_topic: str,
        language: str,
        data: dict[str, Any],
        rendered_text: str,
        status: str,
    ) -> int | None:
        payload = json.dumps(data or {}, ensure_ascii=False)
        result = await self.connection.insert_and_fetchone(
            sql=(
                """
                INSERT INTO contracts (
                    user_id, type, template_topic, language, data, rendered_text, status
                )
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)
                RETURNING id
                """
            ),
            params=(user_id, contract_type, template_topic, language, payload, rendered_text, status),
        )
        if result.is_empty():
            return None
        return int(result.as_dict().get("id") or 0)

    async def update_contract(
        self,
        *,
        contract_id: int,
        status: str,
        rendered_text: str,
        data: dict[str, Any],
    ) -> None:
        payload = json.dumps(data or {}, ensure_ascii=False)
        await self.connection.execute(
            sql=(
                """
                UPDATE contracts
                SET status = %s,
                    rendered_text = %s,
                    data = %s::jsonb,
                    updated_at = NOW()
                WHERE id = %s
                """
            ),
            params=(status, rendered_text, payload, contract_id),
        )

    async def get_contract(self, *, contract_id: int) -> dict[str, Any] | None:
        result = await self.connection.fetchone(
            sql=(
                """
                SELECT id, user_id, type, template_topic, language, data, rendered_text, status, invite_code
                FROM contracts
                WHERE id = %s
                """
            ),
            params=(contract_id,),
        )
        if result.is_empty():
            return None
        return result.as_dict()

    async def get_contract_by_invite_code(self, *, invite_code: str) -> dict[str, Any] | None:
        result = await self.connection.fetchone(
            sql=(
                """
                SELECT id, user_id, type, template_topic, language, data, rendered_text, status, invite_code
                FROM contracts
                WHERE invite_code = %s
                """
            ),
            params=(invite_code,),
        )
        if result.is_empty():
            return None
        return result.as_dict()

    async def get_contracts_by_user(self, *, user_id: int) -> list[dict[str, Any]]:
        result = await self.connection.fetchmany(
            sql=(
                """
                SELECT id, user_id, type, template_topic, language, data, rendered_text, status, invite_code, created_at, updated_at
                FROM contracts
                WHERE user_id = %s
                ORDER BY created_at DESC
                """
            ),
            params=(user_id,),
        )
        return result.as_dicts()

    async def get_contracts_for_user(self, *, user_id: int) -> list[dict[str, Any]]:
        result = await self.connection.fetchmany(
            sql=(
                """
                SELECT id, user_id, type, template_topic, language, data, rendered_text, status, invite_code, created_at, updated_at
                FROM contracts
                WHERE user_id = %s OR data->>'recipient_id' = %s
                ORDER BY created_at DESC
                """
            ),
            params=(user_id, str(user_id)),
        )
        return result.as_dicts()

    async def update_status(
        self,
        *,
        contract_id: int,
        status: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        payload = json.dumps(data or {}, ensure_ascii=False)
        await self.connection.execute(
            sql=(
                """
                UPDATE contracts
                SET status = %s,
                    data = %s::jsonb,
                    updated_at = NOW()
                WHERE id = %s
                """
            ),
            params=(status, payload, contract_id),
        )

    async def set_invite_code(self, *, contract_id: int, invite_code: str | None) -> None:
        await self.connection.execute(
            sql=(
                """
                UPDATE contracts
                SET invite_code = %s,
                    updated_at = NOW()
                WHERE id = %s
                """
            ),
            params=(invite_code, contract_id),
        )

    async def delete_contract(self, *, contract_id: int) -> None:
        await self.connection.execute(
            sql="DELETE FROM contracts WHERE id = %s",
            params=(contract_id,),
        )
