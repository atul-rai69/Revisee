from sqlalchemy import Column, Enum, ForeignKey, Integer, String, Text, TIMESTAMP, UniqueConstraint, Boolean
from sqlalchemy.sql import func

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
    created_at = Column(TIMESTAMP, server_default=func.now())


class RevisionSession(Base):
    __tablename__ = "revision_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    quiz_type = Column(String(20), nullable=False)
    started_at = Column(TIMESTAMP, server_default=func.now())
    ended_at = Column(TIMESTAMP, nullable=True)


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
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_id = Column(
        Integer,
        ForeignKey("revision_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    selected_option = Column(
        Enum("A", "B", "C", "D", name="answer_option_enum"),
        nullable=False,
    )
    is_correct = Column(Boolean, nullable=False)
    attempted_at = Column(TIMESTAMP, server_default=func.now())


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
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_order = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "question_id",
            name="uq_revision_session_question",
        ),
    )
