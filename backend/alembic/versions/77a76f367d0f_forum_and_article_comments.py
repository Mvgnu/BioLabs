"""add forum and article comments

Revision ID: 77a76f367d0f
Revises: 1a2b3c4d5ef0
Create Date: 2025-08-01
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '77a76f367d0f'
down_revision: Union[str, Sequence[str], None] = '1a2b3c4d5ef0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('knowledge_articles', sa.Column('is_public', sa.Boolean(), nullable=True, server_default='0'))
    op.add_column('comments', sa.Column('knowledge_article_id', sa.Uuid(as_uuid=True), nullable=True))
    op.create_table('forum_threads',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('created_by', sa.Uuid(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'))
    )
    op.create_table('forum_posts',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column('thread_id', sa.Uuid(as_uuid=True), sa.ForeignKey('forum_threads.id')),
        sa.Column('user_id', sa.Uuid(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('content', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'))
    )


def downgrade() -> None:
    op.drop_table('forum_posts')
    op.drop_table('forum_threads')
    op.drop_column('comments', 'knowledge_article_id')
    op.drop_column('knowledge_articles', 'is_public')
