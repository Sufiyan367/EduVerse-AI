"""Add evidence and page_no columns to quiz_items for server-side grounding verification.

Revision ID: a07_quiz_evidence
Revises: a06_automation_engine
"""

from alembic import op
import sqlalchemy as sa

revision = 'a07_quiz_evidence'
down_revision = 'a06_automation_engine'
branch_labels = depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'sqlite':
        with op.batch_alter_table('quiz_items') as batch_op:
            batch_op.add_column(sa.Column('evidence', sa.Text(), nullable=True))
            batch_op.add_column(sa.Column('page_no', sa.Integer(), nullable=True))
    else:
        op.add_column('quiz_items', sa.Column('evidence', sa.Text(), nullable=True))
        op.add_column('quiz_items', sa.Column('page_no', sa.Integer(), nullable=True))


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'sqlite':
        with op.batch_alter_table('quiz_items') as batch_op:
            batch_op.drop_column('page_no')
            batch_op.drop_column('evidence')
    else:
        op.drop_column('quiz_items', 'page_no')
        op.drop_column('quiz_items', 'evidence')
