"""community portfolios and engagements"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


# revision identifiers, used by Alembic.
revision = "20241030_community_portfolios"
down_revision = "c3d7b6e1f9ad"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "community_portfolios",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("visibility", sa.String(), nullable=False, server_default="public"),
        sa.Column("license", sa.String(), nullable=False, server_default="CC-BY-4.0"),
        sa.Column("tags", sa.JSON(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("attribution", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("provenance", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "mitigation_history",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "replay_checkpoints",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "guardrail_flags",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "engagement_score", sa.Float(), nullable=False, server_default=sa.text("0"),
        ),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("published_at", sa.DateTime(), nullable=True),
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
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_unique_constraint("uq_community_portfolios_slug", "community_portfolios", ["slug"])

    op.create_table(
        "community_portfolio_assets",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "portfolio_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("community_portfolios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("asset_type", sa.String(), nullable=False),
        sa.Column("asset_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_version_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("planner_session_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("guardrail_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_community_portfolio_assets_asset",
        "community_portfolio_assets",
        ["asset_type", "asset_id"],
    )

    op.create_table(
        "community_portfolio_engagements",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "portfolio_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("community_portfolios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("interaction", sa.String(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("portfolio_id", "user_id", "interaction"),
    )

    op.create_table(
        "community_moderation_events",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "portfolio_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("community_portfolios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "triggered_by_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("guardrail_flags", sa.JSON(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("outcome", sa.String(), nullable=False, server_default="pending"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("community_moderation_events")
    op.drop_table("community_portfolio_engagements")
    op.drop_index("ix_community_portfolio_assets_asset", table_name="community_portfolio_assets")
    op.drop_table("community_portfolio_assets")
    op.drop_constraint("uq_community_portfolios_slug", "community_portfolios", type_="unique")
    op.drop_table("community_portfolios")
