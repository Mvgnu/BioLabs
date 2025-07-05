"""add notebook signing fields and version table

Revision ID: a1e430d0e9d9
Revises: 9b1c3d8fc4a7
Create Date: 2025-07-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from typing import Sequence, Union

revision: str = 'a1e430d0e9d9'
down_revision: Union[str, Sequence[str], None] = '9b1c3d8fc4a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('notebook_entries', sa.Column('is_locked', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('notebook_entries', sa.Column('signed_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('notebook_entries', sa.Column('signed_at', sa.DateTime(), nullable=True))
    op.add_column('notebook_entries', sa.Column('witness_id', sa.UUID(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('notebook_entries', sa.Column('witnessed_at', sa.DateTime(), nullable=True))

    op.create_table(
        'notebook_entry_versions',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('entry_id', sa.UUID(), sa.ForeignKey('notebook_entries.id')),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('content', sa.String(), nullable=False),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('notebook_entry_versions')
    op.drop_column('notebook_entries', 'witnessed_at')
    op.drop_column('notebook_entries', 'witness_id')
    op.drop_column('notebook_entries', 'signed_at')
    op.drop_column('notebook_entries', 'signed_by')
    op.drop_column('notebook_entries', 'is_locked')
