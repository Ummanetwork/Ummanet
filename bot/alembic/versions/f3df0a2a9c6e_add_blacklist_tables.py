"""Add blacklist, complaints, and appeals tables

Revision ID: f3df0a2a9c6e
Revises: 9f12c0c1a1ab
Create Date: 2025-11-05 19:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f3df0a2a9c6e"
down_revision: Union[str, None] = "9f12c0c1a1ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "blacklist",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "date_added",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("birthdate", sa.Date(), nullable=True),
        sa.Column("city", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),  # default inactive until approved
        ),
    )

    op.execute(
        sa.text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_blacklist_identity
            ON blacklist (
                name,
                COALESCE(phone, ''),
                COALESCE(birthdate, DATE '0001-01-01'),
                COALESCE(city, '')
            )
            """
        )
    )

    op.create_table(
        "blacklist_complaints",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "blacklist_id",
            sa.BigInteger(),
            sa.ForeignKey("blacklist.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "complaint_date",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("added_by", sa.Text(), nullable=False),
        sa.Column("added_by_phone", sa.Text(), nullable=True),
        sa.Column("added_by_id", sa.BigInteger(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
    )
    op.create_index(
        "ix_blacklist_complaints_blacklist_id",
        "blacklist_complaints",
        ["blacklist_id"],
    )

    op.create_table(
        "blacklist_appeals",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "blacklist_id",
            sa.BigInteger(),
            sa.ForeignKey("blacklist.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "appeal_date",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "is_appeal",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("appeal_by", sa.Text(), nullable=False),
        sa.Column("appeal_by_phone", sa.Text(), nullable=True),
        sa.Column("appeal_by_id", sa.BigInteger(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
    )
    op.create_index(
        "ix_blacklist_appeals_blacklist_id", "blacklist_appeals", ["blacklist_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_blacklist_appeals_blacklist_id", table_name="blacklist_appeals")
    op.drop_table("blacklist_appeals")

    op.drop_index(
        "ix_blacklist_complaints_blacklist_id", table_name="blacklist_complaints"
    )
    op.drop_table("blacklist_complaints")

    op.execute(
        sa.text(
            "DROP INDEX IF EXISTS uq_blacklist_identity"
        )
    )
    op.drop_table("blacklist")
