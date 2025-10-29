"""Durable cloning planner checkpoints and QC artifacts."""

from __future__ import annotations

from typing import Sequence
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20241012_01"
down_revision: str | Sequence[str] | None = "20241010_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cloning_planner_stage_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cloning_planner_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.String(length=128), nullable=True),
        sa.Column("payload_path", sa.String(length=512), nullable=True),
        sa.Column("payload_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("guardrail_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("metrics", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("review_state", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cloning_planner_stage_records_session_stage",
        "cloning_planner_stage_records",
        ["session_id", "stage"],
    )
    op.create_index(
        "ix_cloning_planner_stage_records_created_at",
        "cloning_planner_stage_records",
        ["created_at"],
    )

    op.create_table(
        "cloning_planner_qc_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cloning_planner_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "stage_record_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cloning_planner_stage_records.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("artifact_name", sa.String(length=128), nullable=True),
        sa.Column("sample_id", sa.String(length=128), nullable=True),
        sa.Column("trace_path", sa.String(length=512), nullable=True),
        sa.Column("storage_path", sa.String(length=512), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("thresholds", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("reviewer_decision", sa.String(length=32), nullable=True),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column(
            "reviewer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cloning_planner_qc_artifacts_session",
        "cloning_planner_qc_artifacts",
        ["session_id"],
    )
    op.create_index(
        "ix_cloning_planner_qc_artifacts_stage_record",
        "cloning_planner_qc_artifacts",
        ["stage_record_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_cloning_planner_qc_artifacts_stage_record",
        table_name="cloning_planner_qc_artifacts",
    )
    op.drop_index(
        "ix_cloning_planner_qc_artifacts_session",
        table_name="cloning_planner_qc_artifacts",
    )
    op.drop_table("cloning_planner_qc_artifacts")
    op.drop_index(
        "ix_cloning_planner_stage_records_created_at",
        table_name="cloning_planner_stage_records",
    )
    op.drop_index(
        "ix_cloning_planner_stage_records_session_stage",
        table_name="cloning_planner_stage_records",
    )
    op.drop_table("cloning_planner_stage_records")
