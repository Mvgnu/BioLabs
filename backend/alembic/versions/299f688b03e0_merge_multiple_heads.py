"""merge multiple heads

Revision ID: 299f688b03e0
Revises: 2345b6789abc, 77a76f367d0f, a1e430d0e9d9, c1a2b3c4d5e6
Create Date: 2025-07-04 22:09:19.291905

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '299f688b03e0'
down_revision: Union[str, Sequence[str], None] = ('2345b6789abc', '77a76f367d0f', 'a1e430d0e9d9', 'c1a2b3c4d5e6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
