"""Add atomic revision submission, statistics, and Decimal mastery.

Historical attempts cannot be truthfully backfilled because the old schema did
not retain a session-question reference, elapsed time, or mastery delta. The
upgrade therefore refuses ambiguous history instead of fabricating it.
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260826_0004"
down_revision: str | None = "20260826_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM user_attempts) THEN
                RAISE EXCEPTION
                    'upgrade refused: legacy attempts require reviewed reconciliation';
            END IF;
            IF EXISTS (
                SELECT 1 FROM revision_sessions WHERE status = 'COMPLETED'
            ) THEN
                RAISE EXCEPTION
                    'upgrade refused: completed sessions require reviewed reconciliation';
            END IF;
            IF EXISTS (
                SELECT 1
                FROM revision_sessions AS session
                WHERE session.status <> 'IN_PROGRESS'
                   OR session.ended_at IS NOT NULL
                   OR session.requested_question_count NOT BETWEEN 1 AND 50
                   OR session.requested_question_count <> (
                        SELECT COUNT(*)
                        FROM revision_session_questions AS selected
                        WHERE selected.session_id = session.id
                   )
            ) THEN
                RAISE EXCEPTION
                    'upgrade refused: revision session lifecycle or snapshot count is invalid';
            END IF;
            IF EXISTS (
                SELECT 1
                FROM revision_session_questions
                WHERE UPPER(BTRIM(correct_option_snapshot))
                      NOT IN ('0', '1', '2', '3', 'A', 'B', 'C', 'D')
            ) THEN
                RAISE EXCEPTION
                    'upgrade refused: a snapshot answer cannot be normalized';
            END IF;
            IF EXISTS (
                SELECT 1 FROM user_label_mastery
                WHERE (mastery_score IS NOT NULL AND mastery_score NOT BETWEEN 0 AND 100)
                   OR (total_attempts IS NOT NULL AND total_attempts < 0)
                   OR (correct_attempts IS NOT NULL AND correct_attempts < 0)
                   OR COALESCE(correct_attempts, 0) > COALESCE(total_attempts, 0)
            ) OR EXISTS (
                SELECT 1 FROM user_learning_item_mastery
                WHERE (mastery_score IS NOT NULL AND mastery_score NOT BETWEEN 0 AND 100)
                   OR (total_attempts IS NOT NULL AND total_attempts < 0)
                   OR (correct_attempts IS NOT NULL AND correct_attempts < 0)
                   OR COALESCE(correct_attempts, 0) > COALESCE(total_attempts, 0)
            ) THEN
                RAISE EXCEPTION
                    'upgrade refused: existing mastery values violate Phase 3 constraints';
            END IF;
        END $$
        """
    )

    op.create_check_constraint(
        "ck_revision_session_lifecycle",
        "revision_sessions",
        "(status = 'IN_PROGRESS' AND ended_at IS NULL) OR "
        "(status = 'COMPLETED' AND ended_at IS NOT NULL)",
    )
    op.create_unique_constraint(
        "uq_revision_session_question_id_session",
        "revision_session_questions",
        ["id", "session_id"],
    )

    op.add_column(
        "user_attempts",
        sa.Column("session_question_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "user_attempts",
        sa.Column("time_taken_seconds", sa.Integer(), nullable=True),
    )
    op.add_column(
        "user_attempts",
        sa.Column("mastery_delta", sa.Numeric(6, 2), nullable=True),
    )
    op.drop_constraint(
        "user_attempts_question_id_fkey",
        "user_attempts",
        type_="foreignkey",
    )
    op.alter_column("user_attempts", "question_id", nullable=True)
    op.create_foreign_key(
        "user_attempts_question_id_fkey",
        "user_attempts",
        "questions",
        ["question_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_user_attempt_session_question_membership",
        "user_attempts",
        "revision_session_questions",
        ["session_question_id", "session_id"],
        ["id", "session_id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_user_attempt_session_question",
        "user_attempts",
        ["session_question_id"],
    )
    op.create_check_constraint(
        "ck_user_attempt_time_taken",
        "user_attempts",
        "time_taken_seconds BETWEEN 0 AND 3600",
    )
    op.alter_column("user_attempts", "session_question_id", nullable=False)
    op.alter_column("user_attempts", "time_taken_seconds", nullable=False)
    op.alter_column("user_attempts", "mastery_delta", nullable=False)
    op.alter_column("user_attempts", "attempted_at", nullable=False)
    op.create_index(
        "ix_user_attempts_session_attempted",
        "user_attempts",
        ["session_id", "attempted_at"],
    )
    op.create_index(
        "ix_user_attempts_user_attempted",
        "user_attempts",
        ["user_id", "attempted_at"],
    )
    op.create_index(
        "ix_user_attempts_question_attempted",
        "user_attempts",
        ["question_id", "attempted_at"],
    )

    op.create_table(
        "question_statistics",
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column(
            "total_attempt_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "correct_attempt_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "total_time_seconds", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column(
            "average_time_seconds",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column("last_attempted_at", sa.TIMESTAMP(), nullable=False),
        sa.CheckConstraint(
            "total_attempt_count >= 0 AND correct_attempt_count >= 0 "
            "AND correct_attempt_count <= total_attempt_count",
            name="ck_question_statistics_counts",
        ),
        sa.CheckConstraint(
            "total_time_seconds >= 0",
            name="ck_question_statistics_total_time",
        ),
        sa.CheckConstraint(
            "average_time_seconds BETWEEN 0 AND 3600",
            name="ck_question_statistics_average_time",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"], ["questions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("question_id"),
    )
    op.create_index(
        "ix_question_statistics_last_attempted",
        "question_statistics",
        ["last_attempted_at"],
    )

    for table_name in ("user_label_mastery", "user_learning_item_mastery"):
        op.execute(
            sa.text(
                f"UPDATE {table_name} SET mastery_score = COALESCE(mastery_score, 50), "
                "total_attempts = COALESCE(total_attempts, 0), "
                "correct_attempts = COALESCE(correct_attempts, 0)"
            )
        )
        op.alter_column(
            table_name,
            "mastery_score",
            existing_type=sa.Integer(),
            type_=sa.Numeric(5, 2),
            postgresql_using="mastery_score::numeric(5,2)",
            nullable=False,
            server_default="50.00",
        )
        op.alter_column(
            table_name,
            "total_attempts",
            nullable=False,
            server_default="0",
        )
        op.alter_column(
            table_name,
            "correct_attempts",
            nullable=False,
            server_default="0",
        )

    op.create_check_constraint(
        "ck_user_label_mastery_score",
        "user_label_mastery",
        "mastery_score BETWEEN 0 AND 100",
    )
    op.create_check_constraint(
        "ck_user_label_mastery_counts",
        "user_label_mastery",
        "total_attempts >= 0 AND correct_attempts >= 0 "
        "AND correct_attempts <= total_attempts",
    )
    op.create_index(
        "ix_user_label_mastery_user_next_review",
        "user_label_mastery",
        ["user_id", "next_review_at"],
    )
    op.create_check_constraint(
        "ck_user_learning_item_mastery_score",
        "user_learning_item_mastery",
        "mastery_score BETWEEN 0 AND 100",
    )
    op.create_check_constraint(
        "ck_user_learning_item_mastery_counts",
        "user_learning_item_mastery",
        "total_attempts >= 0 AND correct_attempts >= 0 "
        "AND correct_attempts <= total_attempts",
    )
    op.create_index(
        "ix_user_learning_item_mastery_user_next_review",
        "user_learning_item_mastery",
        ["user_id", "next_review_at"],
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM user_attempts)
               OR EXISTS (SELECT 1 FROM question_statistics)
               OR EXISTS (
                    SELECT 1 FROM revision_sessions WHERE status = 'COMPLETED'
                ) THEN
                RAISE EXCEPTION
                    'downgrade refused: Phase 3 completion, attempt, or statistics history exists';
            END IF;
            IF EXISTS (
                SELECT 1 FROM user_label_mastery
                WHERE mastery_score <> TRUNC(mastery_score)
            ) OR EXISTS (
                SELECT 1 FROM user_learning_item_mastery
                WHERE mastery_score <> TRUNC(mastery_score)
            ) THEN
                RAISE EXCEPTION
                    'downgrade refused: Decimal mastery cannot be restored losslessly';
            END IF;
        END $$
        """
    )

    op.drop_index(
        "ix_user_learning_item_mastery_user_next_review",
        table_name="user_learning_item_mastery",
    )
    op.drop_constraint(
        "ck_user_learning_item_mastery_counts",
        "user_learning_item_mastery",
        type_="check",
    )
    op.drop_constraint(
        "ck_user_learning_item_mastery_score",
        "user_learning_item_mastery",
        type_="check",
    )
    op.drop_index(
        "ix_user_label_mastery_user_next_review",
        table_name="user_label_mastery",
    )
    op.drop_constraint(
        "ck_user_label_mastery_counts",
        "user_label_mastery",
        type_="check",
    )
    op.drop_constraint(
        "ck_user_label_mastery_score",
        "user_label_mastery",
        type_="check",
    )
    for table_name in ("user_learning_item_mastery", "user_label_mastery"):
        op.alter_column(
            table_name,
            "correct_attempts",
            nullable=True,
            server_default=None,
        )
        op.alter_column(
            table_name,
            "total_attempts",
            nullable=True,
            server_default=None,
        )
        op.alter_column(
            table_name,
            "mastery_score",
            existing_type=sa.Numeric(5, 2),
            type_=sa.Integer(),
            postgresql_using="mastery_score::integer",
            nullable=True,
            server_default=None,
        )

    op.drop_index(
        "ix_question_statistics_last_attempted",
        table_name="question_statistics",
    )
    op.drop_table("question_statistics")

    op.drop_index(
        "ix_user_attempts_question_attempted", table_name="user_attempts"
    )
    op.drop_index("ix_user_attempts_user_attempted", table_name="user_attempts")
    op.drop_index(
        "ix_user_attempts_session_attempted", table_name="user_attempts"
    )
    op.drop_constraint(
        "ck_user_attempt_time_taken", "user_attempts", type_="check"
    )
    op.drop_constraint(
        "uq_user_attempt_session_question", "user_attempts", type_="unique"
    )
    op.drop_constraint(
        "fk_user_attempt_session_question_membership",
        "user_attempts",
        type_="foreignkey",
    )
    op.drop_constraint(
        "user_attempts_question_id_fkey", "user_attempts", type_="foreignkey"
    )
    op.alter_column("user_attempts", "question_id", nullable=False)
    op.create_foreign_key(
        "user_attempts_question_id_fkey",
        "user_attempts",
        "questions",
        ["question_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.alter_column("user_attempts", "attempted_at", nullable=True)
    op.drop_column("user_attempts", "mastery_delta")
    op.drop_column("user_attempts", "time_taken_seconds")
    op.drop_column("user_attempts", "session_question_id")

    op.drop_constraint(
        "uq_revision_session_question_id_session",
        "revision_session_questions",
        type_="unique",
    )
    op.drop_constraint(
        "ck_revision_session_lifecycle",
        "revision_sessions",
        type_="check",
    )
