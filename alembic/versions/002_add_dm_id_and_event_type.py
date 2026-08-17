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
    # 1. Add event_type column to events table
    op.add_column(
        'events',
        sa.Column('event_type', sa.String(length=50), nullable=False, server_default='comment.created')
    )

    # 2. Make post_id, user_id, text nullable in events table
    op.alter_column('events', 'post_id', existing_type=sa.String(length=255), nullable=True)
    op.alter_column('events', 'user_id', existing_type=sa.String(length=255), nullable=True)
    op.alter_column('events', 'text', existing_type=sa.Text(), nullable=True)

    # 3. Add dm_id column to dm_jobs table and create index
    op.add_column(
        'dm_jobs',
        sa.Column('dm_id', sa.String(length=255), nullable=True)
    )
    op.create_index(op.f('ix_dm_jobs_dm_id'), 'dm_jobs', ['dm_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_dm_jobs_dm_id'), table_name='dm_jobs')
    op.drop_column('dm_jobs', 'dm_id')

    op.alter_column('events', 'text', existing_type=sa.Text(), nullable=False)
    op.alter_column('events', 'user_id', existing_type=sa.String(length=255), nullable=False)
    op.alter_column('events', 'post_id', existing_type=sa.String(length=255), nullable=False)
    op.drop_column('events', 'event_type')
