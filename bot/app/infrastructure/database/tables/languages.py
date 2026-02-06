import logging

from app.infrastructure.database.connection.base import BaseConnection
from app.infrastructure.database.models.language import LanguageModel
from app.infrastructure.database.query.results import (
    MultipleQueryResult,
    SingleQueryResult,
)
from app.infrastructure.database.tables.base import BaseTable
from app.infrastructure.database.tables.enums.languages import LanguagesTableAction

logger = logging.getLogger(__name__)


class LanguagesTable(BaseTable):
    __tablename__ = "languages"

    def __init__(self, connection: BaseConnection):
        self.connection = connection

    async def list_all(self) -> list[LanguageModel]:
        result: MultipleQueryResult = await self.connection.fetchmany(
            sql="""
                SELECT id, code, is_default
                FROM languages
                ORDER BY is_default DESC, code
            """
        )
        self._log(LanguagesTableAction.LIST_ALL, count=len(result))
        return result.to_models(LanguageModel) or []

    async def get_by_code(self, code: str) -> LanguageModel | None:
        result: SingleQueryResult = await self.connection.fetchone(
            sql="""
                SELECT id, code, is_default
                FROM languages
                WHERE code = %s
            """,
            params=(code,),
        )
        language = result.to_model(LanguageModel)
        self._log(LanguagesTableAction.GET_BY_CODE, code=code, exists=bool(language))
        return language

    async def get_default(self) -> LanguageModel | None:
        result: SingleQueryResult = await self.connection.fetchone(
            sql="""
                SELECT id, code, is_default
                FROM languages
                WHERE is_default = TRUE
                LIMIT 1
            """
        )
        language = result.to_model(LanguageModel)
        self._log(LanguagesTableAction.GET_DEFAULT, exists=bool(language))
        return language

    async def create(self, *, code: str, is_default: bool = False) -> LanguageModel:
        if is_default:
            await self.connection.execute(
                sql="UPDATE languages SET is_default = FALSE WHERE is_default = TRUE"
            )

        result: SingleQueryResult = await self.connection.insert_and_fetchone(
            sql="""
                INSERT INTO languages(code, is_default)
                VALUES(%s, %s)
                RETURNING id, code, is_default
            """,
            params=(code, is_default),
        )
        language = result.to_model(LanguageModel, raise_if_empty=True)
        self._log(LanguagesTableAction.CREATE, code=code, is_default=is_default)
        return language  # type: ignore[return-value]

    async def set_default(self, language_id: int) -> None:
        await self.connection.execute(
            sql="UPDATE languages SET is_default = FALSE WHERE is_default = TRUE"
        )
        await self.connection.execute(
            sql="UPDATE languages SET is_default = TRUE WHERE id = %s",
            params=(language_id,),
        )
        self._log(LanguagesTableAction.SET_DEFAULT, language_id=language_id)

    async def delete(self, language_id: int) -> None:
        await self.connection.execute(
            sql="DELETE FROM languages WHERE id = %s",
            params=(language_id,),
        )
        self._log(LanguagesTableAction.DELETE, language_id=language_id)
