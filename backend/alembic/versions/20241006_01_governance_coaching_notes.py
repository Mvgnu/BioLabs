"""Introduce governance coaching notes threading."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20241006_01"
down_revision: str | Sequence[str] | None = "20241005_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create governance coaching note persistence tables."""

    op.create_table(
        "governance_coaching_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("override_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("baseline_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("execution_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("thread_root_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("moderation_state", sa.String(), nullable=False, server_default="published"),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("last_edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["override_id"],
            ["governance_override_actions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["baseline_id"],
            ["governance_baseline_versions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["protocol_executions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["governance_coaching_notes.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["thread_root_id"],
            ["governance_coaching_notes.id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "moderation_state IN ('draft', 'published', 'flagged', 'resolved', 'removed')",
            name="ck_governance_coaching_notes_state",
        ),
    )
    op.create_index(
        "ix_governance_coaching_notes_override_id",
        "governance_coaching_notes",
        ["override_id"],
    )
    op.create_index(
        "ix_governance_coaching_notes_baseline_id",
        "governance_coaching_notes",
        ["baseline_id"],
    )
    op.create_index(
        "ix_governance_coaching_notes_execution_id",
        "governance_coaching_notes",
        ["execution_id"],
    )
    op.create_index(
        "ix_governance_coaching_notes_parent_id",
        "governance_coaching_notes",
        ["parent_id"],
    )
    op.create_index(
        "ix_governance_coaching_notes_thread_root_id",
        "governance_coaching_notes",
        ["thread_root_id"],
    )


def downgrade() -> None:
    """Drop governance coaching note persistence tables."""

    op.drop_index(
        "ix_governance_coaching_notes_thread_root_id",
        table_name="governance_coaching_notes",
    )
    op.drop_index(
        "ix_governance_coaching_notes_parent_id",
        table_name="governance_coaching_notes",
    )
    op.drop_index(
        "ix_governance_coaching_notes_execution_id",
        table_name="governance_coaching_notes",
    )
    op.drop_index(
        "ix_governance_coaching_notes_baseline_id",
        table_name="governance_coaching_notes",
    )
    op.drop_index(
        "ix_governance_coaching_notes_override_id",
        table_name="governance_coaching_notes",
    )
    op.drop_table("governance_coaching_notes")
