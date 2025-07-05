"""add protocol stars table"""

from alembic import op
import sqlalchemy as sa
from typing import Sequence, Union

revision: str = 'abcdef123456'
down_revision: Union[str, Sequence[str], None] = '12345abcde01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'protocol_stars',
        sa.Column('protocol_id', sa.UUID(as_uuid=True), sa.ForeignKey('protocol_templates.id'), primary_key=True),
        sa.Column('user_id', sa.UUID(as_uuid=True), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )


def downgrade() -> None:
    op.drop_table('protocol_stars')
