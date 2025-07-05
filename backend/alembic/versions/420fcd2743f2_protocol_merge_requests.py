"""add protocol merge request table"""

from alembic import op
import sqlalchemy as sa
from typing import Sequence, Union

revision: str = '420fcd2743f2'
down_revision: Union[str, Sequence[str], None] = '476a303c6afe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'protocol_merge_requests',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('template_id', sa.UUID(), sa.ForeignKey('protocol_templates.id')),
        sa.Column('proposer_id', sa.UUID(), sa.ForeignKey('users.id')),
        sa.Column('content', sa.String(), nullable=False),
        sa.Column('variables', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(), nullable=True, server_default='open'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('protocol_merge_requests')
