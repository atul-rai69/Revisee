from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    TIMESTAMP,
    UniqueConstraint,
    text,
)
from sqlalchemy.sql import func

from src.db.base import Base


class AICredential(Base):
    __tablename__ = "ai_credentials"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider = Column(String(20), nullable=False, default="GEMINI")
    name = Column(String(80), nullable=False)
    encrypted_secret = Column(LargeBinary, nullable=False)
    encryption_nonce = Column(LargeBinary, nullable=False)
    encryption_key_version = Column(String(40), nullable=False)
    key_fingerprint = Column(String(64), nullable=False)
    key_hint = Column(String(4), nullable=False)
    status = Column(String(20), nullable=False, default="VALID")
    is_default = Column(Boolean, nullable=False, default=False, server_default="false")
    last_validated_at = Column(TIMESTAMP, nullable=False)
    last_used_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(
        TIMESTAMP,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("user_id", "provider", "name", name="uq_ai_credential_name"),
        UniqueConstraint(
            "user_id",
            "provider",
            "key_fingerprint",
            name="uq_ai_credential_fingerprint",
        ),
        CheckConstraint("provider IN ('GEMINI')", name="ck_ai_credential_provider"),
        CheckConstraint(
            "status IN ('VALID', 'INVALID')", name="ck_ai_credential_status"
        ),
        Index("ix_ai_credentials_user_provider", "user_id", "provider"),
        Index(
            "uq_ai_credentials_default",
            "user_id",
            "provider",
            unique=True,
            postgresql_where=text("is_default"),
        ),
    )


class AICredentialUsage(Base):
    __tablename__ = "ai_credential_usage"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    credential_id = Column(
        Integer,
        ForeignKey("ai_credentials.id", ondelete="CASCADE"),
        nullable=False,
    )
    operation_type = Column(String(40), nullable=False)
    provider = Column(String(20), nullable=False)
    model = Column(String(100), nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("provider IN ('GEMINI')", name="ck_ai_credential_usage_provider"),
        CheckConstraint(
            "(input_tokens IS NULL OR input_tokens >= 0) AND "
            "(output_tokens IS NULL OR output_tokens >= 0) AND "
            "(total_tokens IS NULL OR total_tokens >= 0)",
            name="ck_ai_credential_usage_tokens",
        ),
        Index(
            "ix_ai_credential_usage_user_credential_time",
            "user_id",
            "credential_id",
            "created_at",
        ),
    )
