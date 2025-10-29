from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from typing import Sequence

# revision identifiers, used by Alembic.
revision: str = "20241025_01"
down_revision: str | Sequence[str] | None = "20241022_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inventory_items",
        sa.Column("custody_state", sa.String(), nullable=True, server_default="idle"),
    )
    op.add_column(
        "inventory_items",
        sa.Column("custody_snapshot", postgresql.JSONB(), nullable=True, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "governance_sample_custody_logs",
        sa.Column(
            "inventory_item_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_governance_sample_custody_logs_inventory_item_id",
        "governance_sample_custody_logs",
        ["inventory_item_id"],
    )
    op.create_foreign_key(
        "fk_governance_sample_custody_logs_inventory_item_id",
        "governance_sample_custody_logs",
        "inventory_items",
        ["inventory_item_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        "UPDATE inventory_items SET custody_state='idle' WHERE custody_state IS NULL"
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_governance_sample_custody_logs_inventory_item_id",
        "governance_sample_custody_logs",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_governance_sample_custody_logs_inventory_item_id",
        table_name="governance_sample_custody_logs",
    )
    op.drop_column("governance_sample_custody_logs", "inventory_item_id")
    op.drop_column("inventory_items", "custody_snapshot")
    op.drop_column("inventory_items", "custody_state")
