"""add provenance fields to dna repository releases

Revision ID: 20241029_01
Revises: 20241028_01_dna_federation_channels
Create Date: 2025-10-29 22:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20241029_01"
down_revision = "20241028_01_dna_federation_channels"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dna_repository_releases",
        sa.Column("planner_session_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "dna_repository_releases",
        sa.Column(
            "lifecycle_snapshot",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "dna_repository_releases",
        sa.Column(
            "mitigation_history",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "dna_repository_releases",
        sa.Column(
            "replay_checkpoint",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_index(
        "ix_dna_repository_releases_planner_session_id",
        "dna_repository_releases",
        ["planner_session_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_dna_repository_releases_planner_session",
        "dna_repository_releases",
        "cloning_planner_sessions",
        ["planner_session_id"],
        ["id"],
        ondelete="SET NULL",
    )



def downgrade() -> None:
    op.drop_constraint(
        "fk_dna_repository_releases_planner_session",
        "dna_repository_releases",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_dna_repository_releases_planner_session_id",
        table_name="dna_repository_releases",
    )
    op.drop_column("dna_repository_releases", "replay_checkpoint")
    op.drop_column("dna_repository_releases", "mitigation_history")
    op.drop_column("dna_repository_releases", "lifecycle_snapshot")
    op.drop_column("dna_repository_releases", "planner_session_id")
