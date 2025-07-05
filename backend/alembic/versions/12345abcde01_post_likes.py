"""add post likes table"""

from alembic import op
import sqlalchemy as sa
from typing import Sequence, Union

revision: str = '12345abcde01'
down_revision: Union[str, Sequence[str], None] = '420fcd2743f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'post_likes',
        sa.Column('post_id', sa.UUID(as_uuid=True), sa.ForeignKey('posts.id'), primary_key=True),
        sa.Column('user_id', sa.UUID(as_uuid=True), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )


def downgrade() -> None:
    op.drop_table('post_likes')
