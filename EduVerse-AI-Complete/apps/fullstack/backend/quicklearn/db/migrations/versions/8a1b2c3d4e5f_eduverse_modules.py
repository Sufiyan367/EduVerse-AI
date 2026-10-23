"""eduverse auth, revision planner, and activity log tables

Revision ID: 8a1b2c3d4e5f
Revises: 7f63fd3e6594
Create Date: 2026-10-23 14:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '8a1b2c3d4e5f'
down_revision: str | None = '7f63fd3e6594'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('avatar_color', sa.String(length=32), nullable=False, server_default='#7C3AED'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)
        batch_op.create_index(batch_op.f('ix_users_username'), ['username'], unique=True)

    # 2. Revision sessions table
    op.create_table(
        'revision_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('source_id', sa.Integer(), nullable=True),
        sa.Column('concept_id', sa.Integer(), nullable=True),
        sa.Column('topic', sa.String(length=255), nullable=False),
        sa.Column('priority', sa.String(length=32), nullable=False, server_default='MEDIUM'),
        sa.Column('recommended_duration_min', sa.Integer(), nullable=False, server_default='20'),
        sa.Column('reason', sa.Text(), nullable=False, server_default=''),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='PENDING'),
        sa.Column('scheduled_date', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('revision_sessions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_revision_sessions_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_revision_sessions_source_id'), ['source_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_revision_sessions_concept_id'), ['concept_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_revision_sessions_scheduled_date'), ['scheduled_date'], unique=False)

    # 3. Activity logs table
    op.create_table(
        'activity_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=64), nullable=False),
        sa.Column('entity_type', sa.String(length=32), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('activity_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_activity_logs_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_activity_logs_action'), ['action'], unique=False)
        batch_op.create_index(batch_op.f('ix_activity_logs_created_at'), ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_table('activity_logs')
    op.drop_table('revision_sessions')
    op.drop_table('users')
