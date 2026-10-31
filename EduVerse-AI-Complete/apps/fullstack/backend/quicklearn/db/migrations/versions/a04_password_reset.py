"""Create password_reset_tokens table for secure forgot-password workflow."""
from alembic import op
import sqlalchemy as sa

revision = 'a04_password_reset'
down_revision = 'a03_session_revocation'
branch_labels = depends_on = None

def upgrade():
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_password_reset_tokens_token_hash', 'password_reset_tokens', ['token_hash'], unique=True)
    op.create_index('ix_password_reset_tokens_user_id', 'password_reset_tokens', ['user_id'], unique=False)
    op.create_index('ix_password_reset_tokens_expires_at', 'password_reset_tokens', ['expires_at'], unique=False)

def downgrade():
    op.drop_table('password_reset_tokens')
