"""Create automation engine tables and job queue columns for Autonomous Workflows.

Revision ID: a06_automation_engine
Revises: a05_academic_intelligence
"""

from alembic import op
import sqlalchemy as sa

revision = 'a06_automation_engine'
down_revision = 'a05_academic_intelligence'
branch_labels = depends_on = None

def upgrade():
    # 1. Enhance jobs table
    bind = op.get_bind()
    if bind.dialect.name == 'sqlite':
        with op.batch_alter_table('jobs') as batch_op:
            batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
            batch_op.add_column(sa.Column('priority', sa.Integer(), nullable=False, server_default='50'))
            batch_op.add_column(sa.Column('idempotency_key', sa.String(length=128), nullable=True))
            batch_op.add_column(sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True))
            batch_op.add_column(sa.Column('locked_by', sa.String(length=64), nullable=True))
            batch_op.add_column(sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True))
            batch_op.add_column(sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='3'))
            batch_op.add_column(sa.Column('error_details', sa.JSON(), nullable=False, server_default='{}'))
            batch_op.create_index('ix_jobs_user_id', ['user_id'], unique=False)
            batch_op.create_index('ix_jobs_priority', ['priority'], unique=False)
            batch_op.create_index('ix_jobs_idempotency_key', ['idempotency_key'], unique=False)
            batch_op.create_index('ix_jobs_claim_v2', ['status', 'priority', 'next_run_at'], unique=False)
    else:
        op.add_column('jobs', sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True))
        op.add_column('jobs', sa.Column('priority', sa.Integer(), nullable=False, server_default='50'))
        op.add_column('jobs', sa.Column('idempotency_key', sa.String(length=128), nullable=True))
        op.add_column('jobs', sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True))
        op.add_column('jobs', sa.Column('locked_by', sa.String(length=64), nullable=True))
        op.add_column('jobs', sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True))
        op.add_column('jobs', sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='3'))
        op.add_column('jobs', sa.Column('error_details', sa.JSON(), nullable=False, server_default='{}'))

        op.create_index('ix_jobs_user_id', 'jobs', ['user_id'], unique=False)
        op.create_index('ix_jobs_priority', 'jobs', ['priority'], unique=False)
        op.create_index('ix_jobs_idempotency_key', 'jobs', ['idempotency_key'], unique=False)
        op.create_index('ix_jobs_claim_v2', 'jobs', ['status', 'priority', 'next_run_at'], unique=False)

    # 2. Automation Rules
    op.create_table(
        'automation_rules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True),
        sa.Column('rule_name', sa.String(length=64), nullable=False),
        sa.Column('trigger_event', sa.String(length=64), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('config', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_automation_rules_user_id', 'automation_rules', ['user_id'], unique=False)
    op.create_index('ix_automation_rules_rule_name', 'automation_rules', ['rule_name'], unique=False)
    op.create_index('ix_automation_rules_trigger_event', 'automation_rules', ['trigger_event'], unique=False)

    # 3. Weekly Reports
    op.create_table(
        'weekly_reports',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('course_id', sa.Integer(), sa.ForeignKey('courses.id', ondelete='CASCADE'), nullable=True),
        sa.Column('week_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('week_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('metrics', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('strong_topics', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('weak_topics', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('repeated_mistakes', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('revision_completion_rate', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('summary_text', sa.Text(), nullable=False, server_default=''),
        sa.Column('recommendations', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_weekly_reports_user_id', 'weekly_reports', ['user_id'], unique=False)
    op.create_index('ix_weekly_reports_course_id', 'weekly_reports', ['course_id'], unique=False)

    # 4. Notifications
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('kind', sa.String(length=64), nullable=False, server_default='info'),
        sa.Column('link', sa.String(length=255), nullable=True),
        sa.Column('data', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_notifications_user_id', 'notifications', ['user_id'], unique=False)
    op.create_index('ix_notifications_is_read', 'notifications', ['is_read'], unique=False)
    op.create_index('ix_notifications_created_at', 'notifications', ['created_at'], unique=False)

    # 5. Evidence Audit Issues
    op.create_table(
        'evidence_audit_issues',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True),
        sa.Column('course_id', sa.Integer(), sa.ForeignKey('courses.id', ondelete='CASCADE'), nullable=True),
        sa.Column('issue_type', sa.String(length=64), nullable=False),
        sa.Column('severity', sa.String(length=32), nullable=False, server_default='warning'),
        sa.Column('entity_type', sa.String(length=64), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('evidence_context', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='open'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_evidence_audit_issues_user_id', 'evidence_audit_issues', ['user_id'], unique=False)
    op.create_index('ix_evidence_audit_issues_course_id', 'evidence_audit_issues', ['course_id'], unique=False)
    op.create_index('ix_evidence_audit_issues_issue_type', 'evidence_audit_issues', ['issue_type'], unique=False)
    op.create_index('ix_evidence_audit_issues_status', 'evidence_audit_issues', ['status'], unique=False)


def downgrade():
    op.drop_table('evidence_audit_issues')
    op.drop_table('notifications')
    op.drop_table('weekly_reports')
    op.drop_table('automation_rules')
    op.drop_index('ix_jobs_claim_v2', 'jobs')
    op.drop_index('ix_jobs_idempotency_key', 'jobs')
    op.drop_index('ix_jobs_priority', 'jobs')
    op.drop_index('ix_jobs_user_id', 'jobs')
    op.drop_column('jobs', 'error_details')
    op.drop_column('jobs', 'max_attempts')
    op.drop_column('jobs', 'next_run_at')
    op.drop_column('jobs', 'locked_by')
    op.drop_column('jobs', 'locked_until')
    op.drop_column('jobs', 'idempotency_key')
    op.drop_column('jobs', 'priority')
    op.drop_column('jobs', 'user_id')
