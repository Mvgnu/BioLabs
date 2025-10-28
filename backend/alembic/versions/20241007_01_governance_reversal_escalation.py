"""Embed escalation tiers into reversal locks."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20241007_01"
down_revision: str | Sequence[str] | None = "20241006_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "governance_override_actions",
        sa.Column("reversal_lock_tier_key", sa.String(), nullable=True),
    )
    op.add_column(
        "governance_override_actions",
        sa.Column("reversal_lock_tier", sa.String(), nullable=True),
    )
    op.add_column(
        "governance_override_actions",
        sa.Column("reversal_lock_tier_level", sa.Integer(), nullable=True),
    )
    op.add_column(
        "governance_override_actions",
        sa.Column("reversal_lock_scope", sa.String(), nullable=True),
    )

    op.create_table(
        "governance_override_lock_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "override_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("governance_override_actions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("lock_token", sa.String(length=64), nullable=True),
        sa.Column("tier_key", sa.String(), nullable=True),
        sa.Column("tier", sa.String(), nullable=True),
        sa.Column("tier_level", sa.Integer(), nullable=True),
        sa.Column("scope", sa.String(), nullable=True),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_governance_override_lock_events_override_id",
        "governance_override_lock_events",
        ["override_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_governance_override_lock_events_override_id",
        table_name="governance_override_lock_events",
    )
    op.drop_table("governance_override_lock_events")
    op.drop_column("governance_override_actions", "reversal_lock_scope")
    op.drop_column("governance_override_actions", "reversal_lock_tier_level")
    op.drop_column("governance_override_actions", "reversal_lock_tier")
    op.drop_column("governance_override_actions", "reversal_lock_tier_key")
