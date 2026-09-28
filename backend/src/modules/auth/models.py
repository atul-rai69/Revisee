from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, TIMESTAMP
from sqlalchemy.sql import func

from src.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash = Column(String(64), unique=True, nullable=False)
    family_id = Column(String(36), nullable=False)
    parent_session_id = Column(
        Integer,
        ForeignKey("user_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    issued_at = Column(TIMESTAMP(timezone=True), nullable=False)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    absolute_expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    last_used_at = Column(TIMESTAMP(timezone=True), nullable=False)
    revoked_at = Column(TIMESTAMP(timezone=True), nullable=True)
    replaced_by_session_id = Column(
        Integer,
        ForeignKey("user_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_agent = Column(String(255), nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_user_sessions_user_id", "user_id"),
        Index("ix_user_sessions_family_id", "family_id"),
        Index("ix_user_sessions_expires_at", "expires_at"),
    )
