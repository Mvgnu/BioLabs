"""DNA asset lifecycle foundation."""

from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20241010_02"
down_revision: str | Sequence[str] | None = "20241008_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dna_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False, server_default="draft"),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("latest_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dna_assets_team_id", "dna_assets", ["team_id"])
    op.create_index("ix_dna_assets_status", "dna_assets", ["status"])

    op.create_table(
        "dna_asset_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dna_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_index", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Text(), nullable=False),
        sa.Column("sequence_checksum", sa.String(length=128), nullable=False),
        sa.Column("sequence_length", sa.Integer(), nullable=False),
        sa.Column("gc_content", sa.Float(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id", "version_index", name="uq_dna_asset_version_index"),
    )
    op.create_index("ix_dna_asset_versions_asset_id", "dna_asset_versions", ["asset_id"])

    op.create_table(
        "dna_asset_annotations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dna_asset_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("feature_type", sa.String(length=128), nullable=False),
        sa.Column("start", sa.Integer(), nullable=False),
        sa.Column("end", sa.Integer(), nullable=False),
        sa.Column("strand", sa.Integer(), nullable=True),
        sa.Column("qualifiers", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dna_asset_annotations_version_id", "dna_asset_annotations", ["version_id"])

    op.create_table(
        "dna_asset_tags",
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["dna_assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("asset_id", "tag"),
    )

    op.create_table(
        "dna_asset_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dna_asset_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("files.id", ondelete="SET NULL"), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "dna_asset_guardrail_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dna_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dna_asset_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dna_asset_guardrail_events_asset_id", "dna_asset_guardrail_events", ["asset_id"])

    op.create_foreign_key(
        "fk_dna_assets_latest_version_id",
        "dna_assets",
        "dna_asset_versions",
        ["latest_version_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_dna_assets_latest_version_id", "dna_assets", type_="foreignkey")
    op.drop_index("ix_dna_asset_guardrail_events_asset_id", table_name="dna_asset_guardrail_events")
    op.drop_table("dna_asset_guardrail_events")
    op.drop_table("dna_asset_attachments")
    op.drop_table("dna_asset_tags")
    op.drop_index("ix_dna_asset_annotations_version_id", table_name="dna_asset_annotations")
    op.drop_table("dna_asset_annotations")
    op.drop_index("ix_dna_asset_versions_asset_id", table_name="dna_asset_versions")
    op.drop_table("dna_asset_versions")
    op.drop_index("ix_dna_assets_status", table_name="dna_assets")
    op.drop_index("ix_dna_assets_team_id", table_name="dna_assets")
    op.drop_table("dna_assets")

