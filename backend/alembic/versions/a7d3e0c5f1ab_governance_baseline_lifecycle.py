"""governance baseline lifecycle tables

Revision ID: a7d3e0c5f1ab
Revises: ff4b75d7cabc
Create Date: 2025-07-20 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7d3e0c5f1ab"
down_revision: Union[str, Sequence[str], None] = "ff4b75d7cabc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create governance baseline lifecycle tables."""

    op.create_table(
        "governance_baseline_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("execution_id", sa.UUID(), nullable=False),
        sa.Column("template_id", sa.UUID(), nullable=True),
        sa.Column("team_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("labels", sa.JSON(), nullable=False),
        sa.Column("reviewer_ids", sa.JSON(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("submitted_by_id", sa.UUID(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_by_id", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("published_by_id", sa.UUID(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("publish_notes", sa.Text(), nullable=True),
        sa.Column("rollback_of_id", sa.UUID(), nullable=True),
        sa.Column("rolled_back_by_id", sa.UUID(), nullable=True),
        sa.Column("rolled_back_at", sa.DateTime(), nullable=True),
        sa.Column("rollback_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["execution_id"], ["protocol_executions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_id"], ["protocol_templates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["submitted_by_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["published_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["rolled_back_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["rollback_of_id"], ["governance_baseline_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "template_id", "version_number", name="uq_governance_baseline_template_version"
        ),
        sa.CheckConstraint(
            "status IN ('submitted', 'approved', 'rejected', 'published', 'rolled_back')",
            name="ck_governance_baseline_status",
        ),
    )
    op.create_index(
        "ix_governance_baseline_versions_execution_id",
        "governance_baseline_versions",
        ["execution_id"],
    )
    op.create_index(
        "ix_governance_baseline_versions_template_id",
        "governance_baseline_versions",
        ["template_id"],
    )

    op.create_table(
        "governance_baseline_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("baseline_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("performed_by_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["baseline_id"], ["governance_baseline_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["performed_by_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_governance_baseline_events_baseline_id",
        "governance_baseline_events",
        ["baseline_id"],
    )


def downgrade() -> None:
    """Drop governance baseline lifecycle tables."""

    op.drop_index("ix_governance_baseline_events_baseline_id", table_name="governance_baseline_events")
    op.drop_table("governance_baseline_events")
    op.drop_index("ix_governance_baseline_versions_template_id", table_name="governance_baseline_versions")
    op.drop_index("ix_governance_baseline_versions_execution_id", table_name="governance_baseline_versions")
    op.drop_table("governance_baseline_versions")
