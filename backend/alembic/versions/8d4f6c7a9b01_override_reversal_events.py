from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "8d4f6c7a9b01"
down_revision: str | Sequence[str] | None = "7c8d21f34abc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create reversal event bookkeeping for governance overrides."""

    op.create_table(
        "governance_override_reversal_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("override_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("baseline_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reversed_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("cooldown_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["override_id"], ["governance_override_actions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["baseline_id"], ["governance_baseline_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reversed_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_governance_override_reversal_events_cooldown",
        "governance_override_reversal_events",
        ["cooldown_expires_at"],
    )
    op.create_index(
        "ix_governance_override_reversal_events_created",
        "governance_override_reversal_events",
        ["created_at"],
    )


def downgrade() -> None:
    """Drop reversal bookkeeping artefacts."""

    op.drop_index(
        "ix_governance_override_reversal_events_created",
        table_name="governance_override_reversal_events",
    )
    op.drop_index(
        "ix_governance_override_reversal_events_cooldown",
        table_name="governance_override_reversal_events",
    )
    op.drop_table("governance_override_reversal_events")
