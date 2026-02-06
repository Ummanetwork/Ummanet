"""Make users.user_id BIGINT and ensure verification flags

Revision ID: 8e1a2c3d4f5a
Revises: 6a2a4db2c7e7
Create Date: 2025-10-28 18:35:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "8e1a2c3d4f5a"
down_revision: Union[str, None] = "6a2a4db2c7e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Postgres-safe, idempotent operations
    # 1) user_id -> BIGINT (for Telegram user ids)
    op.execute(
        """
        ALTER TABLE users
        ALTER COLUMN user_id TYPE BIGINT USING user_id::bigint;
        """
    )

    # 2) Ensure verification flags exist
    op.execute(
        """
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT false;
        """
    )
    op.execute(
        """
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN NOT NULL DEFAULT false;
        """
    )


def downgrade() -> None:
    # Downgrade is best-effort; may fail if data doesn't fit in INTEGER
    op.execute(
        """
        ALTER TABLE users
        ALTER COLUMN user_id TYPE INTEGER USING user_id::integer;
        """
    )
    op.execute(
        """
        ALTER TABLE users
        DROP COLUMN IF EXISTS phone_verified;
        """
    )
    op.execute(
        """
        ALTER TABLE users
        DROP COLUMN IF EXISTS email_verified;
        """
    )

