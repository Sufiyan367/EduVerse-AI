"""Create academic intelligence domain tables for University Exam & Adaptive Learning.

Revision ID: a05_academic_intelligence
Revises: a04_password_reset
"""

from alembic import op
import sqlalchemy as sa

revision = 'a05_academic_intelligence'
down_revision = 'a04_password_reset'
branch_labels = depends_on = None

def upgrade():
    # 1. Course Workspace
    op.create_table(
        'courses',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('semester', sa.String(length=32), nullable=False, server_default='Semester 3'),
        sa.Column('academic_year', sa.String(length=32), nullable=False, server_default='2025-2026'),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('target_exam_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_courses_user_id', 'courses', ['user_id'], unique=False)
    op.create_index('ix_courses_code', 'courses', ['code'], unique=False)

    op.create_table(
        'course_units',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('course_id', sa.Integer(), sa.ForeignKey('courses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('unit_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('weightage_percent', sa.Float(), nullable=False, server_default='16.6'),
    )
    op.create_index('ix_course_units_course_id', 'course_units', ['course_id'], unique=False)

    op.create_table(
        'course_outcomes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('course_id', sa.Integer(), sa.ForeignKey('courses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('co_code', sa.String(length=32), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('target_level', sa.String(length=32), nullable=False, server_default='Apply'),
    )
    op.create_index('ix_course_outcomes_course_id', 'course_outcomes', ['course_id'], unique=False)

    op.create_table(
        'syllabus_topics',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('course_id', sa.Integer(), sa.ForeignKey('courses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('unit_id', sa.Integer(), sa.ForeignKey('course_units.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('bloom_level', sa.String(length=32), nullable=False, server_default='Understand'),
        sa.Column('importance_score', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_syllabus_topics_course_id', 'syllabus_topics', ['course_id'], unique=False)
    op.create_index('ix_syllabus_topics_unit_id', 'syllabus_topics', ['unit_id'], unique=False)

    op.create_table(
        'topic_outcome_links',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('topic_id', sa.Integer(), sa.ForeignKey('syllabus_topics.id', ondelete='CASCADE'), nullable=False),
        sa.Column('outcome_id', sa.Integer(), sa.ForeignKey('course_outcomes.id', ondelete='CASCADE'), nullable=False),
    )
    op.create_index('ix_topic_outcome_links_topic_id', 'topic_outcome_links', ['topic_id'], unique=False)
    op.create_index('ix_topic_outcome_links_outcome_id', 'topic_outcome_links', ['outcome_id'], unique=False)

    op.create_table(
        'course_material_links',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('course_id', sa.Integer(), sa.ForeignKey('courses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_id', sa.Integer(), sa.ForeignKey('sources.id', ondelete='CASCADE'), nullable=False),
        sa.Column('unit_id', sa.Integer(), sa.ForeignKey('course_units.id', ondelete='SET NULL'), nullable=True),
    )
    op.create_index('ix_course_material_links_course_id', 'course_material_links', ['course_id'], unique=False)
    op.create_index('ix_course_material_links_source_id', 'course_material_links', ['source_id'], unique=False)

    # 2. Previous Paper Intelligence
    op.create_table(
        'previous_papers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('course_id', sa.Integer(), sa.ForeignKey('courses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('exam_term', sa.String(length=64), nullable=False, server_default='End-Sem'),
        sa.Column('exam_year', sa.Integer(), nullable=False, server_default='2024'),
        sa.Column('total_marks', sa.Float(), nullable=False, server_default='70.0'),
        sa.Column('duration_minutes', sa.Integer(), nullable=False, server_default='150'),
        sa.Column('source_id', sa.Integer(), sa.ForeignKey('sources.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_previous_papers_course_id', 'previous_papers', ['course_id'], unique=False)
    op.create_index('ix_previous_papers_user_id', 'previous_papers', ['user_id'], unique=False)

    op.create_table(
        'exam_questions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('paper_id', sa.Integer(), sa.ForeignKey('previous_papers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('question_number', sa.String(length=32), nullable=False, server_default='Q1'),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('marks', sa.Float(), nullable=False, server_default='5.0'),
        sa.Column('bloom_level', sa.String(length=32), nullable=False, server_default='Understand'),
        sa.Column('frequency_count', sa.Integer(), nullable=False, server_default='1'),
    )
    op.create_index('ix_exam_questions_paper_id', 'exam_questions', ['paper_id'], unique=False)

    op.create_table(
        'question_topic_links',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('question_id', sa.Integer(), sa.ForeignKey('exam_questions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('topic_id', sa.Integer(), sa.ForeignKey('syllabus_topics.id', ondelete='CASCADE'), nullable=False),
        sa.Column('relevance_score', sa.Float(), nullable=False, server_default='1.0'),
    )
    op.create_index('ix_question_topic_links_question_id', 'question_topic_links', ['question_id'], unique=False)
    op.create_index('ix_question_topic_links_topic_id', 'question_topic_links', ['topic_id'], unique=False)

    op.create_table(
        'exam_patterns',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('course_id', sa.Integer(), sa.ForeignKey('courses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('pattern_type', sa.String(length=64), nullable=False),
        sa.Column('structure', sa.JSON(), nullable=False),
    )
    op.create_index('ix_exam_patterns_course_id', 'exam_patterns', ['course_id'], unique=False)

    op.create_table(
        'exam_blueprints',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('course_id', sa.Integer(), sa.ForeignKey('courses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('unit_distribution', sa.JSON(), nullable=False),
        sa.Column('bloom_distribution', sa.JSON(), nullable=False),
    )
    op.create_index('ix_exam_blueprints_course_id', 'exam_blueprints', ['course_id'], unique=False)

    # 3. Assessment & Exam Simulator
    op.create_table(
        'rubrics',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('course_id', sa.Integer(), sa.ForeignKey('courses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_rubrics_course_id', 'rubrics', ['course_id'], unique=False)

    op.create_table(
        'rubric_criteria',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('rubric_id', sa.Integer(), sa.ForeignKey('rubrics.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('max_points', sa.Float(), nullable=False, server_default='5.0'),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
    )
    op.create_index('ix_rubric_criteria_rubric_id', 'rubric_criteria', ['rubric_id'], unique=False)

    op.create_table(
        'exam_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('course_id', sa.Integer(), sa.ForeignKey('courses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='in_progress'),
        sa.Column('total_score', sa.Float(), nullable=True),
        sa.Column('max_score', sa.Float(), nullable=False, server_default='50.0'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_exam_sessions_course_id', 'exam_sessions', ['course_id'], unique=False)
    op.create_index('ix_exam_sessions_user_id', 'exam_sessions', ['user_id'], unique=False)

    op.create_table(
        'assessment_questions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('exam_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('topic_id', sa.Integer(), sa.ForeignKey('syllabus_topics.id', ondelete='SET NULL'), nullable=True),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('ideal_answer', sa.Text(), nullable=True),
        sa.Column('marks', sa.Float(), nullable=False, server_default='10.0'),
        sa.Column('question_order', sa.Integer(), nullable=False, server_default='1'),
    )
    op.create_index('ix_assessment_questions_session_id', 'assessment_questions', ['session_id'], unique=False)

    op.create_table(
        'answer_attempts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('exam_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('question_id', sa.Integer(), sa.ForeignKey('assessment_questions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_answer', sa.Text(), nullable=False),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_answer_attempts_session_id', 'answer_attempts', ['session_id'], unique=False)
    op.create_index('ix_answer_attempts_question_id', 'answer_attempts', ['question_id'], unique=False)
    op.create_index('ix_answer_attempts_user_id', 'answer_attempts', ['user_id'], unique=False)

    op.create_table(
        'grading_feedback',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('attempt_id', sa.Integer(), sa.ForeignKey('answer_attempts.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('score_awarded', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('evaluator_model', sa.String(length=64), nullable=False, server_default='qwen3.5:4b'),
        sa.Column('criterion_scores', sa.JSON(), nullable=False),
        sa.Column('strengths', sa.Text(), nullable=False, server_default=''),
        sa.Column('weaknesses', sa.Text(), nullable=False, server_default=''),
        sa.Column('suggestions', sa.Text(), nullable=False, server_default=''),
        sa.Column('graded_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_grading_feedback_attempt_id', 'grading_feedback', ['attempt_id'], unique=True)

    # 4. Adaptive Learning
    op.create_table(
        'student_topic_mastery',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('topic_id', sa.Integer(), sa.ForeignKey('syllabus_topics.id', ondelete='CASCADE'), nullable=False),
        sa.Column('mastery_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('confidence_level', sa.String(length=32), nullable=False, server_default='low'),
        sa.Column('last_evaluated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('user_id', 'topic_id', name='uq_user_topic_mastery'),
    )
    op.create_index('ix_student_topic_mastery_user_id', 'student_topic_mastery', ['user_id'], unique=False)
    op.create_index('ix_student_topic_mastery_topic_id', 'student_topic_mastery', ['topic_id'], unique=False)

    op.create_table(
        'topic_mastery_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('topic_id', sa.Integer(), sa.ForeignKey('syllabus_topics.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.String(length=32), nullable=False, server_default='quiz'),
        sa.Column('score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_topic_mastery_events_user_id', 'topic_mastery_events', ['user_id'], unique=False)
    op.create_index('ix_topic_mastery_events_topic_id', 'topic_mastery_events', ['topic_id'], unique=False)

    op.create_table(
        'revision_plans',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('course_id', sa.Integer(), sa.ForeignKey('courses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('target_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_revision_plans_user_id', 'revision_plans', ['user_id'], unique=False)
    op.create_index('ix_revision_plans_course_id', 'revision_plans', ['course_id'], unique=False)

    op.create_table(
        'revision_tasks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('plan_id', sa.Integer(), sa.ForeignKey('revision_plans.id', ondelete='CASCADE'), nullable=False),
        sa.Column('topic_id', sa.Integer(), sa.ForeignKey('syllabus_topics.id', ondelete='SET NULL'), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('estimated_minutes', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('is_completed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_revision_tasks_plan_id', 'revision_tasks', ['plan_id'], unique=False)

    op.create_table(
        'remediation_attempts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('revision_tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('action_type', sa.String(length=64), nullable=False, server_default='practice_quiz'),
        sa.Column('performance_delta', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_remediation_attempts_task_id', 'remediation_attempts', ['task_id'], unique=False)
    op.create_index('ix_remediation_attempts_user_id', 'remediation_attempts', ['user_id'], unique=False)

def downgrade():
    tables = [
        'remediation_attempts', 'revision_tasks', 'revision_plans',
        'topic_mastery_events', 'student_topic_mastery',
        'grading_feedback', 'answer_attempts', 'assessment_questions', 'exam_sessions',
        'rubric_criteria', 'rubrics', 'exam_blueprints', 'exam_patterns',
        'question_topic_links', 'exam_questions', 'previous_papers',
        'course_material_links', 'topic_outcome_links', 'syllabus_topics',
        'course_outcomes', 'course_units', 'courses'
    ]
    for tbl in tables:
        op.drop_table(tbl)
