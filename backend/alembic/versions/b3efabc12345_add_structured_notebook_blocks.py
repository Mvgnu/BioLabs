"""add structured blocks to notebook entries"""

from alembic import op
import sqlalchemy as sa
from typing import Sequence, Union

revision: str = 'b3efabc12345'
down_revision: Union[str, Sequence[str], None] = 'e83f0e889a1c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('notebook_entries', sa.Column('blocks', sa.JSON(), nullable=True))
    op.add_column('notebook_entry_versions', sa.Column('blocks', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('notebook_entry_versions', 'blocks')
    op.drop_column('notebook_entries', 'blocks')
