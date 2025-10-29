"""augment cloning planner branching metadata

Revision ID: ab12cd34ef56
Revises: c9e5b7d2f1ab
Create Date: 2025-09-14 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ab12cd34ef56"
down_revision = "c9e5b7d2f1ab"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cloning_planner_sessions",
        sa.Column("branch_state", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "cloning_planner_sessions",
        sa.Column("active_branch_id", sa.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "cloning_planner_sessions",
        sa.Column("timeline_cursor", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_cloning_planner_sessions_active_branch_id",
        "cloning_planner_sessions",
        ["active_branch_id"],
    )

    op.add_column(
        "cloning_planner_stage_records",
        sa.Column("branch_id", sa.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "cloning_planner_stage_records",
        sa.Column("checkpoint_key", sa.String(), nullable=True),
    )
    op.add_column(
        "cloning_planner_stage_records",
        sa.Column("checkpoint_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "cloning_planner_stage_records",
        sa.Column("guardrail_transition", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "cloning_planner_stage_records",
        sa.Column("timeline_position", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_cloning_planner_stage_records_branch_id",
        "cloning_planner_stage_records",
        ["branch_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_cloning_planner_stage_records_branch_id", table_name="cloning_planner_stage_records")
    op.drop_column("cloning_planner_stage_records", "timeline_position")
    op.drop_column("cloning_planner_stage_records", "guardrail_transition")
    op.drop_column("cloning_planner_stage_records", "checkpoint_payload")
    op.drop_column("cloning_planner_stage_records", "checkpoint_key")
    op.drop_column("cloning_planner_stage_records", "branch_id")

    op.drop_index("ix_cloning_planner_sessions_active_branch_id", table_name="cloning_planner_sessions")
    op.drop_column("cloning_planner_sessions", "timeline_cursor")
    op.drop_column("cloning_planner_sessions", "active_branch_id")
    op.drop_column("cloning_planner_sessions", "branch_state")
