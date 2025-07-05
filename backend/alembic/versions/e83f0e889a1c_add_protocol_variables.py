"""add protocol variables and workflow conditions"""

from alembic import op
import sqlalchemy as sa
from typing import Sequence, Union

revision: str = 'e83f0e889a1c'
down_revision: Union[str, Sequence[str], None] = 'ff4b75d7cabc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('protocol_templates', sa.Column('variables', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('protocol_templates', 'variables')
