"""Add append-only mastery history.

Revision ID: 20260914_0007
Revises: 20260829_0006
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260914_0007"
down_revision: str | None = "20260829_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mastery_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=20), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("score_before", sa.Numeric(5, 2), nullable=False),
        sa.Column("score_after", sa.Numeric(5, 2), nullable=False),
        sa.Column("total_attempts", sa.Integer(), nullable=False),
        sa.Column("correct_attempts", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "entity_type IN ('LABEL', 'LEARNING_ITEM')",
            name="ck_mastery_history_entity_type",
        ),
        sa.CheckConstraint(
            "score_before BETWEEN 0 AND 100 AND score_after BETWEEN 0 AND 100",
            name="ck_mastery_history_scores",
        ),
        sa.CheckConstraint(
            "total_attempts >= 0 AND correct_attempts >= 0 "
            "AND correct_attempts <= total_attempts",
            name="ck_mastery_history_counts",
        ),
        sa.ForeignKeyConstraint(["session_id"], ["revision_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "session_id", "entity_type", "entity_id",
            name="uq_mastery_history_session_entity",
        ),
    )
    op.create_index("ix_mastery_history_id", "mastery_history", ["id"])
    op.create_index(
        "ix_mastery_history_user_entity_time",
        "mastery_history",
        ["user_id", "entity_type", "entity_id", "recorded_at"],
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM mastery_history) THEN
                RAISE EXCEPTION
                    'downgrade refused: recorded mastery history would be lost';
            END IF;
        END $$;
        """
    )
    op.drop_index("ix_mastery_history_user_entity_time", table_name="mastery_history")
    op.drop_index("ix_mastery_history_id", table_name="mastery_history")
    op.drop_table("mastery_history")
