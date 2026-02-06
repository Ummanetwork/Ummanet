from app.infrastructure.database.tables.base import BaseTable

class ChannelsTable(BaseTable):
    async def ensure_schema(self) -> None:
        await self.connection.execute(
            sql="""
            CREATE TABLE IF NOT EXISTS channels (
                id SERIAL PRIMARY KEY,
                lang VARCHAR(10) NOT NULL,
                kind TEXT NOT NULL,
                url  TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_channels_lang_kind ON channels(lang, kind);
            """
        )
