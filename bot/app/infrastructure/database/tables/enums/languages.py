from app.infrastructure.database.tables.enums.base import BaseTableActionEnum


class LanguagesTableAction(BaseTableActionEnum):
    CREATE = "create"
    DELETE = "delete"
    LIST_ALL = "list_all"
    GET_BY_CODE = "get_by_code"
    GET_DEFAULT = "get_default"
    SET_DEFAULT = "set_default"
