"""add artifact metadata to execution narrative exports

Revision ID: 9d1e1af1a2b3
Revises: 299f688b03e0
Create Date: 2025-09-01 00:00:00
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "9d1e1af1a2b3"
down_revision = "299f688b03e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "execution_narrative_exports",
        sa.Column("artifact_status", sa.String(), nullable=False, server_default="queued"),
    )
    op.add_column(
        "execution_narrative_exports",
        sa.Column("artifact_file_id", sa.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "execution_narrative_exports",
        sa.Column("artifact_checksum", sa.String(), nullable=True),
    )
    op.add_column(
        "execution_narrative_exports",
        sa.Column("artifact_error", sa.String(), nullable=True),
    )
    op.create_foreign_key(
        "fk_execution_narrative_exports_artifact_file",
        "execution_narrative_exports",
        "files",
        ["artifact_file_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column(
        "execution_narrative_exports",
        "artifact_status",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_execution_narrative_exports_artifact_file",
        "execution_narrative_exports",
        type_="foreignkey",
    )
    op.drop_column("execution_narrative_exports", "artifact_error")
    op.drop_column("execution_narrative_exports", "artifact_checksum")
    op.drop_column("execution_narrative_exports", "artifact_file_id")
    op.drop_column("execution_narrative_exports", "artifact_status")
