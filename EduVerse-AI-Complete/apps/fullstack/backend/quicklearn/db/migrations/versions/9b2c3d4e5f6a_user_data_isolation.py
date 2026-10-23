"""add user_id to sources and notes for data isolation

Revision ID: 9b2c3d4e5f6a
Revises: 8a1b2c3d4e5f
Create Date: 2026-10-23 16:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '9b2c3d4e5f6a'
down_revision: str | None = '8a1b2c3d4e5f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('sources', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_sources_user_id_users',
            'users',
            ['user_id'],
            ['id'],
            ondelete='CASCADE',
        )
        batch_op.create_index(batch_op.f('ix_sources_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('notes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_notes_user_id_users',
            'users',
            ['user_id'],
            ['id'],
            ondelete='CASCADE',
        )
        batch_op.create_index(batch_op.f('ix_notes_user_id'), ['user_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('notes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_notes_user_id'))
        batch_op.drop_constraint('fk_notes_user_id_users', type_='foreignkey')
        batch_op.drop_column('user_id')

    with op.batch_alter_table('sources', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sources_user_id'))
        batch_op.drop_constraint('fk_sources_user_id_users', type_='foreignkey')
        batch_op.drop_column('user_id')
