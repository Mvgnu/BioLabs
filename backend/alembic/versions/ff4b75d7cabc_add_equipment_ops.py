"""add equipment ops

Revision ID: ff4b75d7cabc
Revises: d69c2eb94812
Create Date: 2025-07-14 12:00:00
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'ff4b75d7cabc'
down_revision = 'd69c2eb94812'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'equipment_maintenance',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('equipment_id', sa.UUID(), sa.ForeignKey('equipment.id', ondelete='CASCADE')),
        sa.Column('due_date', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('task_type', sa.String(), nullable=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_table(
        'sops',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('content', sa.String(), nullable=False),
        sa.Column('team_id', sa.UUID(), sa.ForeignKey('teams.id')),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_table(
        'training_records',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('user_id', sa.UUID(), sa.ForeignKey('users.id')),
        sa.Column('sop_id', sa.UUID(), sa.ForeignKey('sops.id')),
        sa.Column('equipment_id', sa.UUID(), sa.ForeignKey('equipment.id')),
        sa.Column('trained_by', sa.UUID(), sa.ForeignKey('users.id')),
        sa.Column('trained_at', sa.DateTime(), nullable=True),
    )

def downgrade():
    op.drop_table('training_records')
    op.drop_table('sops')
    op.drop_table('equipment_maintenance')
