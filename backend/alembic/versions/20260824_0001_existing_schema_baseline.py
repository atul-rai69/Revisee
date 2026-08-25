"""Baseline for the existing Revisee schema.

This revision is intended to create a new empty database. An existing database
must be inspected and stamped only after its schema is confirmed equivalent.
"""
from collections.abc import Sequence

from alembic import op
from sqlalchemy.dialects import postgresql
import sqlalchemy as sa


revision: str = "20260824_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    media_type = postgresql.ENUM(
        "image", "video", "pdf", name="media_type_enum"
    )
    answer_option = postgresql.ENUM(
        "A", "B", "C", "D", name="answer_option_enum"
    )
    media_type.create(bind, checkfirst=True)
    answer_option.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("email", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_id", "users", ["id"])

    op.create_table(
        "learning_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("description_text", sa.Text()),
        sa.Column("theory", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_learning_item_id", "learning_item", ["id"])

    op.create_table(
        "learning_item_key_points",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("learning_item_id", sa.Integer()),
        sa.Column("key_point", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["learning_item_id"], ["learning_item.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "label",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("label_name", sa.String(200), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_label_id", "label", ["id"])

    op.create_table(
        "learning_item_label",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("learning_item_id", sa.Integer(), nullable=False),
        sa.Column("label_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["learning_item_id"], ["learning_item.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["label_id"], ["label.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "learning_item_id", "label_id", name="uq_learning_item_label"
        ),
    )
    op.create_index("ix_learning_item_label_id", "learning_item_label", ["id"])

    op.create_table(
        "questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("learning_item_id", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("option_a", sa.String(255), nullable=False),
        sa.Column("option_b", sa.String(255), nullable=False),
        sa.Column("option_c", sa.String(255), nullable=False),
        sa.Column("option_d", sa.String(255), nullable=False),
        sa.Column("correct_option", sa.String(1), nullable=False),
        sa.Column("explanation", sa.Text()),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column("expected_time_seconds", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(20)),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["learning_item_id"], ["learning_item.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_questions_id", "questions", ["id"])

    op.create_table(
        "revision_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("quiz_type", sa.String(20), nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(), server_default=sa.func.now()),
        sa.Column("ended_at", sa.TIMESTAMP()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_revision_sessions_id", "revision_sessions", ["id"])

    op.create_table(
        "user_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column(
            "selected_option",
            postgresql.ENUM(
                "A", "B", "C", "D", name="answer_option_enum", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("attempted_at", sa.TIMESTAMP(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["question_id"], ["questions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["revision_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_attempts_id", "user_attempts", ["id"])

    op.create_table(
        "media",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("learning_item_id", sa.Integer(), nullable=False),
        sa.Column(
            "type",
            postgresql.ENUM(
                "image", "video", "pdf", name="media_type_enum", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("public_id", sa.String(300), nullable=False),
        sa.ForeignKeyConstraint(
            ["learning_item_id"], ["learning_item.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_media_id", "media", ["id"])

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean()),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now()),
        sa.Column("expires_at", sa.TIMESTAMP()),
        sa.Column("last_used_at", sa.TIMESTAMP(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
    )
    op.create_index("ix_user_sessions_id", "user_sessions", ["id"])

    op.create_table(
        "revision_session_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("question_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"], ["revision_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["question_id"], ["questions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id", "question_id", name="uq_revision_session_question"
        ),
    )
    op.create_index(
        "ix_revision_session_questions_id", "revision_session_questions", ["id"]
    )

    op.create_table(
        "user_label_mastery",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("label_id", sa.Integer(), nullable=False),
        sa.Column("mastery_score", sa.Integer()),
        sa.Column("total_attempts", sa.Integer()),
        sa.Column("correct_attempts", sa.Integer()),
        sa.Column("last_attempt_at", sa.TIMESTAMP()),
        sa.Column("last_reviewed_at", sa.TIMESTAMP()),
        sa.Column("next_review_at", sa.TIMESTAMP()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["label_id"], ["label.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "label_id", name="uq_user_label_mastery"),
    )
    op.create_index("ix_user_label_mastery_id", "user_label_mastery", ["id"])

    op.create_table(
        "user_learning_item_mastery",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("learning_item_id", sa.Integer(), nullable=False),
        sa.Column("mastery_score", sa.Integer()),
        sa.Column("total_attempts", sa.Integer()),
        sa.Column("correct_attempts", sa.Integer()),
        sa.Column("last_attempt_at", sa.TIMESTAMP()),
        sa.Column("last_reviewed_at", sa.TIMESTAMP()),
        sa.Column("next_review_at", sa.TIMESTAMP()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["learning_item_id"], ["learning_item.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "learning_item_id", name="uq_user_learning_item_mastery"
        ),
    )
    op.create_index(
        "ix_user_learning_item_mastery_id", "user_learning_item_mastery", ["id"]
    )


def downgrade() -> None:
    for table_name in (
        "user_learning_item_mastery",
        "user_label_mastery",
        "revision_session_questions",
        "user_sessions",
        "media",
        "user_attempts",
        "revision_sessions",
        "questions",
        "learning_item_label",
        "label",
        "learning_item_key_points",
        "learning_item",
        "users",
    ):
        op.drop_table(table_name)

    bind = op.get_bind()
    postgresql.ENUM(name="answer_option_enum").drop(bind, checkfirst=True)
    postgresql.ENUM(name="media_type_enum").drop(bind, checkfirst=True)
