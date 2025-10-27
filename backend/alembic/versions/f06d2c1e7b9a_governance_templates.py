"""governance workflow templates"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f06d2c1e7b9a"
down_revision: Union[str, Sequence[str], None] = "e9a1dfc4f712"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "execution_narrative_workflow_templates",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("template_key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "stage_blueprint",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("default_stage_sla_hours", sa.Integer(), nullable=True),
        sa.Column(
            "permitted_roles",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("forked_from_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_latest",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.ForeignKeyConstraint(
            ["forked_from_id"],
            ["execution_narrative_workflow_templates.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("template_key", "version", name="uq_template_key_version"),
    )

    op.create_table(
        "execution_narrative_workflow_template_assignments",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("template_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("team_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("protocol_template_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["execution_narrative_workflow_templates.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["protocol_template_id"],
            ["protocol_templates.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "(team_id IS NOT NULL) OR (protocol_template_id IS NOT NULL)",
            name="ck_template_assignment_target",
        ),
        sa.UniqueConstraint(
            "template_id",
            "team_id",
            name="uq_template_assignment_team",
        ),
        sa.UniqueConstraint(
            "template_id",
            "protocol_template_id",
            name="uq_template_assignment_protocol",
        ),
    )

    op.add_column(
        "execution_narrative_exports",
        sa.Column("workflow_template_key", sa.String(), nullable=True),
    )
    op.add_column(
        "execution_narrative_exports",
        sa.Column("workflow_template_version", sa.Integer(), nullable=True),
    )
    op.add_column(
        "execution_narrative_exports",
        sa.Column(
            "workflow_template_snapshot",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_foreign_key(
        "fk_execution_narrative_exports_template",
        "execution_narrative_exports",
        "execution_narrative_workflow_templates",
        ["workflow_template_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column(
        "execution_narrative_workflow_templates",
        "version",
        server_default=None,
    )
    op.alter_column(
        "execution_narrative_workflow_templates",
        "stage_blueprint",
        server_default=None,
    )
    op.alter_column(
        "execution_narrative_workflow_templates",
        "permitted_roles",
        server_default=None,
    )
    op.alter_column(
        "execution_narrative_workflow_templates",
        "status",
        server_default=None,
    )
    op.alter_column(
        "execution_narrative_workflow_templates",
        "is_latest",
        server_default=None,
    )
    op.alter_column(
        "execution_narrative_workflow_template_assignments",
        "metadata",
        server_default=None,
    )
    op.alter_column(
        "execution_narrative_exports",
        "workflow_template_snapshot",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_execution_narrative_exports_template",
        "execution_narrative_exports",
        type_="foreignkey",
    )
    op.drop_column("execution_narrative_exports", "workflow_template_snapshot")
    op.drop_column("execution_narrative_exports", "workflow_template_version")
    op.drop_column("execution_narrative_exports", "workflow_template_key")
    op.drop_table("execution_narrative_workflow_template_assignments")
    op.drop_table("execution_narrative_workflow_templates")
