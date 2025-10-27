"""governance override reversal support

Revision ID: c8a9f6e7d123
Revises: a7d3e0c5f1ab
Create Date: 2025-08-04 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c8a9f6e7d123"
down_revision: Union[str, Sequence[str], None] = "a7d3e0c5f1ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "governance_override_actions",
        sa.Column("execution_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "governance_override_actions",
        sa.Column(
            "detail_snapshot",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_unique_constraint(
        "uq_governance_override_execution_hash",
        "governance_override_actions",
        ["execution_hash"],
    )
    op.execute(
        "UPDATE governance_override_actions SET detail_snapshot = '{}'::jsonb"
    )
    op.alter_column(
        "governance_override_actions",
        "detail_snapshot",
        server_default=None,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "governance_override_actions",
        "detail_snapshot",
        server_default=sa.text("'{}'::jsonb"),
    )
    op.drop_constraint(
        "uq_governance_override_execution_hash",
        "governance_override_actions",
        type_="unique",
    )
    op.drop_column("governance_override_actions", "detail_snapshot")
    op.drop_column("governance_override_actions", "execution_hash")
