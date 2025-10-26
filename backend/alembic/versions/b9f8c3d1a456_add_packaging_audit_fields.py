"""add lifecycle audit fields to narrative exports"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b9f8c3d1a456"
down_revision = "ff4b75d7cabc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "execution_narrative_exports",
        sa.Column("artifact_manifest_digest", sa.String(), nullable=True),
    )
    op.add_column(
        "execution_narrative_exports",
        sa.Column(
            "packaging_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "execution_narrative_exports",
        sa.Column("packaged_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "execution_narrative_exports",
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "execution_narrative_exports",
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column(
        "execution_narrative_exports",
        "packaging_attempts",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("execution_narrative_exports", "retention_expires_at")
    op.drop_column("execution_narrative_exports", "retired_at")
    op.drop_column("execution_narrative_exports", "packaged_at")
    op.drop_column("execution_narrative_exports", "packaging_attempts")
    op.drop_column("execution_narrative_exports", "artifact_manifest_digest")
