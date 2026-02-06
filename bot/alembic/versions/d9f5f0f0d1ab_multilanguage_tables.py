"""add multilanguage tables

Revision ID: d9f5f0f0d1ab
Revises: b20e5643d3bd
Create Date: 2025-10-11 15:40:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d9f5f0f0d1ab"
down_revision: Union[str, None] = "b20e5643d3bd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # languages (idempotent)
    if not insp.has_table("languages"):
        op.create_table(
            "languages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code", sa.String(length=32), nullable=False, unique=True),
            sa.Column(
                "is_default",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
    # unique partial index for default language
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_languages_default_true ON languages (is_default) WHERE is_default = true"
        )
    )

    # Optional documents maintenance (idempotent)
    op.execute(sa.text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS type TEXT"))
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_documents_category ON documents (category)"
        )
    )
    op.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_documents_type ON documents (type)")
    )

    # translation_keys
    if not insp.has_table("translation_keys"):
        op.create_table(
            "translation_keys",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("identifier", sa.Text(), nullable=False, unique=True),
            sa.Column("description", sa.Text(), nullable=True),
        )

    # translations
    if not insp.has_table("translations"):
        op.create_table(
            "translations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "language_id",
                sa.Integer(),
                sa.ForeignKey("languages.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "key_id",
                sa.Integer(),
                sa.ForeignKey("translation_keys.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("value", sa.Text(), nullable=True),
            sa.UniqueConstraint(
                "language_id", "key_id", name="uq_translations_language_key"
            ),
        )

    # indexes for translations
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_translations_language_id ON translations (language_id)"
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_translations_key_id ON translations (key_id)"
        )
    )

    # users.language_id column
    has_lang_id = False
    try:
        cols = insp.get_columns("users")
        has_lang_id = any(col.get("name") == "language_id" for col in cols)
    except Exception:
        has_lang_id = False
    if not has_lang_id:
        op.add_column("users", sa.Column("language_id", sa.Integer(), nullable=True))
    # foreign key (guarded)
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'fk_users_language'
                ) THEN
                    ALTER TABLE users
                    ADD CONSTRAINT fk_users_language
                    FOREIGN KEY (language_id) REFERENCES languages(id) ON DELETE RESTRICT;
                END IF;
            END $$;
            """
        )
    )

    # migrate old users.language -> users.language_id if needed
    has_old_language = False
    try:
        cols = insp.get_columns("users")
        has_old_language = any(col.get("name") == "language" for col in cols)
    except Exception:
        has_old_language = False

    # Ensure at least one language exists; prefer ru as default
    default_language_id = bind.execute(
        sa.text(
            "INSERT INTO languages (code, is_default) VALUES (:code, true) "
            "ON CONFLICT (code) DO UPDATE SET is_default = EXCLUDED.is_default RETURNING id"
        ),
        {"code": "ru"},
    ).scalar_one()

    if has_old_language:
        # Backfill mapping from users.language
        distinct_langs = [
            row[0]
            for row in bind.execute(
                sa.text(
                    "SELECT DISTINCT language FROM users WHERE language IS NOT NULL AND language <> ''"
                )
            )
        ]
        language_id_map: dict[str, int] = {}
        for code in distinct_langs:
            normalized_code = (code or "").strip()
            if not normalized_code:
                continue
            lang_id = bind.execute(
                sa.text(
                    "INSERT INTO languages (code, is_default) VALUES (:code, false) "
                    "ON CONFLICT (code) DO UPDATE SET code = EXCLUDED.code RETURNING id"
                ),
                {"code": normalized_code},
            ).scalar_one()
            language_id_map[normalized_code] = lang_id

        for code, lang_id in language_id_map.items():
            bind.execute(
                sa.text(
                    "UPDATE users SET language_id = :lang_id WHERE language = :code"
                ),
                {"lang_id": lang_id, "code": code},
            )

        # Assign default for missing
        bind.execute(
            sa.text(
                "UPDATE users SET language_id = :default_lang_id WHERE language_id IS NULL"
            ),
            {"default_lang_id": default_language_id},
        )

        # Drop legacy column
        op.drop_column("users", "language")

    # Ensure not-null on language_id once populated
    op.alter_column(
        "users",
        "language_id",
        existing_type=sa.Integer(),
        nullable=False,
    )


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("language", sa.VARCHAR(length=10), nullable=True),
    )

    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE users SET language = languages.code "
            "FROM languages WHERE users.language_id = languages.id"
        )
    )

    op.drop_constraint("fk_users_language", "users", type_="foreignkey")
    op.drop_column("users", "language_id")

    op.drop_index("ix_translations_key_id", table_name="translations")
    op.drop_index("ix_translations_language_id", table_name="translations")
    op.drop_table("translations")
    op.drop_table("translation_keys")
    op.drop_index("uq_languages_default_true", table_name="languages")
    op.execute(
        sa.text(
            "DROP INDEX IF EXISTS ix_documents_type"
        )
    )
    op.execute(
        sa.text(
            "DROP INDEX IF EXISTS ix_documents_category"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE documents DROP COLUMN IF EXISTS type"
        )
    )
    op.drop_table("languages")
