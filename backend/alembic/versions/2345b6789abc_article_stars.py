"""add knowledge article stars table"""

from alembic import op
import sqlalchemy as sa
from typing import Sequence, Union

revision: str = '2345b6789abc'
down_revision: Union[str, Sequence[str], None] = 'abcdef123456'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'knowledge_article_stars',
        sa.Column('article_id', sa.UUID(as_uuid=True), sa.ForeignKey('knowledge_articles.id'), primary_key=True),
        sa.Column('user_id', sa.UUID(as_uuid=True), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )


def downgrade() -> None:
    op.drop_table('knowledge_article_stars')
