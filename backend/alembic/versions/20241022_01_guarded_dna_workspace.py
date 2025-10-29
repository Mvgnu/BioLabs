from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from typing import Sequence


# revision identifiers, used by Alembic.
revision: str = "20241022_01"
down_revision: str | Sequence[str] | None = "20241020_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dna_repositories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "guardrail_policy",
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
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("slug", name="uq_dna_repository_slug"),
    )
    op.create_index(
        "ix_dna_repositories_owner_id",
        "dna_repositories",
        ["owner_id"],
        unique=False,
    )
    op.create_index(
        "ix_dna_repositories_team_id",
        "dna_repositories",
        ["team_id"],
        unique=False,
    )

    op.create_table(
        "dna_repository_collaborators",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False, server_default="contributor"),
        sa.Column(
            "invitation_status",
            sa.String(length=32),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "meta",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"], ["dna_repositories.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "repository_id",
            "user_id",
            name="uq_dna_repository_collaborator",
        ),
    )
    op.create_index(
        "ix_dna_repository_collaborators_repository_id",
        "dna_repository_collaborators",
        ["repository_id"],
        unique=False,
    )
    op.create_index(
        "ix_dna_repository_collaborators_user_id",
        "dna_repository_collaborators",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "dna_repository_releases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "guardrail_state",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "guardrail_snapshot",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("mitigation_summary", sa.Text(), nullable=True),
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
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["repository_id"], ["dna_repositories.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "repository_id",
            "version",
            name="uq_dna_repository_release_version",
        ),
    )
    op.create_index(
        "ix_dna_repository_releases_repository_id",
        "dna_repository_releases",
        ["repository_id"],
        unique=False,
    )
    op.create_index(
        "ix_dna_repository_releases_status",
        "dna_repository_releases",
        ["status"],
        unique=False,
    )

    op.create_table(
        "dna_repository_release_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("release_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approver_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "guardrail_flags",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["release_id"], ["dna_repository_releases.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["approver_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "release_id",
            "approver_id",
            name="uq_dna_repository_release_approver",
        ),
    )
    op.create_index(
        "ix_dna_repository_release_approvals_release_id",
        "dna_repository_release_approvals",
        ["release_id"],
        unique=False,
    )

    op.create_table(
        "dna_repository_timeline_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("release_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column(
            "payload",
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
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["repository_id"], ["dna_repositories.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["release_id"], ["dna_repository_releases.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_dna_repository_timeline_events_repository_id",
        "dna_repository_timeline_events",
        ["repository_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_dna_repository_timeline_events_repository_id",
        table_name="dna_repository_timeline_events",
    )
    op.drop_table("dna_repository_timeline_events")

    op.drop_index(
        "ix_dna_repository_release_approvals_release_id",
        table_name="dna_repository_release_approvals",
    )
    op.drop_table("dna_repository_release_approvals")

    op.drop_index(
        "ix_dna_repository_releases_status",
        table_name="dna_repository_releases",
    )
    op.drop_index(
        "ix_dna_repository_releases_repository_id",
        table_name="dna_repository_releases",
    )
    op.drop_table("dna_repository_releases")

    op.drop_index(
        "ix_dna_repository_collaborators_user_id",
        table_name="dna_repository_collaborators",
    )
    op.drop_index(
        "ix_dna_repository_collaborators_repository_id",
        table_name="dna_repository_collaborators",
    )
    op.drop_table("dna_repository_collaborators")

    op.drop_index("ix_dna_repositories_team_id", table_name="dna_repositories")
    op.drop_index("ix_dna_repositories_owner_id", table_name="dna_repositories")
    op.drop_table("dna_repositories")
