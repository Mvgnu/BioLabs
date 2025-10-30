"""Marketplace monetization and billing tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


# revision identifiers, used by Alembic.
revision = "20241110_marketplace_billing"
down_revision = "20241106_enterprise_compliance_controls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketplace_pricing_plans",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(), nullable=False, unique=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("billing_cadence", sa.String(), nullable=False, server_default="monthly"),
        sa.Column("base_price_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("credit_allowance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sla_tier", sa.String(), nullable=False, server_default="standard"),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "marketplace_plan_features",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("plan_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("feature_key", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["plan_id"], ["marketplace_pricing_plans.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("plan_id", "feature_key", name="uq_plan_feature_key"),
    )

    op.create_table(
        "marketplace_subscriptions",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("billing_email", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("renews_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sla_acceptance", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("current_credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["marketplace_pricing_plans.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("organization_id", "plan_id", name="uq_org_plan_active"),
    )

    op.create_table(
        "marketplace_usage_events",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("subscription_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("organization_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("team_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("service", sa.String(), nullable=False),
        sa.Column("operation", sa.String(), nullable=False),
        sa.Column("unit_quantity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("credits_consumed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("guardrail_flags", sa.JSON(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["subscription_id"], ["marketplace_subscriptions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.Index("ix_usage_events_service_operation", "service", "operation"),
        sa.Index("ix_usage_events_org_time", "organization_id", "occurred_at"),
    )

    op.create_table(
        "marketplace_invoices",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("subscription_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_number", sa.String(), nullable=False, unique=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount_due_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("credit_usage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("line_items", sa.JSON(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["subscription_id"], ["marketplace_subscriptions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "marketplace_credit_ledger",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("subscription_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("usage_event_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("delta_credits", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("running_balance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["subscription_id"], ["marketplace_subscriptions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usage_event_id"], ["marketplace_usage_events.id"], ondelete="SET NULL"),
        sa.Index("ix_credit_ledger_org_time", "organization_id", "created_at"),
    )


def downgrade() -> None:
    op.drop_table("marketplace_credit_ledger")
    op.drop_table("marketplace_invoices")
    op.drop_table("marketplace_usage_events")
    op.drop_table("marketplace_subscriptions")
    op.drop_table("marketplace_plan_features")
    op.drop_table("marketplace_pricing_plans")
