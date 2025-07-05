"""add service marketplace tables"""
from alembic import op
import sqlalchemy as sa
import uuid
from sqlalchemy.dialects import postgresql

revision = 'c1a2b3c4d5e6'
down_revision = 'b3efabc12345'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'service_listings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('provider_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String()),
        sa.Column('price', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='open'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )
    op.create_table(
        'service_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('uuid_generate_v4()')),
        sa.Column('listing_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('service_listings.id')),
        sa.Column('requester_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('inventory_items.id'), nullable=True),
        sa.Column('message', sa.String()),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )

def downgrade():
    op.drop_table('service_requests')
    op.drop_table('service_listings')
