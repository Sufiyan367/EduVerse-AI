"""Persist ungraded responses separately from assessment evidence."""
from alembic import op
import sqlalchemy as sa

revision = 'a01_grade_failures'
down_revision = '9b2c3d4e5f6a'
branch_labels = depends_on = None

def upgrade():
    op.create_table('grading_failures',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('quiz_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('quiz_item_id', sa.Integer(), sa.ForeignKey('quiz_items.id', ondelete='CASCADE'), nullable=False),
        sa.Column('response', sa.Text(), nullable=False),
        sa.Column('resolved', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint('session_id', 'quiz_item_id', name='uq_grading_failure'))
    op.add_column('concepts', sa.Column('learning_version', sa.Integer(), nullable=False, server_default='0'))

def downgrade():
    raise RuntimeError('Forward-only migration: preserve learning evidence.')
