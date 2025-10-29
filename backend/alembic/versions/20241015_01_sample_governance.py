"""Introduce freezer custody governance tables."""

from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20241015_01"
down_revision: str | Sequence[str] | None = "20241012_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "governance_freezer_units",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("facility_code", sa.String(length=128), nullable=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False, server_default="active"),
        sa.Column("guardrail_config", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("timezone('utc', now())")),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("timezone('utc', now())")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_governance_freezer_units_team_id", "governance_freezer_units", ["team_id"])
    op.create_index("ix_governance_freezer_units_status", "governance_freezer_units", ["status"])

    op.create_table(
        "governance_freezer_compartments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("freezer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("governance_freezer_units.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("governance_freezer_compartments.id", ondelete="CASCADE"), nullable=True),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("position_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("guardrail_thresholds", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("timezone('utc', now())")),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("timezone('utc', now())")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_governance_freezer_compartments_freezer_id", "governance_freezer_compartments", ["freezer_id"])
    op.create_index("ix_governance_freezer_compartments_parent_id", "governance_freezer_compartments", ["parent_id"])

    op.create_table(
        "governance_sample_custody_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dna_asset_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("planner_session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cloning_planner_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("compartment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("governance_freezer_compartments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("custody_action", sa.String(length=128), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("quantity_units", sa.String(length=64), nullable=True),
        sa.Column("performed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("performed_for_team_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="SET NULL"), nullable=True),
        sa.Column("guardrail_flags", sa.JSON(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("performed_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("timezone('utc', now())")),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("timezone('utc', now())")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_governance_sample_custody_logs_asset_version_id", "governance_sample_custody_logs", ["asset_version_id"])
    op.create_index("ix_governance_sample_custody_logs_planner_session_id", "governance_sample_custody_logs", ["planner_session_id"])
    op.create_index("ix_governance_sample_custody_logs_compartment_id", "governance_sample_custody_logs", ["compartment_id"])


def downgrade() -> None:
    op.drop_index("ix_governance_sample_custody_logs_compartment_id", table_name="governance_sample_custody_logs")
    op.drop_index("ix_governance_sample_custody_logs_planner_session_id", table_name="governance_sample_custody_logs")
    op.drop_index("ix_governance_sample_custody_logs_asset_version_id", table_name="governance_sample_custody_logs")
    op.drop_table("governance_sample_custody_logs")
    op.drop_index("ix_governance_freezer_compartments_parent_id", table_name="governance_freezer_compartments")
    op.drop_index("ix_governance_freezer_compartments_freezer_id", table_name="governance_freezer_compartments")
    op.drop_table("governance_freezer_compartments")
    op.drop_index("ix_governance_freezer_units_status", table_name="governance_freezer_units")
    op.drop_index("ix_governance_freezer_units_team_id", table_name="governance_freezer_units")
    op.drop_table("governance_freezer_units")
