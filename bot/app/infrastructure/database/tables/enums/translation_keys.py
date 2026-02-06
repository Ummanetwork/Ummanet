from app.infrastructure.database.tables.enums.base import BaseTableActionEnum


class TranslationKeysTableAction(BaseTableActionEnum):
    CREATE = "create"
    GET_BY_IDENTIFIER = "get_by_identifier"
    LIST_ALL = "list_all"
