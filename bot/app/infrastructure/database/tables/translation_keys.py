import logging

from app.infrastructure.database.connection.base import BaseConnection
from app.infrastructure.database.models.translation_key import TranslationKeyModel
from app.infrastructure.database.query.results import (
    MultipleQueryResult,
    SingleQueryResult,
)
from app.infrastructure.database.tables.base import BaseTable
from app.infrastructure.database.tables.enums.translation_keys import (
    TranslationKeysTableAction,
)

logger = logging.getLogger(__name__)


class TranslationKeysTable(BaseTable):
    __tablename__ = "translation_keys"

    def __init__(self, connection: BaseConnection):
        self.connection = connection

    async def list_all(self) -> list[TranslationKeyModel]:
        result: MultipleQueryResult = await self.connection.fetchmany(
            sql="""
                SELECT id, identifier, description
                FROM translation_keys
                ORDER BY identifier
            """
        )
        self._log(TranslationKeysTableAction.LIST_ALL, count=len(result))
        return result.to_models(TranslationKeyModel) or []

    async def get_by_identifier(
        self, identifier: str
    ) -> TranslationKeyModel | None:
        result: SingleQueryResult = await self.connection.fetchone(
            sql="""
                SELECT id, identifier, description
                FROM translation_keys
                WHERE identifier = %s
            """,
            params=(identifier,),
        )
        key = result.to_model(TranslationKeyModel)
        self._log(
            TranslationKeysTableAction.GET_BY_IDENTIFIER,
            identifier=identifier,
            exists=bool(key),
        )
        return key

    async def create(
        self, *, identifier: str, description: str | None = None
    ) -> TranslationKeyModel:
        result: SingleQueryResult = await self.connection.insert_and_fetchone(
            sql="""
                INSERT INTO translation_keys(identifier, description)
                VALUES(%s, %s)
                ON CONFLICT (identifier) DO UPDATE
                SET description = EXCLUDED.description
                RETURNING id, identifier, description
            """,
            params=(identifier, description),
        )
        key = result.to_model(TranslationKeyModel, raise_if_empty=True)
        self._log(
            TranslationKeysTableAction.CREATE,
            identifier=identifier,
            description=description,
        )
        return key  # type: ignore[return-value]
