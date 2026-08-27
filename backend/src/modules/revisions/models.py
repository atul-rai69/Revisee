from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    TIMESTAMP,
    UniqueConstraint,
)
from sqlalchemy.sql import func
from sqlalchemy.sql import expression

from src.db.base import Base


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    learning_item_id = Column(
        Integer,
        ForeignKey("learning_item.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_text = Column(Text, nullable=False)
    option_a = Column(String(255), nullable=False)
    option_b = Column(String(255), nullable=False)
    option_c = Column(String(255), nullable=False)
    option_d = Column(String(255), nullable=False)
    correct_option = Column(String(1), nullable=False)
    explanation = Column(Text)
    difficulty = Column(Integer, nullable=False)
    expected_time_seconds = Column(Integer, nullable=False)
    source = Column(String(20))
    content_fingerprint = Column(String(64), nullable=True)
    generation_event_id = Column(
        Integer,
        ForeignKey("ai_generation_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        Index(
            "uq_questions_learning_item_fingerprint",
            "learning_item_id",
            "content_fingerprint",
            unique=True,
            postgresql_where=expression.column("content_fingerprint").isnot(None),
        ),
        Index("ix_questions_generation_event_id", "generation_event_id"),
    )


class RevisionSession(Base):
    __tablename__ = "revision_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Deprecated compatibility column; reads use requested_strategy instead.
    quiz_type = Column(String(20), nullable=False)
    requested_strategy = Column(String(20), nullable=False)
    strategy_used = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="IN_PROGRESS")
    requested_question_count = Column(Integer, nullable=False)
    questions_per_label = Column(Integer, nullable=True)
    generated_question_count = Column(Integer, nullable=False, default=0)
    allow_ai_generation = Column(Boolean, nullable=False, default=False)
    started_at = Column(TIMESTAMP, server_default=func.now())
    ended_at = Column(TIMESTAMP, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "requested_strategy IN ('RANDOM', 'LABEL')",
            name="ck_revision_session_requested_strategy",
        ),
        CheckConstraint(
            "strategy_used IN ('RANDOM', 'LABEL')",
            name="ck_revision_session_strategy_used",
        ),
        CheckConstraint(
            "status IN ('IN_PROGRESS', 'COMPLETED')",
            name="ck_revision_session_status",
        ),
        CheckConstraint(
            "requested_question_count BETWEEN 1 AND 50",
            name="ck_revision_session_question_count",
        ),
        CheckConstraint(
            "questions_per_label IS NULL OR questions_per_label BETWEEN 1 AND 20",
            name="ck_revision_session_questions_per_label",
        ),
        CheckConstraint(
            "generated_question_count BETWEEN 0 AND requested_question_count",
            name="ck_revision_session_generated_count",
        ),
        CheckConstraint(
            "(status = 'IN_PROGRESS' AND ended_at IS NULL) OR "
            "(status = 'COMPLETED' AND ended_at IS NOT NULL)",
            name="ck_revision_session_lifecycle",
        ),
        Index(
            "ix_revision_sessions_user_status_started",
            "user_id",
            "status",
            "started_at",
        ),
    )


class RevisionSessionLabel(Base):
    __tablename__ = "revision_session_labels"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(
        Integer,
        ForeignKey("revision_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    label_id = Column(
        Integer,
        ForeignKey("label.id", ondelete="SET NULL"),
        nullable=True,
    )
    label_name_snapshot = Column(String(200), nullable=False)
    label_order = Column(Integer, nullable=False)
    question_quota = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "label_id",
            name="uq_revision_session_label",
        ),
        UniqueConstraint(
            "session_id",
            "label_order",
            name="uq_revision_session_label_order",
        ),
        CheckConstraint(
            "label_order >= 1",
            name="ck_revision_session_label_order",
        ),
        CheckConstraint(
            "question_quota BETWEEN 1 AND 20",
            name="ck_revision_session_label_quota",
        ),
    )


class UserAttempt(Base):
    __tablename__ = "user_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id = Column(
        Integer,
        ForeignKey("questions.id", ondelete="SET NULL"),
        nullable=True,
    )
    session_id = Column(
        Integer,
        ForeignKey("revision_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_question_id = Column(Integer, nullable=False)
    selected_option = Column(
        Enum("A", "B", "C", "D", name="answer_option_enum"),
        nullable=False,
    )
    is_correct = Column(Boolean, nullable=False)
    time_taken_seconds = Column(Integer, nullable=False)
    mastery_delta = Column(Numeric(6, 2), nullable=False)
    attempted_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "session_question_id",
            name="uq_user_attempt_session_question",
        ),
        ForeignKeyConstraint(
            ["session_question_id", "session_id"],
            [
                "revision_session_questions.id",
                "revision_session_questions.session_id",
            ],
            ondelete="CASCADE",
            name="fk_user_attempt_session_question_membership",
        ),
        CheckConstraint(
            "time_taken_seconds BETWEEN 0 AND 3600",
            name="ck_user_attempt_time_taken",
        ),
        Index("ix_user_attempts_session_attempted", "session_id", "attempted_at"),
        Index("ix_user_attempts_user_attempted", "user_id", "attempted_at"),
        Index("ix_user_attempts_question_attempted", "question_id", "attempted_at"),
    )


class RevisionSessionQuestion(Base):
    __tablename__ = "revision_session_questions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(
        Integer,
        ForeignKey("revision_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id = Column(
        Integer,
        ForeignKey("questions.id", ondelete="SET NULL"),
        nullable=True,
    )
    learning_item_id = Column(
        Integer,
        ForeignKey("learning_item.id", ondelete="SET NULL"),
        nullable=True,
    )
    session_label_id = Column(
        Integer,
        ForeignKey("revision_session_labels.id", ondelete="SET NULL"),
        nullable=True,
    )
    question_order = Column(Integer, nullable=False)
    learning_item_title_snapshot = Column(String(100), nullable=False)
    question_text_snapshot = Column(Text, nullable=False)
    option_a_snapshot = Column(String(255), nullable=False)
    option_b_snapshot = Column(String(255), nullable=False)
    option_c_snapshot = Column(String(255), nullable=False)
    option_d_snapshot = Column(String(255), nullable=False)
    correct_option_snapshot = Column(String(1), nullable=False)
    explanation_snapshot = Column(Text, nullable=True)
    difficulty_snapshot = Column(Integer, nullable=False)
    expected_time_seconds_snapshot = Column(Integer, nullable=False)
    source_snapshot = Column(String(20), nullable=True)
    generated_for_session = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint(
            "id",
            "session_id",
            name="uq_revision_session_question_id_session",
        ),
        UniqueConstraint(
            "session_id",
            "question_id",
            name="uq_revision_session_question",
        ),
        UniqueConstraint(
            "session_id",
            "question_order",
            name="uq_revision_session_question_order",
        ),
        CheckConstraint(
            "question_order >= 1",
            name="ck_revision_session_question_order",
        ),
        CheckConstraint(
            "difficulty_snapshot BETWEEN 1 AND 3",
            name="ck_revision_session_question_difficulty",
        ),
        CheckConstraint(
            "expected_time_seconds_snapshot > 0",
            name="ck_revision_session_question_expected_time",
        ),
    )


class QuestionStatistics(Base):
    __tablename__ = "question_statistics"

    question_id = Column(
        Integer,
        ForeignKey("questions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    total_attempt_count = Column(
        Integer, nullable=False, default=0, server_default="0"
    )
    correct_attempt_count = Column(
        Integer, nullable=False, default=0, server_default="0"
    )
    total_time_seconds = Column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    average_time_seconds = Column(
        Numeric(10, 2), nullable=False, default=0, server_default="0.00"
    )
    last_attempted_at = Column(TIMESTAMP, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "total_attempt_count >= 0 AND correct_attempt_count >= 0 "
            "AND correct_attempt_count <= total_attempt_count",
            name="ck_question_statistics_counts",
        ),
        CheckConstraint(
            "total_time_seconds >= 0",
            name="ck_question_statistics_total_time",
        ),
        CheckConstraint(
            "average_time_seconds BETWEEN 0 AND 3600",
            name="ck_question_statistics_average_time",
        ),
        Index("ix_question_statistics_last_attempted", "last_attempted_at"),
    )
