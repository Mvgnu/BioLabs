"""add field definition constraint

Revision ID: d69c2eb94812
Revises: 74cfc64cc205
Create Date: 2025-07-03 20:08:07.466069

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd69c2eb94812'
down_revision: Union[str, Sequence[str], None] = '74cfc64cc205'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_unique_constraint(
        "uq_field_def",
        "field_definitions",
        ["entity_type", "field_key", "team_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "uq_field_def",
        "field_definitions",
        type_="unique",
    )
