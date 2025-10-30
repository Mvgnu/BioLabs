"""Expand sharing federation grants and channel scoping."""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20241013_01"
down_revision: str | Sequence[str] | None = "20241012_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dna_repository_federation_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "link_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dna_repository_federation_links.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("organization", sa.String(length=256), nullable=False),
        sa.Column("permission_tier", sa.String(length=64), nullable=False, server_default="reviewer"),
        sa.Column("guardrail_scope", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("handshake_state", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column(
            "requested_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "approved_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("link_id", "organization", name="uq_dna_repository_federation_grant_organization"),
    )
    op.create_index(
        "ix_dna_repository_federation_grants_link",
        "dna_repository_federation_grants",
        ["link_id"],
    )
    op.create_index(
        "ix_dna_repository_federation_grants_requested",
        "dna_repository_federation_grants",
        ["requested_by_id"],
    )
    op.create_index(
        "ix_dna_repository_federation_grants_approved",
        "dna_repository_federation_grants",
        ["approved_by_id"],
    )

    op.add_column(
        "dna_repository_release_channel_versions",
        sa.Column(
            "grant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dna_repository_federation_grants.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_dna_repository_release_channel_versions_grant",
        "dna_repository_release_channel_versions",
        ["grant_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_dna_repository_release_channel_versions_grant",
        table_name="dna_repository_release_channel_versions",
    )
    op.drop_column("dna_repository_release_channel_versions", "grant_id")

    op.drop_index(
        "ix_dna_repository_federation_grants_approved",
        table_name="dna_repository_federation_grants",
    )
    op.drop_index(
        "ix_dna_repository_federation_grants_requested",
        table_name="dna_repository_federation_grants",
    )
    op.drop_index(
        "ix_dna_repository_federation_grants_link",
        table_name="dna_repository_federation_grants",
    )
    op.drop_table("dna_repository_federation_grants")
