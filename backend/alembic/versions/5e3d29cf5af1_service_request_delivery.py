"""add service request delivery

Revision ID: 5e3d29cf5af1
Revises: ff4b75d7cabc_add_equipment_ops
Create Date: 2025-07-26 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '5e3d29cf5af1'
down_revision = 'ff4b75d7cabc'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('service_requests', sa.Column('result_file_id', sa.UUID(as_uuid=True), nullable=True))
    op.add_column('service_requests', sa.Column('payment_status', sa.String(), nullable=True, server_default='pending'))


def downgrade() -> None:
    op.drop_column('service_requests', 'payment_status')
    op.drop_column('service_requests', 'result_file_id')
