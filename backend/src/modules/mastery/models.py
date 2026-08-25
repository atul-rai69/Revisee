from sqlalchemy import Column, ForeignKey, Integer, TIMESTAMP, UniqueConstraint

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
    mastery_score = Column(Integer, default=50)
    total_attempts = Column(Integer, default=0)
    correct_attempts = Column(Integer, default=0)
    last_attempt_at = Column(TIMESTAMP)
    last_reviewed_at = Column(TIMESTAMP)
    next_review_at = Column(TIMESTAMP)

    __table_args__ = (
        UniqueConstraint("user_id", "label_id", name="uq_user_label_mastery"),
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
    mastery_score = Column(Integer, default=50)
    total_attempts = Column(Integer, default=0)
    correct_attempts = Column(Integer, default=0)
    last_attempt_at = Column(TIMESTAMP)
    last_reviewed_at = Column(TIMESTAMP)
    next_review_at = Column(TIMESTAMP)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "learning_item_id",
            name="uq_user_learning_item_mastery",
        ),
    )
