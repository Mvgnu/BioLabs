"""add public and fork fields to protocol templates"""

from alembic import op
import sqlalchemy as sa
from typing import Sequence, Union

revision: str = '476a303c6afe'
down_revision: Union[str, Sequence[str], None] = 'ff4b75d7cabc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('protocol_templates', sa.Column('is_public', sa.Boolean(), nullable=True, server_default=sa.false()))
    op.add_column('protocol_templates', sa.Column('forked_from', sa.UUID(), sa.ForeignKey('protocol_templates.id'), nullable=True))


def downgrade() -> None:
    op.drop_column('protocol_templates', 'forked_from')
    op.drop_column('protocol_templates', 'is_public')
