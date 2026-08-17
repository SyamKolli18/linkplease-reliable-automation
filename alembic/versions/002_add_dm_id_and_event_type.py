"""Add dm_id and event_type columns with optional event fields

Revision ID: 002_add_dm_id_and_event_type
Revises: 001_initial_tables
Create Date: 2026-08-17 21:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '002_add_dm_id_and_event_type'
down_revision: Union[str, None] = '001_initial_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. Add event_type column to events table if not existing
    event_cols = [c['name'] for c in inspector.get_columns('events')] if inspector.has_table('events') else []
    if 'event_type' not in event_cols:
        op.add_column(
            'events',
            sa.Column('event_type', sa.String(length=50), nullable=False, server_default='comment.created')
        )

    # 2. Make post_id, user_id, text nullable in events table
    with op.batch_alter_table('events') as batch_op:
        if 'post_id' in event_cols:
            batch_op.alter_column('post_id', existing_type=sa.String(length=255), nullable=True)
        if 'user_id' in event_cols:
            batch_op.alter_column('user_id', existing_type=sa.String(length=255), nullable=True)
        if 'text' in event_cols:
            batch_op.alter_column('text', existing_type=sa.Text(), nullable=True)

    # 3. Add dm_id column to dm_jobs table and create index if not existing
    dm_job_cols = [c['name'] for c in inspector.get_columns('dm_jobs')] if inspector.has_table('dm_jobs') else []
    if 'dm_id' not in dm_job_cols:
        op.add_column(
            'dm_jobs',
            sa.Column('dm_id', sa.String(length=255), nullable=True)
        )

    dm_job_indexes = [idx['name'] for idx in inspector.get_indexes('dm_jobs')] if inspector.has_table('dm_jobs') else []
    if 'ix_dm_jobs_dm_id' not in dm_job_indexes:
        op.create_index(op.f('ix_dm_jobs_dm_id'), 'dm_jobs', ['dm_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_dm_jobs_dm_id'), table_name='dm_jobs')
    op.drop_column('dm_jobs', 'dm_id')

    op.alter_column('events', 'text', existing_type=sa.Text(), nullable=False)
    op.alter_column('events', 'user_id', existing_type=sa.String(length=255), nullable=False)
    op.alter_column('events', 'post_id', existing_type=sa.String(length=255), nullable=False)
    op.drop_column('events', 'event_type')
