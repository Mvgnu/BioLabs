"""add locations table

Revision ID: 9b1c3d8fc4a7
Revises: d69c2eb94812
Create Date: 2025-07-13 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from typing import Sequence, Union

revision: str = '9b1c3d8fc4a7'
down_revision: Union[str, Sequence[str], None] = 'd69c2eb94812'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'locations',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('parent_id', sa.UUID(), sa.ForeignKey('locations.id')),
        sa.Column('team_id', sa.UUID(), sa.ForeignKey('teams.id')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.add_column('inventory_items', sa.Column('location_id', sa.UUID(), sa.ForeignKey('locations.id')))


def downgrade() -> None:
    op.drop_column('inventory_items', 'location_id')
    op.drop_table('locations')
