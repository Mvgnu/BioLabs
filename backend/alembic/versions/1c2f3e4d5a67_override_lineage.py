"""create governance override lineage table

Revision ID: 1c2f3e4d5a67
Revises: c8a9f6e7d123
Create Date: 2024-04-07 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "1c2f3e4d5a67"
down_revision = "c8a9f6e7d123"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "governance_override_lineages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "override_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("governance_override_actions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "scenario_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiment_preview_scenarios.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("scenario_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "notebook_entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("notebook_entries.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("notebook_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "captured_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "captured_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.UniqueConstraint("override_id", name="uq_override_lineage_override"),
    )
    op.create_index(
        "ix_override_lineage_scenario_id",
        "governance_override_lineages",
        ["scenario_id"],
        unique=False,
    )
    op.create_index(
        "ix_override_lineage_notebook_entry_id",
        "governance_override_lineages",
        ["notebook_entry_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_override_lineage_notebook_entry_id", table_name="governance_override_lineages")
    op.drop_index("ix_override_lineage_scenario_id", table_name="governance_override_lineages")
    op.drop_table("governance_override_lineages")
