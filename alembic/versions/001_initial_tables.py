"""Initial tables migration

Revision ID: 001_initial_tables
Revises: 
Create Date: 2026-08-16 19:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '001_initial_tables'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Rules
    op.create_table(
        'rules',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('keyword', sa.String(length=255), nullable=False),
        sa.Column('dm_message', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_rules_keyword'), 'rules', ['keyword'], unique=False)

    # 2. Events
    op.create_table(
        'events',
        sa.Column('id', sa.String(length=255), nullable=False),
        sa.Column('post_id', sa.String(length=255), nullable=False),
        sa.Column('comment_id', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_events_user_id'), 'events', ['user_id'], unique=False)

    # 3. DM Jobs
    op.create_table(
        'dm_jobs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('event_id', sa.String(length=255), nullable=False),
        sa.Column('rule_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('comment_id', sa.String(length=255), nullable=False),
        sa.Column('dm_message', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('max_retries', sa.Integer(), nullable=False),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['rule_id'], ['rules.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dm_jobs_status'), 'dm_jobs', ['status'], unique=False)
    op.create_index(op.f('ix_dm_jobs_user_id'), 'dm_jobs', ['user_id'], unique=False)
    op.create_index('idx_dm_jobs_status_retry', 'dm_jobs', ['status', 'next_retry_at'], unique=False)

    # 4. User Rule Deliveries
    op.create_table(
        'user_rule_deliveries',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('rule_id', sa.String(length=36), nullable=False),
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['dm_jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['rule_id'], ['rules.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'rule_id', name='uq_user_rule')
    )


def downgrade() -> None:
    op.drop_table('user_rule_deliveries')
    op.drop_table('dm_jobs')
    op.drop_table('events')
    op.drop_table('rules')
