"""Enterprise compliance residency and legal holds."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


# revision identifiers, used by Alembic.
revision = "20241106_enterprise_compliance_controls"
down_revision = "20241030_community_portfolios"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("slug", sa.String(), nullable=False, unique=True),
        sa.Column("primary_region", sa.String(), nullable=False),
        sa.Column("residency_enforced", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "allowed_regions",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "encryption_policy",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "retention_policy",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.add_column(
        "teams",
        sa.Column("organization_id", pg.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_teams_organization",
        "teams",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "organization_residency_policies",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("data_domain", sa.String(), nullable=False),
        sa.Column(
            "allowed_regions",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("default_region", sa.String(), nullable=False),
        sa.Column("encryption_at_rest", sa.String(), nullable=False),
        sa.Column("encryption_in_transit", sa.String(), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False, server_default="365"),
        sa.Column("audit_interval_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column(
            "guardrail_flags",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("organization_id", "data_domain", name="uq_org_residency_domain"),
    )

    op.create_table(
        "organization_legal_holds",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_type", sa.String(), nullable=False),
        sa.Column("scope_reference", sa.String(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("initiated_by_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("released_by_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("release_notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["initiated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["released_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_organization_legal_holds_status",
        "organization_legal_holds",
        ["status"],
    )

    op.add_column("compliance_records", sa.Column("organization_id", pg.UUID(as_uuid=True), nullable=True))
    op.add_column("compliance_records", sa.Column("region", sa.String(), nullable=True))
    op.add_column(
        "compliance_records",
        sa.Column("data_domain", sa.String(), nullable=False, server_default="general"),
    )
    op.add_column(
        "compliance_records",
        sa.Column(
            "encryption_profile",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "compliance_records",
        sa.Column("retention_period_days", sa.Integer(), nullable=True),
    )
    op.add_column(
        "compliance_records",
        sa.Column(
            "guardrail_flags",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "compliance_records",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_foreign_key(
        "fk_compliance_records_organization",
        "compliance_records",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_compliance_records_org_status",
        "compliance_records",
        ["organization_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_compliance_records_org_status", table_name="compliance_records")
    op.drop_constraint("fk_compliance_records_organization", "compliance_records", type_="foreignkey")
    op.drop_column("compliance_records", "data_domain")
    op.drop_column("compliance_records", "updated_at")
    op.drop_column("compliance_records", "guardrail_flags")
    op.drop_column("compliance_records", "retention_period_days")
    op.drop_column("compliance_records", "encryption_profile")
    op.drop_column("compliance_records", "region")
    op.drop_column("compliance_records", "organization_id")

    op.drop_index("ix_organization_legal_holds_status", table_name="organization_legal_holds")
    op.drop_table("organization_legal_holds")

    op.drop_table("organization_residency_policies")

    op.drop_constraint("fk_teams_organization", "teams", type_="foreignkey")
    op.drop_column("teams", "organization_id")

    op.drop_table("organizations")
