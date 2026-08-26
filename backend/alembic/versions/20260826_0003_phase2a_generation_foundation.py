"""Add the Phase 2A AI question-generation foundation.

Existing questions remain unchanged: fingerprints and generation-event links
are nullable and are populated only for newly generated question-only content.
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260826_0003"
down_revision: str | None = "20260825_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_generation_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("label_id", sa.Integer(), nullable=True),
        sa.Column("operation_type", sa.String(40), nullable=False),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("prompt_template_version", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("requested_count", sa.Integer(), nullable=False),
        sa.Column("valid_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "persisted_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "duplicate_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "rejected_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("excess_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("cached_tokens", sa.Integer(), nullable=True),
        sa.Column("thought_tokens", sa.Integer(), nullable=True),
        sa.Column("tool_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_input_tokens", sa.Integer(), nullable=True),
        sa.Column(
            "input_token_count_estimated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("response_id", sa.String(255), nullable=True),
        sa.Column("safe_error_code", sa.String(80), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(), nullable=True),
        sa.CheckConstraint(
            "operation_type IN ("
            "'LEARNING_ITEM_CREATE', 'LEARNING_ITEM_REGENERATE', "
            "'SESSION_SHORTAGE', 'LABEL_PROACTIVE')",
            name="ck_ai_generation_event_operation",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'PARTIAL', 'FAILED')",
            name="ck_ai_generation_event_status",
        ),
        sa.CheckConstraint(
            "requested_count > 0",
            name="ck_ai_generation_event_requested_count",
        ),
        sa.CheckConstraint(
            "valid_count >= 0 AND persisted_count >= 0 "
            "AND duplicate_count >= 0 AND rejected_count >= 0 "
            "AND excess_count >= 0",
            name="ck_ai_generation_event_counts",
        ),
        sa.CheckConstraint(
            "valid_count <= requested_count "
            "AND persisted_count <= valid_count "
            "AND duplicate_count <= valid_count "
            "AND valid_count + rejected_count <= requested_count",
            name="ck_ai_generation_event_count_bounds",
        ),
        sa.CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name="ck_ai_generation_event_input_tokens",
        ),
        sa.CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name="ck_ai_generation_event_output_tokens",
        ),
        sa.CheckConstraint(
            "total_tokens IS NULL OR total_tokens >= 0",
            name="ck_ai_generation_event_total_tokens",
        ),
        sa.CheckConstraint(
            "estimated_input_tokens IS NULL OR estimated_input_tokens >= 0",
            name="ck_ai_generation_event_estimated_tokens",
        ),
        sa.CheckConstraint(
            "cached_tokens IS NULL OR cached_tokens >= 0",
            name="ck_ai_generation_event_cached_tokens",
        ),
        sa.CheckConstraint(
            "thought_tokens IS NULL OR thought_tokens >= 0",
            name="ck_ai_generation_event_thought_tokens",
        ),
        sa.CheckConstraint(
            "tool_tokens IS NULL OR tool_tokens >= 0",
            name="ck_ai_generation_event_tool_tokens",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["label_id"],
            ["label.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_generation_events_user_created",
        "ai_generation_events",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_ai_generation_events_status_created",
        "ai_generation_events",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_ai_generation_events_label_created",
        "ai_generation_events",
        ["label_id", "created_at"],
    )

    op.create_table(
        "ai_generation_calls",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("generation_event_id", sa.Integer(), nullable=False),
        sa.Column("learning_item_id", sa.Integer(), nullable=True),
        sa.Column("source_identifier", sa.String(64), nullable=False),
        sa.Column("call_order", sa.Integer(), nullable=False),
        sa.Column("allocated_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("valid_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "persisted_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "duplicate_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "rejected_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("excess_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("cached_tokens", sa.Integer(), nullable=True),
        sa.Column("thought_tokens", sa.Integer(), nullable=True),
        sa.Column("tool_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_input_tokens", sa.Integer(), nullable=True),
        sa.Column(
            "input_token_count_estimated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("response_id", sa.String(255), nullable=True),
        sa.Column("safe_error_code", sa.String(80), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(), nullable=True),
        sa.CheckConstraint(
            "call_order >= 1",
            name="ck_ai_generation_call_order",
        ),
        sa.CheckConstraint(
            "allocated_count > 0",
            name="ck_ai_generation_call_allocated_count",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'PARTIAL', 'FAILED')",
            name="ck_ai_generation_call_status",
        ),
        sa.CheckConstraint(
            "valid_count >= 0 AND persisted_count >= 0 "
            "AND duplicate_count >= 0 AND rejected_count >= 0 "
            "AND excess_count >= 0",
            name="ck_ai_generation_call_counts",
        ),
        sa.CheckConstraint(
            "valid_count <= allocated_count "
            "AND persisted_count <= valid_count "
            "AND duplicate_count <= valid_count "
            "AND valid_count + rejected_count <= allocated_count",
            name="ck_ai_generation_call_count_bounds",
        ),
        sa.CheckConstraint(
            "(input_tokens IS NULL OR input_tokens >= 0) "
            "AND (output_tokens IS NULL OR output_tokens >= 0) "
            "AND (total_tokens IS NULL OR total_tokens >= 0) "
            "AND (cached_tokens IS NULL OR cached_tokens >= 0) "
            "AND (thought_tokens IS NULL OR thought_tokens >= 0) "
            "AND (tool_tokens IS NULL OR tool_tokens >= 0) "
            "AND (estimated_input_tokens IS NULL OR estimated_input_tokens >= 0)",
            name="ck_ai_generation_call_tokens",
        ),
        sa.ForeignKeyConstraint(
            ["generation_event_id"],
            ["ai_generation_events.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["learning_item_id"],
            ["learning_item.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "generation_event_id",
            "call_order",
            name="uq_ai_generation_call_order",
        ),
    )
    op.create_index(
        "ix_ai_generation_calls_item_created",
        "ai_generation_calls",
        ["learning_item_id", "created_at"],
    )

    op.add_column(
        "questions",
        sa.Column("content_fingerprint", sa.String(64), nullable=True),
    )
    op.add_column(
        "questions",
        sa.Column("generation_event_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_questions_generation_event",
        "questions",
        "ai_generation_events",
        ["generation_event_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "uq_questions_learning_item_fingerprint",
        "questions",
        ["learning_item_id", "content_fingerprint"],
        unique=True,
        postgresql_where=sa.text("content_fingerprint IS NOT NULL"),
    )
    op.create_index(
        "ix_questions_generation_event_id",
        "questions",
        ["generation_event_id"],
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM ai_generation_events)
               OR EXISTS (
                    SELECT 1
                    FROM questions
                    WHERE content_fingerprint IS NOT NULL
                       OR generation_event_id IS NOT NULL
               )
            THEN
                RAISE EXCEPTION
                    'downgrade refused: Phase 2A operational history exists';
            END IF;
        END $$
        """
    )

    op.drop_index(
        "ix_questions_generation_event_id",
        table_name="questions",
    )
    op.drop_index(
        "uq_questions_learning_item_fingerprint",
        table_name="questions",
    )
    op.drop_constraint(
        "fk_questions_generation_event",
        "questions",
        type_="foreignkey",
    )
    op.drop_column("questions", "generation_event_id")
    op.drop_column("questions", "content_fingerprint")

    op.drop_index(
        "ix_ai_generation_calls_item_created",
        table_name="ai_generation_calls",
    )
    op.drop_table("ai_generation_calls")

    op.drop_index(
        "ix_ai_generation_events_label_created",
        table_name="ai_generation_events",
    )
    op.drop_index(
        "ix_ai_generation_events_status_created",
        table_name="ai_generation_events",
    )
    op.drop_index(
        "ix_ai_generation_events_user_created",
        table_name="ai_generation_events",
    )
    op.drop_table("ai_generation_events")
