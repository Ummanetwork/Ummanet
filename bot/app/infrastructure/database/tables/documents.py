from typing import Any

from app.infrastructure.database.tables.base import BaseTable
from app.infrastructure.database.query.results import MultipleQueryResult, SingleQueryResult

class DocumentsTable(BaseTable):
    async def ensure_schema(self) -> None:
        await self.connection.execute(
            sql="""
            CREATE TABLE IF NOT EXISTS documents (
                id SERIAL PRIMARY KEY,
                filename TEXT UNIQUE NOT NULL,
                user_id BIGINT,
                category TEXT NOT NULL,
                name TEXT NOT NULL,
                content BYTEA NOT NULL,
                type TEXT,
                contract_id BIGINT
            );
            CREATE INDEX IF NOT EXISTS idx_documents_user ON documents(user_id);
            """
        )
        await self.connection.execute(
            sql="ALTER TABLE documents ADD COLUMN IF NOT EXISTS type TEXT"
        )
        await self.connection.execute(
            sql="ALTER TABLE documents ADD COLUMN IF NOT EXISTS contract_id BIGINT"
        )
        await self.connection.execute(
            sql="CREATE INDEX IF NOT EXISTS ix_documents_category ON documents(category)"
        )
        await self.connection.execute(
            sql="CREATE INDEX IF NOT EXISTS ix_documents_type ON documents(type)"
        )
        await self.connection.execute(
            sql="CREATE INDEX IF NOT EXISTS ix_documents_contract ON documents(contract_id)"
        )

    async def add_document(
        self,
        *,
        filename: str,
        user_id: int | None,
        category: str,
        name: str,
        content: bytes,
        doc_type: str | None = None,
        contract_id: int | None = None,
    ) -> None:
        await self.connection.execute(
            sql="""
                INSERT INTO documents(filename, user_id, category, name, content, type, contract_id)
                VALUES(%s,%s,%s,%s,%s,%s,%s)
            """,
            params=(filename, user_id, category, name, content, doc_type, contract_id),
        )

    async def get_documents_by_category(self, *, category: str) -> list[dict[str, Any]]:
        result: MultipleQueryResult = await self.connection.fetchmany(
            sql="""
                SELECT id, filename, user_id, category, name, content, type, contract_id
                FROM documents
                WHERE category = %s
            """,
            params=(category,),
        )
        return result.as_dicts()

    async def get_document_by_id(self, *, document_id: int) -> dict[str, Any] | None:
        result: SingleQueryResult = await self.connection.fetchone(
            sql="""
                SELECT id, filename, user_id, category, name, content, type, contract_id
                FROM documents
                WHERE id = %s
            """,
            params=(document_id,),
        )
        if result.is_empty():
            return None
        return result.as_dict()

    async def get_user_documents_by_type(
        self, *, user_id: int, doc_type: str | None = None
    ) -> list[dict[str, Any]]:
        if doc_type:
            result: MultipleQueryResult = await self.connection.fetchmany(
                sql="""
                    SELECT id, filename, user_id, category, name, content, type, contract_id
                    FROM documents
                    WHERE user_id = %s AND type = %s
                """,
                params=(user_id, doc_type),
            )
        else:
            result = await self.connection.fetchmany(
                sql="""
                    SELECT id, filename, user_id, category, name, content, type, contract_id
                    FROM documents
                    WHERE user_id = %s
                """,
                params=(user_id,),
            )
        return result.as_dicts()

    async def search_documents_by_name_in_category(
        self, *, category: str, pattern: str
    ) -> list[dict[str, Any]]:
        result: MultipleQueryResult = await self.connection.fetchmany(
            sql="""
                SELECT id, filename, user_id, category, name, content, type, contract_id
                FROM documents
                WHERE category = %s AND LOWER(name) LIKE LOWER(%s)
            """,
            params=(category, f"%{pattern}%"),
        )
        return result.as_dicts()

    async def get_user_document_by_contract_id(
        self,
        *,
        user_id: int,
        contract_id: int,
    ) -> dict[str, Any] | None:
        result: SingleQueryResult = await self.connection.fetchone(
            sql="""
                SELECT id, filename, user_id, category, name, content, type, contract_id
                FROM documents
                WHERE user_id = %s AND contract_id = %s
                LIMIT 1
            """,
            params=(user_id, contract_id),
        )
        if result.is_empty():
            return None
        return result.as_dict()

    async def delete_by_contract_id(self, *, contract_id: int) -> None:
        await self.connection.execute(
            sql="DELETE FROM documents WHERE contract_id = %s",
            params=(contract_id,),
        )
