from app.infrastructure.database.tables.base import BaseTable


class PromptsTable(BaseTable):
    async def ensure_schema(self) -> None:
        await self.connection.execute(
            sql="""
            CREATE TABLE IF NOT EXISTS prompts (
                id SERIAL PRIMARY KEY,
                key TEXT NOT NULL,
                lang VARCHAR(10) NOT NULL,
                text TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_prompts_key_lang ON prompts(key, lang);
            """
        )

    async def get_text(self, *, key: str, lang: str) -> str | None:
        row = await self.connection.fetchrow(
            sql="""
                SELECT text FROM prompts WHERE key = %s AND lang = %s LIMIT 1
            """,
            params=(key, lang),
        )
        return row[0] if row else None

    async def upsert(self, *, key: str, lang: str, text: str) -> None:
        await self.connection.execute(
            sql="""
            INSERT INTO prompts(key, lang, text) VALUES(%s,%s,%s)
            ON CONFLICT (key, lang) DO UPDATE SET text = EXCLUDED.text
            """,
            params=(key, lang, text),
        )
