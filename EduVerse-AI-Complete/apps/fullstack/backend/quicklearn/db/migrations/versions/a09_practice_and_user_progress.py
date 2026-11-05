"""add user_id to reviews and create practice_attempts table

Revision ID: a09_practice_progress
Revises: a08_guided_quiz_sessions
Create Date: 2026-11-03 16:50:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a09_practice_progress"
down_revision: str | None = "a08_guided_quiz_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add user_id to reviews
    with op.batch_alter_table("reviews", schema=None) as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_reviews_user_id_users",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index(batch_op.f("ix_reviews_user_id"), ["user_id"], unique=False)

    # 2. Create practice_attempts table
    op.create_table(
        "practice_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("challenge_id", sa.String(length=64), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("student_answer", sa.Text(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("is_passing", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("model_solution", sa.Text(), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_practice_attempts_challenge_id"), "practice_attempts", ["challenge_id"], unique=False)
    op.create_index(op.f("ix_practice_attempts_source_id"), "practice_attempts", ["source_id"], unique=False)
    op.create_index(op.f("ix_practice_attempts_user_id"), "practice_attempts", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_practice_attempts_user_id"), table_name="practice_attempts")
    op.drop_index(op.f("ix_practice_attempts_source_id"), table_name="practice_attempts")
    op.drop_index(op.f("ix_practice_attempts_challenge_id"), table_name="practice_attempts")
    op.drop_table("practice_attempts")

    with op.batch_alter_table("reviews", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_reviews_user_id"))
        batch_op.drop_constraint("fk_reviews_user_id_users", type_="foreignkey")
        batch_op.drop_column("user_id")
