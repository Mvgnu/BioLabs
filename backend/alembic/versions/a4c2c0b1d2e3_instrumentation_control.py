"""instrumentation control tables

Revision ID: a4c2c0b1d2e3
Revises: ff4b75d7cabc
Create Date: 2025-07-20 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a4c2c0b1d2e3'
down_revision = 'ff4b75d7cabc'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'instrument_capabilities',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('equipment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('equipment.id', ondelete='CASCADE'), nullable=False),
        sa.Column('capability_key', sa.String(length=120), nullable=False),
        sa.Column('title', sa.String(length=240), nullable=False),
        sa.Column('parameters', sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('guardrail_requirements', sa.JSON(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('equipment_id', 'capability_key', name='uq_instrument_capability'),
    )

    op.create_table(
        'instrument_sop_links',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('equipment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('equipment.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sop_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sops.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(length=40), nullable=False, server_default='active'),
        sa.Column('effective_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('retired_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('equipment_id', 'sop_id', name='uq_instrument_sop_link'),
    )

    op.create_table(
        'instrument_run_reservations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('equipment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('equipment.id', ondelete='CASCADE'), nullable=False),
        sa.Column('planner_session_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('protocol_execution_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('team_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('teams.id'), nullable=True),
        sa.Column('requested_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('scheduled_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('scheduled_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='scheduled'),
        sa.Column('run_parameters', sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('guardrail_snapshot', sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint('scheduled_end > scheduled_start', name='ck_reservation_window'),
    )
    op.create_index(
        'ix_instrument_run_reservations_equipment_time',
        'instrument_run_reservations',
        ['equipment_id', 'scheduled_start', 'scheduled_end'],
    )

    op.create_table(
        'instrument_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('reservation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('instrument_run_reservations.id', ondelete='SET NULL'), nullable=True),
        sa.Column('equipment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('equipment.id', ondelete='CASCADE'), nullable=False),
        sa.Column('team_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('teams.id'), nullable=True),
        sa.Column('planner_session_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('protocol_execution_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='queued'),
        sa.Column('run_parameters', sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('guardrail_flags', sa.JSON(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        'ix_instrument_runs_equipment_status',
        'instrument_runs',
        ['equipment_id', 'status'],
    )

    op.create_table(
        'instrument_telemetry_samples',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('run_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('instrument_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('channel', sa.String(length=120), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        'ix_instrument_telemetry_channel_time',
        'instrument_telemetry_samples',
        ['run_id', 'channel', 'recorded_at'],
    )

def downgrade():
    op.drop_index('ix_instrument_telemetry_channel_time', table_name='instrument_telemetry_samples')
    op.drop_table('instrument_telemetry_samples')
    op.drop_index('ix_instrument_runs_equipment_status', table_name='instrument_runs')
    op.drop_table('instrument_runs')
    op.drop_index('ix_instrument_run_reservations_equipment_time', table_name='instrument_run_reservations')
    op.drop_table('instrument_run_reservations')
    op.drop_table('instrument_sop_links')
    op.drop_table('instrument_capabilities')
