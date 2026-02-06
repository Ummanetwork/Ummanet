"""add user contact fields

Revision ID: 3d6f0bff2e2c
Revises: d9f5f0f0d1ab
Create Date: 2025-10-28 16:05:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3d6f0bff2e2c"
down_revision: Union[str, None] = "d9f5f0f0d1ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use idempotent DDL to avoid duplicate column/index errors on existing DB
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name TEXT NULL"
    )
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email TEXT NULL"
    )
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_number TEXT NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_users_email ON users (email)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_users_phone_number ON users (phone_number)"
    )


def downgrade() -> None:
    op.drop_index("ix_users_phone_number", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_column("users", "phone_number")
    op.drop_column("users", "email")
    op.drop_column("users", "full_name")
