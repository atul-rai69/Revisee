from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    TIMESTAMP,
    UniqueConstraint,
    String,
)

from src.db.base import Base


class UserLabelMastery(Base):
    __tablename__ = "user_label_mastery"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    label_id = Column(
        Integer,
        ForeignKey("label.id", ondelete="CASCADE"),
        nullable=False,
    )
    mastery_score = Column(
        Numeric(5, 2), nullable=False, default=50, server_default="50.00"
    )
    total_attempts = Column(Integer, nullable=False, default=0, server_default="0")
    correct_attempts = Column(Integer, nullable=False, default=0, server_default="0")
    last_attempt_at = Column(TIMESTAMP)
    last_reviewed_at = Column(TIMESTAMP)
    next_review_at = Column(TIMESTAMP)

    __table_args__ = (
        UniqueConstraint("user_id", "label_id", name="uq_user_label_mastery"),
        CheckConstraint(
            "mastery_score BETWEEN 0 AND 100",
            name="ck_user_label_mastery_score",
        ),
        CheckConstraint(
            "total_attempts >= 0 AND correct_attempts >= 0 "
            "AND correct_attempts <= total_attempts",
            name="ck_user_label_mastery_counts",
        ),
        Index(
            "ix_user_label_mastery_user_next_review",
            "user_id",
            "next_review_at",
        ),
    )


class UserLearningItemMastery(Base):
    __tablename__ = "user_learning_item_mastery"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    learning_item_id = Column(
        Integer,
        ForeignKey("learning_item.id", ondelete="CASCADE"),
        nullable=False,
    )
    mastery_score = Column(
        Numeric(5, 2), nullable=False, default=50, server_default="50.00"
    )
    total_attempts = Column(Integer, nullable=False, default=0, server_default="0")
    correct_attempts = Column(Integer, nullable=False, default=0, server_default="0")
    last_attempt_at = Column(TIMESTAMP)
    last_reviewed_at = Column(TIMESTAMP)
    next_review_at = Column(TIMESTAMP)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "learning_item_id",
            name="uq_user_learning_item_mastery",
        ),
        CheckConstraint(
            "mastery_score BETWEEN 0 AND 100",
            name="ck_user_learning_item_mastery_score",
        ),
        CheckConstraint(
            "total_attempts >= 0 AND correct_attempts >= 0 "
            "AND correct_attempts <= total_attempts",
            name="ck_user_learning_item_mastery_counts",
        ),
        Index(
            "ix_user_learning_item_mastery_user_next_review",
            "user_id",
            "next_review_at",
        ),
    )


class MasteryHistory(Base):
    """Append-only evidence captured in the same transaction as mastery updates."""

    __tablename__ = "mastery_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    entity_type = Column(String(20), nullable=False)
    entity_id = Column(Integer, nullable=False)
    session_id = Column(
        Integer,
        ForeignKey("revision_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    recorded_at = Column(TIMESTAMP, nullable=False)
    score_before = Column(Numeric(5, 2), nullable=False)
    score_after = Column(Numeric(5, 2), nullable=False)
    total_attempts = Column(Integer, nullable=False)
    correct_attempts = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "user_id", "session_id", "entity_type", "entity_id",
            name="uq_mastery_history_session_entity",
        ),
        CheckConstraint(
            "entity_type IN ('LABEL', 'LEARNING_ITEM')",
            name="ck_mastery_history_entity_type",
        ),
        CheckConstraint(
            "score_before BETWEEN 0 AND 100 AND score_after BETWEEN 0 AND 100",
            name="ck_mastery_history_scores",
        ),
        CheckConstraint(
            "total_attempts >= 0 AND correct_attempts >= 0 "
            "AND correct_attempts <= total_attempts",
            name="ck_mastery_history_counts",
        ),
        Index("ix_mastery_history_user_entity_time", "user_id", "entity_type", "entity_id", "recorded_at"),
    )
