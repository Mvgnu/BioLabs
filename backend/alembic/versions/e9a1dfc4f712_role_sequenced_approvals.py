"""introduce staged approval workflow for narrative exports"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e9a1dfc4f712"
down_revision = "9d1e1af1a2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_narrative_approval_stages",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("export_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("required_role", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("sla_hours", sa.Integer(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assignee_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("delegated_to_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("overdue_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["export_id"], ["execution_narrative_exports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["delegated_to_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("export_id", "sequence_index", name="uq_approval_stage_export_sequence"),
    )
    op.create_index(
        "ix_execution_narrative_approval_stages_export_id",
        "execution_narrative_approval_stages",
        ["export_id"],
    )
    op.create_index(
        "ix_execution_narrative_approval_stages_assignee_id",
        "execution_narrative_approval_stages",
        ["assignee_id"],
    )
    op.create_index(
        "ix_execution_narrative_approval_stages_delegated_to_id",
        "execution_narrative_approval_stages",
        ["delegated_to_id"],
    )

    op.create_table(
        "execution_narrative_approval_actions",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("stage_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("action_type", sa.String(), nullable=False),
        sa.Column("signature", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("delegation_target_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["stage_id"], ["execution_narrative_approval_stages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["delegation_target_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_execution_narrative_approval_actions_stage_id",
        "execution_narrative_approval_actions",
        ["stage_id"],
    )
    op.create_index(
        "ix_execution_narrative_approval_actions_actor_id",
        "execution_narrative_approval_actions",
        ["actor_id"],
    )

    op.add_column(
        "execution_narrative_exports",
        sa.Column("approval_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "execution_narrative_exports",
        sa.Column(
            "approval_stage_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "execution_narrative_exports",
        sa.Column("workflow_template_id", sa.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "execution_narrative_exports",
        sa.Column("current_stage_id", sa.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "execution_narrative_exports",
        sa.Column("current_stage_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_execution_narrative_exports_current_stage",
        "execution_narrative_exports",
        "execution_narrative_approval_stages",
        ["current_stage_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column(
        "execution_narrative_exports",
        "approval_stage_count",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_execution_narrative_exports_current_stage",
        "execution_narrative_exports",
        type_="foreignkey",
    )
    op.drop_column("execution_narrative_exports", "current_stage_started_at")
    op.drop_column("execution_narrative_exports", "current_stage_id")
    op.drop_column("execution_narrative_exports", "workflow_template_id")
    op.drop_column("execution_narrative_exports", "approval_stage_count")
    op.drop_column("execution_narrative_exports", "approval_completed_at")

    op.drop_index(
        "ix_execution_narrative_approval_actions_actor_id",
        table_name="execution_narrative_approval_actions",
    )
    op.drop_index(
        "ix_execution_narrative_approval_actions_stage_id",
        table_name="execution_narrative_approval_actions",
    )
    op.drop_table("execution_narrative_approval_actions")

    op.drop_index(
        "ix_execution_narrative_approval_stages_delegated_to_id",
        table_name="execution_narrative_approval_stages",
    )
    op.drop_index(
        "ix_execution_narrative_approval_stages_assignee_id",
        table_name="execution_narrative_approval_stages",
    )
    op.drop_index(
        "ix_execution_narrative_approval_stages_export_id",
        table_name="execution_narrative_approval_stages",
    )
    op.drop_table("execution_narrative_approval_stages")
