"""Add persisted revision-session selection and immutable snapshots.

The legacy revision_sessions.quiz_type column is intentionally retained. Its
removal requires a separately reviewed cleanup migration after real data and
rollback requirements have been inspected.
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260825_0002"
down_revision: str | None = "20260824_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "revision_sessions",
        sa.Column("requested_strategy", sa.String(20), nullable=True),
    )
    op.add_column(
        "revision_sessions",
        sa.Column("strategy_used", sa.String(20), nullable=True),
    )
    op.add_column(
        "revision_sessions",
        sa.Column("status", sa.String(20), nullable=True),
    )
    op.add_column(
        "revision_sessions",
        sa.Column("requested_question_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "revision_sessions",
        sa.Column("questions_per_label", sa.Integer(), nullable=True),
    )
    op.add_column(
        "revision_sessions",
        sa.Column(
            "generated_question_count",
            sa.Integer(),
            nullable=True,
            server_default="0",
        ),
    )
    op.add_column(
        "revision_sessions",
        sa.Column(
            "allow_ai_generation",
            sa.Boolean(),
            nullable=True,
            server_default=sa.false(),
        ),
    )

    op.execute(
        """
        UPDATE revision_sessions AS session
        SET requested_strategy = UPPER(session.quiz_type),
            strategy_used = UPPER(session.quiz_type),
            status = CASE
                WHEN session.ended_at IS NULL THEN 'IN_PROGRESS'
                ELSE 'COMPLETED'
            END,
            requested_question_count = (
                SELECT COUNT(*)
                FROM revision_session_questions AS selected
                WHERE selected.session_id = session.id
            ),
            generated_question_count = 0,
            allow_ai_generation = FALSE
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM revision_sessions
                WHERE requested_strategy NOT IN ('RANDOM', 'LABEL')
                   OR requested_question_count NOT BETWEEN 1 AND 50
            ) THEN
                RAISE EXCEPTION
                    'revision session backfill requires manual reconciliation';
            END IF;
        END $$
        """
    )

    for column_name in (
        "requested_strategy",
        "strategy_used",
        "status",
        "requested_question_count",
        "generated_question_count",
        "allow_ai_generation",
    ):
        op.alter_column("revision_sessions", column_name, nullable=False)

    op.create_check_constraint(
        "ck_revision_session_requested_strategy",
        "revision_sessions",
        "requested_strategy IN ('RANDOM', 'LABEL')",
    )
    op.create_check_constraint(
        "ck_revision_session_strategy_used",
        "revision_sessions",
        "strategy_used IN ('RANDOM', 'LABEL')",
    )
    op.create_check_constraint(
        "ck_revision_session_status",
        "revision_sessions",
        "status IN ('IN_PROGRESS', 'COMPLETED')",
    )
    op.create_check_constraint(
        "ck_revision_session_question_count",
        "revision_sessions",
        "requested_question_count BETWEEN 1 AND 50",
    )
    op.create_check_constraint(
        "ck_revision_session_questions_per_label",
        "revision_sessions",
        "questions_per_label IS NULL OR questions_per_label BETWEEN 1 AND 20",
    )
    op.create_check_constraint(
        "ck_revision_session_generated_count",
        "revision_sessions",
        "generated_question_count BETWEEN 0 AND requested_question_count",
    )
    op.create_index(
        "ix_revision_sessions_user_status_started",
        "revision_sessions",
        ["user_id", "status", "started_at"],
    )

    op.create_table(
        "revision_session_labels",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("label_id", sa.Integer(), nullable=True),
        sa.Column("label_name_snapshot", sa.String(200), nullable=False),
        sa.Column("label_order", sa.Integer(), nullable=False),
        sa.Column("question_quota", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "label_order >= 1",
            name="ck_revision_session_label_order",
        ),
        sa.CheckConstraint(
            "question_quota BETWEEN 1 AND 20",
            name="ck_revision_session_label_quota",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["revision_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["label_id"], ["label.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id",
            "label_id",
            name="uq_revision_session_label",
        ),
        sa.UniqueConstraint(
            "session_id",
            "label_order",
            name="uq_revision_session_label_order",
        ),
    )
    op.create_index(
        "ix_revision_session_labels_id",
        "revision_session_labels",
        ["id"],
    )

    op.add_column(
        "revision_session_questions",
        sa.Column("learning_item_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "revision_session_questions",
        sa.Column("session_label_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "revision_session_questions",
        sa.Column("learning_item_title_snapshot", sa.String(100), nullable=True),
    )
    op.add_column(
        "revision_session_questions",
        sa.Column("question_text_snapshot", sa.Text(), nullable=True),
    )
    for option in ("a", "b", "c", "d"):
        op.add_column(
            "revision_session_questions",
            sa.Column(f"option_{option}_snapshot", sa.String(255), nullable=True),
        )
    op.add_column(
        "revision_session_questions",
        sa.Column("correct_option_snapshot", sa.String(1), nullable=True),
    )
    op.add_column(
        "revision_session_questions",
        sa.Column("explanation_snapshot", sa.Text(), nullable=True),
    )
    op.add_column(
        "revision_session_questions",
        sa.Column("difficulty_snapshot", sa.Integer(), nullable=True),
    )
    op.add_column(
        "revision_session_questions",
        sa.Column("expected_time_seconds_snapshot", sa.Integer(), nullable=True),
    )
    op.add_column(
        "revision_session_questions",
        sa.Column("source_snapshot", sa.String(20), nullable=True),
    )
    op.add_column(
        "revision_session_questions",
        sa.Column(
            "generated_for_session",
            sa.Boolean(),
            nullable=True,
            server_default=sa.false(),
        ),
    )

    op.execute(
        """
        UPDATE revision_session_questions AS selected
        SET learning_item_id = question.learning_item_id,
            learning_item_title_snapshot = item.title,
            question_text_snapshot = question.question_text,
            option_a_snapshot = question.option_a,
            option_b_snapshot = question.option_b,
            option_c_snapshot = question.option_c,
            option_d_snapshot = question.option_d,
            correct_option_snapshot = question.correct_option,
            explanation_snapshot = question.explanation,
            difficulty_snapshot = question.difficulty,
            expected_time_seconds_snapshot = question.expected_time_seconds,
            source_snapshot = question.source,
            generated_for_session = FALSE
        FROM questions AS question
        JOIN learning_item AS item ON item.id = question.learning_item_id
        WHERE selected.question_id = question.id
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM revision_session_questions
                GROUP BY session_id, question_order
                HAVING COUNT(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'duplicate revision-session question order requires reconciliation';
            END IF;
            IF EXISTS (
                SELECT 1
                FROM revision_session_questions
                WHERE learning_item_id IS NULL
                   OR learning_item_title_snapshot IS NULL
                   OR question_text_snapshot IS NULL
                   OR option_a_snapshot IS NULL
                   OR option_b_snapshot IS NULL
                   OR option_c_snapshot IS NULL
                   OR option_d_snapshot IS NULL
                   OR correct_option_snapshot IS NULL
                   OR difficulty_snapshot IS NULL
                   OR expected_time_seconds_snapshot IS NULL
            ) THEN
                RAISE EXCEPTION
                    'revision-session snapshot backfill is incomplete';
            END IF;
        END $$
        """
    )

    op.create_foreign_key(
        "fk_revision_session_questions_learning_item",
        "revision_session_questions",
        "learning_item",
        ["learning_item_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_revision_session_questions_session_label",
        "revision_session_questions",
        "revision_session_labels",
        ["session_label_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_constraint(
        "revision_session_questions_question_id_fkey",
        "revision_session_questions",
        type_="foreignkey",
    )
    op.alter_column("revision_session_questions", "question_id", nullable=True)
    op.create_foreign_key(
        "revision_session_questions_question_id_fkey",
        "revision_session_questions",
        "questions",
        ["question_id"],
        ["id"],
        ondelete="SET NULL",
    )

    for column_name in (
        "learning_item_title_snapshot",
        "question_text_snapshot",
        "option_a_snapshot",
        "option_b_snapshot",
        "option_c_snapshot",
        "option_d_snapshot",
        "correct_option_snapshot",
        "difficulty_snapshot",
        "expected_time_seconds_snapshot",
        "generated_for_session",
    ):
        op.alter_column("revision_session_questions", column_name, nullable=False)

    op.create_unique_constraint(
        "uq_revision_session_question_order",
        "revision_session_questions",
        ["session_id", "question_order"],
    )
    op.create_check_constraint(
        "ck_revision_session_question_order",
        "revision_session_questions",
        "question_order >= 1",
    )
    op.create_check_constraint(
        "ck_revision_session_question_difficulty",
        "revision_session_questions",
        "difficulty_snapshot BETWEEN 1 AND 3",
    )
    op.create_check_constraint(
        "ck_revision_session_question_expected_time",
        "revision_session_questions",
        "expected_time_seconds_snapshot > 0",
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM revision_session_questions
                WHERE question_id IS NULL OR learning_item_id IS NULL
            ) OR EXISTS (
                SELECT 1
                FROM revision_session_labels
            ) OR EXISTS (
                SELECT 1
                FROM revision_session_questions AS selected
                JOIN questions AS question ON question.id = selected.question_id
                JOIN learning_item AS item ON item.id = selected.learning_item_id
                WHERE selected.learning_item_title_snapshot IS DISTINCT FROM item.title
                   OR selected.question_text_snapshot IS DISTINCT FROM question.question_text
                   OR selected.option_a_snapshot IS DISTINCT FROM question.option_a
                   OR selected.option_b_snapshot IS DISTINCT FROM question.option_b
                   OR selected.option_c_snapshot IS DISTINCT FROM question.option_c
                   OR selected.option_d_snapshot IS DISTINCT FROM question.option_d
                   OR selected.correct_option_snapshot IS DISTINCT FROM question.correct_option
                   OR selected.explanation_snapshot IS DISTINCT FROM question.explanation
                   OR selected.difficulty_snapshot IS DISTINCT FROM question.difficulty
                   OR selected.expected_time_seconds_snapshot
                        IS DISTINCT FROM question.expected_time_seconds
                   OR selected.source_snapshot IS DISTINCT FROM question.source
            ) THEN
                RAISE EXCEPTION
                    'downgrade refused: Phase 1 historical data is not representable';
            END IF;
        END $$
        """
    )

    op.drop_constraint(
        "ck_revision_session_question_expected_time",
        "revision_session_questions",
        type_="check",
    )
    op.drop_constraint(
        "ck_revision_session_question_difficulty",
        "revision_session_questions",
        type_="check",
    )
    op.drop_constraint(
        "ck_revision_session_question_order",
        "revision_session_questions",
        type_="check",
    )
    op.drop_constraint(
        "uq_revision_session_question_order",
        "revision_session_questions",
        type_="unique",
    )
    op.drop_constraint(
        "revision_session_questions_question_id_fkey",
        "revision_session_questions",
        type_="foreignkey",
    )
    op.alter_column("revision_session_questions", "question_id", nullable=False)
    op.create_foreign_key(
        "revision_session_questions_question_id_fkey",
        "revision_session_questions",
        "questions",
        ["question_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint(
        "fk_revision_session_questions_session_label",
        "revision_session_questions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_revision_session_questions_learning_item",
        "revision_session_questions",
        type_="foreignkey",
    )
    for column_name in (
        "generated_for_session",
        "source_snapshot",
        "expected_time_seconds_snapshot",
        "difficulty_snapshot",
        "explanation_snapshot",
        "correct_option_snapshot",
        "option_d_snapshot",
        "option_c_snapshot",
        "option_b_snapshot",
        "option_a_snapshot",
        "question_text_snapshot",
        "learning_item_title_snapshot",
        "session_label_id",
        "learning_item_id",
    ):
        op.drop_column("revision_session_questions", column_name)

    op.drop_index(
        "ix_revision_session_labels_id",
        table_name="revision_session_labels",
    )
    op.drop_table("revision_session_labels")

    op.drop_index(
        "ix_revision_sessions_user_status_started",
        table_name="revision_sessions",
    )
    for constraint_name in (
        "ck_revision_session_generated_count",
        "ck_revision_session_questions_per_label",
        "ck_revision_session_question_count",
        "ck_revision_session_status",
        "ck_revision_session_strategy_used",
        "ck_revision_session_requested_strategy",
    ):
        op.drop_constraint(constraint_name, "revision_sessions", type_="check")
    for column_name in (
        "allow_ai_generation",
        "generated_question_count",
        "questions_per_label",
        "requested_question_count",
        "status",
        "strategy_used",
        "requested_strategy",
    ):
        op.drop_column("revision_sessions", column_name)
