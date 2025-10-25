"""add notification settings columns

Revision ID: 8b1f3e2c4d5a
Revises: ff4b75d7cabc
Create Date: 2025-07-15 00:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8b1f3e2c4d5a"
down_revision = "ff4b75d7cabc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("digest_frequency", sa.String(), nullable=False, server_default="daily"),
    )
    op.add_column(
        "users",
        sa.Column("quiet_hours_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "users",
        sa.Column("quiet_hours_start", sa.Time(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("quiet_hours_end", sa.Time(), nullable=True),
    )

    op.execute("ALTER TABLE users ALTER COLUMN digest_frequency DROP DEFAULT")
    op.execute("ALTER TABLE users ALTER COLUMN quiet_hours_enabled DROP DEFAULT")


def downgrade() -> None:
    op.drop_column("users", "quiet_hours_end")
    op.drop_column("users", "quiet_hours_start")
    op.drop_column("users", "quiet_hours_enabled")
    op.drop_column("users", "digest_frequency")
