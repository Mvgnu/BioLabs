"""governance snapshots and audit log"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "1f2e3d4c5b67"
down_revision = "f06d2c1e7b9a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_narrative_workflow_template_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_key", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("captured_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["captured_by_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["template_id"], ["execution_narrative_workflow_templates.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("template_id", "version", name="uq_template_snapshot_version"),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_template_snapshot_status",
        ),
    )
    op.create_index(
        op.f("ix_execution_narrative_workflow_template_snapshots_template_id"),
        "execution_narrative_workflow_template_snapshots",
        ["template_id"],
        unique=False,
    )

    op.create_table(
        "governance_template_audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["execution_narrative_workflow_template_snapshots.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["template_id"], ["execution_narrative_workflow_templates.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.add_column(
        "execution_narrative_workflow_templates",
        sa.Column("published_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_execution_templates_published_snapshot",
        "execution_narrative_workflow_templates",
        "execution_narrative_workflow_template_snapshots",
        ["published_snapshot_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_template_lifecycle_status",
        "execution_narrative_workflow_templates",
        "status IN ('draft', 'published', 'archived')",
    )

    op.add_column(
        "execution_narrative_exports",
        sa.Column("workflow_template_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_execution_exports_snapshot",
        "execution_narrative_exports",
        "execution_narrative_workflow_template_snapshots",
        ["workflow_template_snapshot_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_execution_exports_snapshot",
        "execution_narrative_exports",
        type_="foreignkey",
    )
    op.drop_column("execution_narrative_exports", "workflow_template_snapshot_id")

    op.drop_constraint("ck_template_lifecycle_status", "execution_narrative_workflow_templates", type_="check")
    op.drop_constraint(
        "fk_execution_templates_published_snapshot",
        "execution_narrative_workflow_templates",
        type_="foreignkey",
    )
    op.drop_column("execution_narrative_workflow_templates", "published_snapshot_id")

    op.drop_table("governance_template_audit_logs")
    op.drop_index(
        op.f("ix_execution_narrative_workflow_template_snapshots_template_id"),
        table_name="execution_narrative_workflow_template_snapshots",
    )
    op.drop_table("execution_narrative_workflow_template_snapshots")
