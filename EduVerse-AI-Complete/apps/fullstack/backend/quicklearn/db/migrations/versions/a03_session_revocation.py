"""Add token_version to users and create revoked_tokens table for server-side logout."""
from alembic import op
import sqlalchemy as sa

revision = 'a03_session_revocation'
down_revision = 'a02_resource_ownership'
branch_labels = depends_on = None

def upgrade():
    # Add token_version to users table
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('token_version', sa.Integer(), nullable=False, server_default='1'))

    # Create revoked_tokens table
    op.create_table(
        'revoked_tokens',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('jti', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_revoked_tokens_jti', 'revoked_tokens', ['jti'], unique=True)
    op.create_index('ix_revoked_tokens_user_id', 'revoked_tokens', ['user_id'], unique=False)
    op.create_index('ix_revoked_tokens_expires_at', 'revoked_tokens', ['expires_at'], unique=False)

def downgrade():
    op.drop_table('revoked_tokens')
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('token_version')
