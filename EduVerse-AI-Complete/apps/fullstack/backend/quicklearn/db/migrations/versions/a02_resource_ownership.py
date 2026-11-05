"""Ownership for previously global resources; legacy rows remain quarantined."""
from alembic import op
import sqlalchemy as sa
revision = 'a02_resource_ownership'
down_revision = 'a01_grade_failures'
branch_labels = depends_on = None

def upgrade():
    for table in ('folders', 'tags', 'chats', 'quiz_sessions', 'podcasts'):
        op.add_column(table, sa.Column('user_id', sa.Integer(), nullable=True))
        op.create_index('ix_' + table + '_user_id', table, ['user_id'])

def downgrade():
    raise RuntimeError('Forward-only migration: preserve ownership data.')
