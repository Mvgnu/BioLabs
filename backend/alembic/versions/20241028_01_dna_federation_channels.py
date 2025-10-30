"""dna federation links and release channels"""
"""dna federation links and release channels"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20241028_01"
down_revision: str | Sequence[str] | None = "20241022_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dna_repository_federation_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_repository_id", sa.String(length=255), nullable=False),
        sa.Column("external_organization", sa.String(length=255), nullable=False),
        sa.Column(
            "trust_state",
            sa.String(length=64),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "permissions",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "guardrail_contract",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("last_attested_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint([
            "repository_id"
        ], ["dna_repositories.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "repository_id",
            "external_repository_id",
            name="uq_dna_repository_federation_peer",
        ),
    )
    op.create_index(
        "ix_dna_repository_federation_links_repository_id",
        "dna_repository_federation_links",
        ["repository_id"],
    )

    op.create_table(
        "dna_repository_federation_attestations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("link_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("release_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("attestor_organization", sa.String(length=255), nullable=False),
        sa.Column("attestor_contact", sa.String(length=255), nullable=True),
        sa.Column(
            "guardrail_summary",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("provenance_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint([
            "link_id"
        ], ["dna_repository_federation_links.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint([
            "release_id"
        ], ["dna_repository_releases.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint([
            "created_by_id"
        ], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_dna_repository_federation_attestations_link_id",
        "dna_repository_federation_attestations",
        ["link_id"],
    )
    op.create_index(
        "ix_dna_repository_federation_attestations_release_id",
        "dna_repository_federation_attestations",
        ["release_id"],
    )

    op.create_table(
        "dna_repository_release_channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("federation_link_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "audience_scope",
            sa.String(length=64),
            nullable=False,
            server_default="internal",
        ),
        sa.Column(
            "guardrail_profile",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint([
            "repository_id"
        ], ["dna_repositories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint([
            "federation_link_id"
        ], ["dna_repository_federation_links.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "repository_id",
            "slug",
            name="uq_dna_repository_release_channel",
        ),
    )
    op.create_index(
        "ix_dna_repository_release_channels_repository_id",
        "dna_repository_release_channels",
        ["repository_id"],
    )
    op.create_index(
        "ix_dna_repository_release_channels_federation_link_id",
        "dna_repository_release_channels",
        ["federation_link_id"],
    )

    op.create_table(
        "dna_repository_release_channel_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("release_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("version_label", sa.String(length=255), nullable=False),
        sa.Column(
            "guardrail_attestation",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "provenance_snapshot",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("mitigation_digest", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint([
            "channel_id"
        ], ["dna_repository_release_channels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint([
            "release_id"
        ], ["dna_repository_releases.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "channel_id",
            "sequence",
            name="uq_dna_repository_channel_sequence",
        ),
    )
    op.create_index(
        "ix_dna_repository_release_channel_versions_channel_id",
        "dna_repository_release_channel_versions",
        ["channel_id"],
    )
    op.create_index(
        "ix_dna_repository_release_channel_versions_release_id",
        "dna_repository_release_channel_versions",
        ["release_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_dna_repository_release_channel_versions_release_id",
        table_name="dna_repository_release_channel_versions",
    )
    op.drop_index(
        "ix_dna_repository_release_channel_versions_channel_id",
        table_name="dna_repository_release_channel_versions",
    )
    op.drop_table("dna_repository_release_channel_versions")

    op.drop_index(
        "ix_dna_repository_release_channels_federation_link_id",
        table_name="dna_repository_release_channels",
    )
    op.drop_index(
        "ix_dna_repository_release_channels_repository_id",
        table_name="dna_repository_release_channels",
    )
    op.drop_table("dna_repository_release_channels")

    op.drop_index(
        "ix_dna_repository_federation_attestations_release_id",
        table_name="dna_repository_federation_attestations",
    )
    op.drop_index(
        "ix_dna_repository_federation_attestations_link_id",
        table_name="dna_repository_federation_attestations",
    )
    op.drop_table("dna_repository_federation_attestations")

    op.drop_index(
        "ix_dna_repository_federation_links_repository_id",
        table_name="dna_repository_federation_links",
    )
    op.drop_table("dna_repository_federation_links")
