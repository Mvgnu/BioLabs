from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20241008_01"
down_revision: str | Sequence[str] | None = "20241007_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cloning_planner_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("assembly_strategy", sa.String(length=64), nullable=False),
        sa.Column("input_sequences", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("primer_set", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("restriction_digest", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("assembly_plan", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("qc_reports", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("inventory_reservations", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("guardrail_state", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("stage_timings", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("current_step", sa.String(length=32), nullable=True),
        sa.Column("celery_task_id", sa.String(length=128), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cloning_planner_sessions_created_by_id",
        "cloning_planner_sessions",
        ["created_by_id"],
    )
    op.create_index(
        "ix_cloning_planner_sessions_status",
        "cloning_planner_sessions",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_cloning_planner_sessions_status",
        table_name="cloning_planner_sessions",
    )
    op.drop_index(
        "ix_cloning_planner_sessions_created_by_id",
        table_name="cloning_planner_sessions",
    )
    op.drop_table("cloning_planner_sessions")
