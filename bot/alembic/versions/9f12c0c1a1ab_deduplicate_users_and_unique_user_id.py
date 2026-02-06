"""Deduplicate users by user_id and enforce uniqueness

Revision ID: 9f12c0c1a1ab
Revises: 8e1a2c3d4f5a
Create Date: 2025-10-29 03:50:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9f12c0c1a1ab"
down_revision: Union[str, None] = "8e1a2c3d4f5a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Deduplicate rows keeping the smallest id for each user_id
    op.execute(
        sa.text(
            """
            WITH d AS (
                SELECT MIN(id) AS keep_id, user_id
                FROM users
                GROUP BY user_id
                HAVING COUNT(*) > 1
            )
            DELETE FROM users u
            USING d
            WHERE u.user_id = d.user_id
              AND u.id <> d.keep_id;
            """
        )
    )

    # 2) Enforce uniqueness on user_id (idempotent)
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'uq_users_user_id'
                ) THEN
                    BEGIN
                        ALTER TABLE users
                        ADD CONSTRAINT uq_users_user_id UNIQUE (user_id);
                    EXCEPTION WHEN duplicate_table THEN
                        -- Fallback: ignore if some env already has similar constraint
                        NULL;
                    END;
                END IF;
            END $$;
            """
        )
    )


def downgrade() -> None:
    # Best-effort: drop unique constraint if exists
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'uq_users_user_id'
                ) THEN
                    ALTER TABLE users DROP CONSTRAINT uq_users_user_id;
                END IF;
            END $$;
            """
        )
    )

