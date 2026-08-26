from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    TIMESTAMP,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from src.db.base import Base


class AIGenerationEvent(Base):
    __tablename__ = "ai_generation_events"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    label_id = Column(
        Integer,
        ForeignKey("label.id", ondelete="SET NULL"),
        nullable=True,
    )
    operation_type = Column(String(40), nullable=False)
    provider = Column(String(50), nullable=True)
    model = Column(String(100), nullable=True)
    prompt_template_version = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)
    requested_count = Column(Integer, nullable=False)
    valid_count = Column(Integer, nullable=False, default=0, server_default="0")
    persisted_count = Column(Integer, nullable=False, default=0, server_default="0")
    duplicate_count = Column(Integer, nullable=False, default=0, server_default="0")
    rejected_count = Column(Integer, nullable=False, default=0, server_default="0")
    excess_count = Column(Integer, nullable=False, default=0, server_default="0")
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    cached_tokens = Column(Integer, nullable=True)
    thought_tokens = Column(Integer, nullable=True)
    tool_tokens = Column(Integer, nullable=True)
    estimated_input_tokens = Column(Integer, nullable=True)
    input_token_count_estimated = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    response_id = Column(String(255), nullable=True)
    safe_error_code = Column(String(80), nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    started_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "operation_type IN ("
            "'LEARNING_ITEM_CREATE', 'LEARNING_ITEM_REGENERATE', "
            "'SESSION_SHORTAGE', 'LABEL_PROACTIVE')",
            name="ck_ai_generation_event_operation",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'PARTIAL', 'FAILED')",
            name="ck_ai_generation_event_status",
        ),
        CheckConstraint(
            "requested_count > 0",
            name="ck_ai_generation_event_requested_count",
        ),
        CheckConstraint(
            "valid_count >= 0 AND persisted_count >= 0 "
            "AND duplicate_count >= 0 AND rejected_count >= 0 "
            "AND excess_count >= 0",
            name="ck_ai_generation_event_counts",
        ),
        CheckConstraint(
            "valid_count <= requested_count "
            "AND persisted_count <= valid_count "
            "AND duplicate_count <= valid_count "
            "AND valid_count + rejected_count <= requested_count",
            name="ck_ai_generation_event_count_bounds",
        ),
        CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name="ck_ai_generation_event_input_tokens",
        ),
        CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name="ck_ai_generation_event_output_tokens",
        ),
        CheckConstraint(
            "total_tokens IS NULL OR total_tokens >= 0",
            name="ck_ai_generation_event_total_tokens",
        ),
        CheckConstraint(
            "estimated_input_tokens IS NULL OR estimated_input_tokens >= 0",
            name="ck_ai_generation_event_estimated_tokens",
        ),
        CheckConstraint(
            "cached_tokens IS NULL OR cached_tokens >= 0",
            name="ck_ai_generation_event_cached_tokens",
        ),
        CheckConstraint(
            "thought_tokens IS NULL OR thought_tokens >= 0",
            name="ck_ai_generation_event_thought_tokens",
        ),
        CheckConstraint(
            "tool_tokens IS NULL OR tool_tokens >= 0",
            name="ck_ai_generation_event_tool_tokens",
        ),
        Index(
            "ix_ai_generation_events_user_created",
            "user_id",
            "created_at",
        ),
        Index(
            "ix_ai_generation_events_status_created",
            "status",
            "created_at",
        ),
        Index(
            "ix_ai_generation_events_label_created",
            "label_id",
            "created_at",
        ),
    )


class AIGenerationCall(Base):
    __tablename__ = "ai_generation_calls"

    id = Column(Integer, primary_key=True)
    generation_event_id = Column(
        Integer,
        ForeignKey("ai_generation_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    learning_item_id = Column(
        Integer,
        ForeignKey("learning_item.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_identifier = Column(String(64), nullable=False)
    call_order = Column(Integer, nullable=False)
    allocated_count = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False)
    valid_count = Column(Integer, nullable=False, default=0, server_default="0")
    persisted_count = Column(Integer, nullable=False, default=0, server_default="0")
    duplicate_count = Column(Integer, nullable=False, default=0, server_default="0")
    rejected_count = Column(Integer, nullable=False, default=0, server_default="0")
    excess_count = Column(Integer, nullable=False, default=0, server_default="0")
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    cached_tokens = Column(Integer, nullable=True)
    thought_tokens = Column(Integer, nullable=True)
    tool_tokens = Column(Integer, nullable=True)
    estimated_input_tokens = Column(Integer, nullable=True)
    input_token_count_estimated = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    provider = Column(String(50), nullable=True)
    model = Column(String(100), nullable=True)
    response_id = Column(String(255), nullable=True)
    safe_error_code = Column(String(80), nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    started_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "generation_event_id",
            "call_order",
            name="uq_ai_generation_call_order",
        ),
        CheckConstraint(
            "call_order >= 1",
            name="ck_ai_generation_call_order",
        ),
        CheckConstraint(
            "allocated_count > 0",
            name="ck_ai_generation_call_allocated_count",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'PARTIAL', 'FAILED')",
            name="ck_ai_generation_call_status",
        ),
        CheckConstraint(
            "valid_count >= 0 AND persisted_count >= 0 "
            "AND duplicate_count >= 0 AND rejected_count >= 0 "
            "AND excess_count >= 0",
            name="ck_ai_generation_call_counts",
        ),
        CheckConstraint(
            "valid_count <= allocated_count "
            "AND persisted_count <= valid_count "
            "AND duplicate_count <= valid_count "
            "AND valid_count + rejected_count <= allocated_count",
            name="ck_ai_generation_call_count_bounds",
        ),
        CheckConstraint(
            "(input_tokens IS NULL OR input_tokens >= 0) "
            "AND (output_tokens IS NULL OR output_tokens >= 0) "
            "AND (total_tokens IS NULL OR total_tokens >= 0) "
            "AND (cached_tokens IS NULL OR cached_tokens >= 0) "
            "AND (thought_tokens IS NULL OR thought_tokens >= 0) "
            "AND (tool_tokens IS NULL OR tool_tokens >= 0) "
            "AND (estimated_input_tokens IS NULL OR estimated_input_tokens >= 0)",
            name="ck_ai_generation_call_tokens",
        ),
        Index(
            "ix_ai_generation_calls_item_created",
            "learning_item_id",
            "created_at",
        ),
    )
