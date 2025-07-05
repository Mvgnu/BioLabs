"""add is_admin and project member role

Revision ID: 74cfc64cc205
Revises: fee2a4743cf3
Create Date: 2025-07-03 18:10:42.610284
"""
from alembic import op
import sqlalchemy as sa

revision = '74cfc64cc205'
down_revision = 'fee2a4743cf3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('is_admin', sa.Boolean(), server_default='0', nullable=False))
    op.add_column('project_members', sa.Column('role', sa.String(), server_default='member', nullable=False))


def downgrade():
    op.drop_column('project_members', 'role')
    op.drop_column('users', 'is_admin')
