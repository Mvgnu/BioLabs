"""add knowledge article views table"""

from alembic import op
import sqlalchemy as sa
from typing import Sequence, Union

revision: str = '1a2b3c4d5ef0'
down_revision: Union[str, Sequence[str], None] = '5e3d29cf5af1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'knowledge_article_views',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True),
        sa.Column('article_id', sa.UUID(as_uuid=True), sa.ForeignKey('knowledge_articles.id')),
        sa.Column('user_id', sa.UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('viewed_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )


def downgrade() -> None:
    op.drop_table('knowledge_article_views')
