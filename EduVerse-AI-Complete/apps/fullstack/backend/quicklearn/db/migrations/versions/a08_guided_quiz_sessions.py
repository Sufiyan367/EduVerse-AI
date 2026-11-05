"""Create guided_quiz_sessions table for opaque, server-side anti-tamper quiz integrity.

Revision ID: a08_guided_quiz_sessions
Revises: a07_quiz_evidence
"""

from alembic import op
import sqlalchemy as sa

revision = 'a08_guided_quiz_sessions'
down_revision = 'a07_quiz_evidence'
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        'guided_quiz_sessions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('session_token', sa.String(length=128), nullable=False),
        sa.Column('quiz_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('course_id', sa.Integer(), sa.ForeignKey('courses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('topic_id', sa.Integer(), sa.ForeignKey('syllabus_topics.id', ondelete='CASCADE'), nullable=False),
        sa.Column('question_ids', sa.JSON(), nullable=False),
        sa.Column('answer_key', sa.JSON(), nullable=False),
        sa.Column('explanations', sa.JSON(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_guided_quiz_sessions_session_token', 'guided_quiz_sessions', ['session_token'], unique=True)
    op.create_index('ix_guided_quiz_sessions_user_id', 'guided_quiz_sessions', ['user_id'])
    op.create_index('ix_guided_quiz_sessions_topic_id', 'guided_quiz_sessions', ['topic_id'])


def downgrade():
    op.drop_index('ix_guided_quiz_sessions_topic_id', table_name='guided_quiz_sessions')
    op.drop_index('ix_guided_quiz_sessions_user_id', table_name='guided_quiz_sessions')
    op.drop_index('ix_guided_quiz_sessions_session_token', table_name='guided_quiz_sessions')
    op.drop_table('guided_quiz_sessions')
