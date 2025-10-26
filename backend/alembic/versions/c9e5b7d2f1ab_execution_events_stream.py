"""create execution events stream table

Revision ID: c9e5b7d2f1ab
Revises: 5e3d29cf5af1
Create Date: 2025-08-01 00:00:00
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c9e5b7d2f1ab"
down_revision = "5e3d29cf5af1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_events",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("execution_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("actor_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["execution_id"], ["protocol_executions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.UniqueConstraint("execution_id", "sequence", name="uq_execution_event_sequence"),
    )
    op.create_index(
        "ix_execution_events_execution_id_created_at",
        "execution_events",
        ["execution_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_execution_events_execution_id_created_at", table_name="execution_events")
    op.drop_table("execution_events")
