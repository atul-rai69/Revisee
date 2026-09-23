"""Add encrypted user-owned AI credentials and recorded usage.

Revision ID: 20260915_0008
Revises: 20260914_0007
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260915_0008"
down_revision: str | None = "20260914_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_ai_generation_event_operation",
        "ai_generation_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_ai_generation_event_operation",
        "ai_generation_events",
        "operation_type IN ("
        "'LEARNING_ITEM_CREATE', 'LEARNING_ITEM_REGENERATE', "
        "'LEARNING_ITEM_QUESTIONS', 'SESSION_SHORTAGE', 'LABEL_PROACTIVE')",
    )
    op.create_table(
        "ai_credentials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("encrypted_secret", sa.LargeBinary(), nullable=False),
        sa.Column("encryption_nonce", sa.LargeBinary(), nullable=False),
        sa.Column("encryption_key_version", sa.String(length=40), nullable=False),
        sa.Column("key_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("key_hint", sa.String(length=4), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("last_validated_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("last_used_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("provider IN ('GEMINI')", name="ck_ai_credential_provider"),
        sa.CheckConstraint("status IN ('VALID', 'INVALID')", name="ck_ai_credential_status"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "provider", "name", name="uq_ai_credential_name"),
        sa.UniqueConstraint(
            "user_id",
            "provider",
            "key_fingerprint",
            name="uq_ai_credential_fingerprint",
        ),
    )
    op.create_index(
        "ix_ai_credentials_user_provider",
        "ai_credentials",
        ["user_id", "provider"],
    )
    op.create_index(
        "uq_ai_credentials_default",
        "ai_credentials",
        ["user_id", "provider"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )
    op.create_table(
        "ai_credential_usage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("credential_id", sa.Integer(), nullable=False),
        sa.Column("operation_type", sa.String(length=40), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("provider IN ('GEMINI')", name="ck_ai_credential_usage_provider"),
        sa.CheckConstraint(
            "(input_tokens IS NULL OR input_tokens >= 0) AND "
            "(output_tokens IS NULL OR output_tokens >= 0) AND "
            "(total_tokens IS NULL OR total_tokens >= 0)",
            name="ck_ai_credential_usage_tokens",
        ),
        sa.ForeignKeyConstraint(
            ["credential_id"], ["ai_credentials.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_credential_usage_user_credential_time",
        "ai_credential_usage",
        ["user_id", "credential_id", "created_at"],
    )
    op.add_column(
        "ai_generation_events",
        sa.Column("credential_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_ai_generation_events_credential_id",
        "ai_generation_events",
        "ai_credentials",
        ["credential_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_ai_generation_events_credential_created",
        "ai_generation_events",
        ["credential_id", "created_at"],
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM ai_credentials)
               OR EXISTS (
                    SELECT 1 FROM ai_generation_events
                    WHERE operation_type = 'LEARNING_ITEM_QUESTIONS'
               ) THEN
                RAISE EXCEPTION
                    'downgrade refused: BYOK data or question-generation history would be lost';
            END IF;
        END $$;
        """
    )
    op.drop_index(
        "ix_ai_generation_events_credential_created",
        table_name="ai_generation_events",
    )
    op.drop_constraint(
        "fk_ai_generation_events_credential_id",
        "ai_generation_events",
        type_="foreignkey",
    )
    op.drop_column("ai_generation_events", "credential_id")
    op.drop_index(
        "ix_ai_credential_usage_user_credential_time",
        table_name="ai_credential_usage",
    )
    op.drop_table("ai_credential_usage")
    op.drop_index("uq_ai_credentials_default", table_name="ai_credentials")
    op.drop_index("ix_ai_credentials_user_provider", table_name="ai_credentials")
    op.drop_table("ai_credentials")
    op.drop_constraint(
        "ck_ai_generation_event_operation",
        "ai_generation_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_ai_generation_event_operation",
        "ai_generation_events",
        "operation_type IN ("
        "'LEARNING_ITEM_CREATE', 'LEARNING_ITEM_REGENERATE', "
        "'SESSION_SHORTAGE', 'LABEL_PROACTIVE')",
    )
