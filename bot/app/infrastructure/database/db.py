from app.infrastructure.database.connection.base import BaseConnection
from app.infrastructure.database.tables.users import UsersTable
from app.infrastructure.database.tables.prompts import PromptsTable
from app.infrastructure.database.tables.templates import TemplatesTable
from app.infrastructure.database.tables.documents import DocumentsTable
from app.infrastructure.database.tables.court_cases import CourtCasesTable
from app.infrastructure.database.tables.channels import ChannelsTable
from app.infrastructure.database.tables.languages import LanguagesTable
from app.infrastructure.database.tables.translation_keys import TranslationKeysTable
from app.infrastructure.database.tables.translations import TranslationsTable
from app.infrastructure.database.tables.contracts import ContractsTable
from app.infrastructure.database.tables.meetings import MeetingsTable
from app.infrastructure.database.tables.good_deeds import GoodDeedsTable
from app.infrastructure.database.tables.shariah_admin_applications import (
    ShariahAdminApplicationsTable,
)


class DB:
    def __init__(self, connection: BaseConnection) -> None:
        self.users = UsersTable(connection=connection)
        self.prompts = PromptsTable(connection=connection)
        self.templates = TemplatesTable(connection=connection)
        self.documents = DocumentsTable(connection=connection)
        self.court_cases = CourtCasesTable(connection=connection)
        self.channels = ChannelsTable(connection=connection)
        self.languages = LanguagesTable(connection=connection)
        self.translation_keys = TranslationKeysTable(connection=connection)
        self.translations = TranslationsTable(connection=connection)
        self.contracts = ContractsTable(connection=connection)
        self.meetings = MeetingsTable(connection=connection)
        self.good_deeds = GoodDeedsTable(connection=connection)
        self.shariah_admin_applications = ShariahAdminApplicationsTable(connection=connection)
