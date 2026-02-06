from app.infrastructure.database.tables.base import BaseTable

class TemplatesTable(BaseTable):
    async def ensure_schema(self) -> None:
        await self.connection.execute(
            sql="""
            CREATE TABLE IF NOT EXISTS templates (
                id SERIAL PRIMARY KEY,
                key TEXT NOT NULL,
                lang VARCHAR(10) NOT NULL,
                title TEXT NOT NULL,
                body  TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_templates_key_lang ON templates(key, lang);
            """
        )
