"""collaborative scenarios enhancements

Revision ID: c3d7b6e1f9ad
Revises: ff4b75d7cabc
Create Date: 2025-08-30 12:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c3d7b6e1f9ad"
down_revision = "ff4b75d7cabc"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "experiment_preview_scenario_folders",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "execution_id",
            sa.UUID(),
            sa.ForeignKey("protocol_executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("team_id", sa.UUID(), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("visibility", sa.String(), nullable=False, server_default="private"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.add_column(
        "experiment_preview_scenarios",
        sa.Column("folder_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "experiment_preview_scenarios",
        sa.Column(
            "is_shared",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "experiment_preview_scenarios",
        sa.Column(
            "shared_team_ids",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "experiment_preview_scenarios",
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "experiment_preview_scenarios",
        sa.Column("timeline_event_id", sa.UUID(), nullable=True),
    )

    op.create_index(
        "ix_experiment_preview_scenarios_folder_id",
        "experiment_preview_scenarios",
        ["folder_id"],
    )
    op.create_foreign_key(
        "fk_scenarios_folder",
        "experiment_preview_scenarios",
        "experiment_preview_scenario_folders",
        ["folder_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_scenarios_timeline_event",
        "experiment_preview_scenarios",
        "execution_events",
        ["timeline_event_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint("fk_scenarios_timeline_event", "experiment_preview_scenarios", type_="foreignkey")
    op.drop_constraint("fk_scenarios_folder", "experiment_preview_scenarios", type_="foreignkey")
    op.drop_index("ix_experiment_preview_scenarios_folder_id", table_name="experiment_preview_scenarios")
    op.drop_column("experiment_preview_scenarios", "timeline_event_id")
    op.drop_column("experiment_preview_scenarios", "expires_at")
    op.drop_column("experiment_preview_scenarios", "shared_team_ids")
    op.drop_column("experiment_preview_scenarios", "is_shared")
    op.drop_column("experiment_preview_scenarios", "folder_id")
    op.drop_table("experiment_preview_scenario_folders")
