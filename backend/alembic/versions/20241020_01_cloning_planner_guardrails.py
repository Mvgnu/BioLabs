"""Link cloning planner sessions to protocol guardrails."""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20241020_01"
down_revision: str | Sequence[str] | None = "20241015_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cloning_planner_sessions",
        sa.Column(
            "protocol_execution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("protocol_executions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_cloning_planner_sessions_protocol_execution_id",
        "cloning_planner_sessions",
        ["protocol_execution_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_cloning_planner_sessions_protocol_execution_id",
        table_name="cloning_planner_sessions",
    )
    op.drop_column("cloning_planner_sessions", "protocol_execution_id")
