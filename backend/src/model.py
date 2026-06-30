from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Enum,
    Boolean,
    TIMESTAMP
)
from sqlalchemy.sql import func
from sqlalchemy import UniqueConstraint
from src.db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class LearningItem(Base):
    __tablename__ = "learning_item"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    title = Column(String(100), nullable=False)
    description_text = Column(Text)
    theory = Column(Text)

    created_at = Column(DateTime, server_default=func.now())

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )

class LearningItemKeyPoint(Base):
    __tablename__ = "learning_item_key_points"

    id = Column(Integer, primary_key=True)
    
    learning_item_id = Column(
        Integer,
        ForeignKey("learning_item.id")
    )

    key_point = Column(Text, nullable=False)


class Label(Base):
    __tablename__ = "label"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    label_name = Column(String(200), nullable=False)


class LearningItemLabel(Base):
    __tablename__ = "learning_item_label"

    id = Column(Integer, primary_key=True, index=True)

    learning_item_id = Column(
        Integer,
        ForeignKey("learning_item.id", ondelete="CASCADE"),
        nullable=False
    )

    label_id = Column(
        Integer,
        ForeignKey("label.id", ondelete="CASCADE"),
        nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "learning_item_id",
            "label_id",
            name="uq_learning_item_label"
        ),
    )


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)

    learning_item_id = Column(
        Integer,
        ForeignKey("learning_item.id", ondelete="CASCADE"),
        nullable=False
    )

    question_text = Column(Text, nullable=False)

    option_a = Column(String(255), nullable=False)
    option_b = Column(String(255), nullable=False)
    option_c = Column(String(255), nullable=False)
    option_d = Column(String(255), nullable=False)

    correct_option = Column(
        Enum("A", "B", "C", "D"),
        nullable=False
    )

    explanation = Column(Text)

    difficulty = Column(
        Integer,
        nullable=False
    )

    expected_time_seconds = Column(
        Integer,
        nullable=False
    )

    source = Column(
        Enum("manual", "future-ai"),
        default="manual"
    )

    created_at = Column(
        TIMESTAMP,
        server_default=func.now()
    )


class RevisionSession(Base):
    __tablename__ = "revision_sessions"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    quiz_type = Column(
        String(20),
        nullable=False
    )

    started_at = Column(
        TIMESTAMP,
        server_default=func.now()
    )

    ended_at = Column(
        TIMESTAMP,
        nullable=True
    )


class UserAttempt(Base):
    __tablename__ = "user_attempts"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    question_id = Column(
        Integer,
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False
    )

    session_id = Column(
        Integer,
        ForeignKey("revision_sessions.id", ondelete="CASCADE"),
        nullable=False
    )

    selected_option = Column(
        Enum("A", "B", "C", "D"),
        nullable=False
    )

    is_correct = Column(Boolean, nullable=False)

    attempted_at = Column(TIMESTAMP, server_default=func.now())



class Media(Base):
    __tablename__ = "media"

    id = Column(Integer, primary_key=True, index=True)

    learning_item_id = Column(
        Integer,
        ForeignKey(
            "learning_item.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    type = Column(
        Enum(
            "image",
            "video",
            "pdf"
        ),
        nullable=False
    )

    url = Column(
        String(500),
        nullable=False
    )

    public_id = Column(
        String(300),
        nullable=False
    )

class UserSession(Base):

    __tablename__ = "user_sessions"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    session_id = Column(
        String(255),
        unique=True,
        nullable=False
    )

    is_active = Column(
        Boolean,
        default=True
    )

    created_at = Column(
        TIMESTAMP,
        server_default=func.now()
    )

    expires_at = Column(
        TIMESTAMP,
        nullable=True
    )

    last_used_at = Column(
        TIMESTAMP,
        server_default=func.now(),
        onupdate=func.now()
    )



class RevisionSessionQuestion(Base):
    __tablename__ = "revision_session_questions"

    id = Column(Integer, primary_key=True, index=True)

    session_id = Column(
        Integer,
        ForeignKey("revision_sessions.id", ondelete="CASCADE"),
        nullable=False
    )

    question_id = Column(
        Integer,
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False
    )

    question_order = Column(
        Integer,
        nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "question_id",
            name="uq_revision_session_question"
        ),
    )


class UserLabelMastery(Base):
    __tablename__ = "user_label_mastery"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    label_id = Column(
        Integer,
        ForeignKey("label.id", ondelete="CASCADE"),
        nullable=False
    )

    mastery_score = Column(
        Integer,
        default=50
    )

    total_attempts = Column(
        Integer,
        default=0
    )

    correct_attempts = Column(
        Integer,
        default=0
    )

    last_attempt_at = Column(TIMESTAMP)

    last_reviewed_at = Column(TIMESTAMP)

    next_review_at = Column(TIMESTAMP)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "label_id",
            name="uq_user_label_mastery"
        ),
    )


class UserLearningItemMastery(Base):
    __tablename__ = "user_learning_item_mastery"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    learning_item_id = Column(
        Integer,
        ForeignKey("learning_item.id", ondelete="CASCADE"),
        nullable=False
    )

    mastery_score = Column(
        Integer,
        default=50
    )

    total_attempts = Column(
        Integer,
        default=0
    )

    correct_attempts = Column(
        Integer,
        default=0
    )

    last_attempt_at = Column(TIMESTAMP)

    last_reviewed_at = Column(TIMESTAMP)

    next_review_at = Column(TIMESTAMP)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "learning_item_id",
            name="uq_user_learning_item_mastery"
        ),
    )


