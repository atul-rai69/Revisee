from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    TIMESTAMP,
    UniqueConstraint,
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
