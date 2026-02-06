import logging

from app.infrastructure.database.connection.base import BaseConnection
from app.infrastructure.database.models.translation import TranslationModel
from app.infrastructure.database.query.results import (
    MultipleQueryResult,
    SingleQueryResult,
)
from app.infrastructure.database.tables.base import BaseTable
from app.infrastructure.database.tables.enums.translations import (
    TranslationsTableAction,
)

logger = logging.getLogger(__name__)


class TranslationsTable(BaseTable):
    __tablename__ = "translations"

    def __init__(self, connection: BaseConnection):
        self.connection = connection

    async def list_by_language(self, language_id: int) -> list[TranslationModel]:
        result: MultipleQueryResult = await self.connection.fetchmany(
            sql="""
                SELECT id, language_id, key_id, value
                FROM translations
                WHERE language_id = %s
            """,
            params=(language_id,),
        )
        self._log(
            TranslationsTableAction.LIST_BY_LANGUAGE,
            language_id=language_id,
            count=len(result),
        )
        return result.to_models(TranslationModel) or []

    async def upsert(
        self, *, language_id: int, key_id: int, value: str | None
    ) -> TranslationModel:
        result: SingleQueryResult = await self.connection.insert_and_fetchone(
            sql="""
                INSERT INTO translations(language_id, key_id, value)
                VALUES(%s, %s, %s)
                ON CONFLICT(language_id, key_id)
                DO UPDATE SET value = EXCLUDED.value
                RETURNING id, language_id, key_id, value
            """,
            params=(language_id, key_id, value),
        )
        translation = result.to_model(TranslationModel, raise_if_empty=True)
        self._log(
            TranslationsTableAction.UPSERT,
            language_id=language_id,
            key_id=key_id,
        )
        return translation  # type: ignore[return-value]

    async def delete_by_language(self, language_id: int) -> None:
        await self.connection.execute(
            sql="DELETE FROM translations WHERE language_id = %s",
            params=(language_id,),
        )
        self._log(
            TranslationsTableAction.DELETE_BY_LANGUAGE,
            language_id=language_id,
        )
