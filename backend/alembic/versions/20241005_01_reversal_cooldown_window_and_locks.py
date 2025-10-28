from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20241005_01"
down_revision: str | Sequence[str] | None = "8d4f6c7a9b01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add cooldown window metadata and reversal locks."""

    op.add_column(
        "governance_override_reversal_events",
        sa.Column(
            "cooldown_window_minutes",
            sa.Integer(),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_governance_override_reversal_events_window_non_negative",
        "governance_override_reversal_events",
        "cooldown_window_minutes IS NULL OR cooldown_window_minutes >= 0",
    )
    op.create_index(
        "ix_governance_override_reversal_events_window",
        "governance_override_reversal_events",
        ["cooldown_window_minutes"],
    )

    op.add_column(
        "governance_override_actions",
        sa.Column("reversal_lock_token", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "governance_override_actions",
        sa.Column(
            "reversal_lock_acquired_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "governance_override_actions",
        sa.Column(
            "reversal_lock_actor_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_governance_override_actions_reversal_lock_token",
        "governance_override_actions",
        ["reversal_lock_token"],
    )
    op.create_foreign_key(
        "fk_governance_override_actions_reversal_lock_actor",
        "governance_override_actions",
        "users",
        ["reversal_lock_actor_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Remove cooldown window metadata and reversal locks."""

    op.drop_constraint(
        "fk_governance_override_actions_reversal_lock_actor",
        "governance_override_actions",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_governance_override_actions_reversal_lock_token",
        table_name="governance_override_actions",
    )
    op.drop_column("governance_override_actions", "reversal_lock_actor_id")
    op.drop_column("governance_override_actions", "reversal_lock_acquired_at")
    op.drop_column("governance_override_actions", "reversal_lock_token")

    op.drop_index(
        "ix_governance_override_reversal_events_window",
        table_name="governance_override_reversal_events",
    )
    op.drop_constraint(
        "ck_governance_override_reversal_events_window_non_negative",
        "governance_override_reversal_events",
        type_="check",
    )
    op.drop_column("governance_override_reversal_events", "cooldown_window_minutes")
