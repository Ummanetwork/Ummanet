from app.infrastructure.database.tables.enums.base import BaseTableActionEnum


class TranslationsTableAction(BaseTableActionEnum):
    UPSERT = "upsert"
    LIST_BY_LANGUAGE = "list_by_language"
    DELETE_BY_LANGUAGE = "delete_by_language"
