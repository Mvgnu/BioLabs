"""enhance_notification_model

Revision ID: 2b6b3907b253
Revises: 299f688b03e0
Create Date: 2025-07-05 00:38:22.673845

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2b6b3907b253'
down_revision: Union[str, Sequence[str], None] = '299f688b03e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add new columns to notifications table
    op.add_column('notifications', sa.Column('title', sa.String(), nullable=True))
    op.add_column('notifications', sa.Column('category', sa.String(), nullable=True))
    op.add_column('notifications', sa.Column('priority', sa.String(), nullable=False, server_default='medium'))
    op.add_column('notifications', sa.Column('meta', sa.JSON(), nullable=False, server_default='{}'))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove columns from notifications table
    op.drop_column('notifications', 'meta')
    op.drop_column('notifications', 'priority')
    op.drop_column('notifications', 'category')
    op.drop_column('notifications', 'title')
