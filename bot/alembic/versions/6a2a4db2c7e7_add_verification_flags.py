"""add verification flags to users

Revision ID: 6a2a4db2c7e7
Revises: 3d6f0bff2e2c
Create Date: 2025-10-28 17:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6a2a4db2c7e7"
down_revision: Union[str, None] = "3d6f0bff2e2c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make idempotent to avoid failures if columns already exist
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT false"
    )
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN NOT NULL DEFAULT false"
    )


def downgrade() -> None:
    op.drop_column("users", "phone_verified")
    op.drop_column("users", "email_verified")
