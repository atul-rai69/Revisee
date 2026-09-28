"""Replace legacy access sessions with rotating refresh-token sessions.

Revision ID: 20260927_0011
Revises: 20260920_0010

Existing user_sessions rows are intentionally removed. They contain legacy
access-session identifiers rather than refresh-token hashes, so preserving
them would be unsafe and incompatible. Users must sign in once after rollout.
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260927_0011"
down_revision: str | None = "20260920_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM user_sessions")
    op.drop_constraint("user_sessions_user_id_fkey", "user_sessions", type_="foreignkey")
    op.drop_constraint("user_sessions_session_id_key", "user_sessions", type_="unique")
    op.drop_column("user_sessions", "session_id")
    op.drop_column("user_sessions", "is_active")

    op.add_column("user_sessions", sa.Column("token_hash", sa.String(64), nullable=False))
    op.add_column("user_sessions", sa.Column("family_id", sa.String(36), nullable=False))
    op.add_column("user_sessions", sa.Column("parent_session_id", sa.Integer(), nullable=True))
    op.add_column(
        "user_sessions",
        sa.Column("issued_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )
    op.add_column(
        "user_sessions",
        sa.Column(
            "absolute_expires_at", sa.TIMESTAMP(timezone=True), nullable=False
        ),
    )
    op.add_column(
        "user_sessions",
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "user_sessions",
        sa.Column("replaced_by_session_id", sa.Integer(), nullable=True),
    )
    op.add_column("user_sessions", sa.Column("user_agent", sa.String(255), nullable=True))
    for column_name in ("expires_at", "last_used_at", "created_at"):
        op.alter_column(
            "user_sessions",
            column_name,
            existing_type=sa.TIMESTAMP(timezone=False),
            type_=sa.TIMESTAMP(timezone=True),
            nullable=False,
        )

    op.create_unique_constraint("uq_user_sessions_token_hash", "user_sessions", ["token_hash"])
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_family_id", "user_sessions", ["family_id"])
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"])
    op.create_foreign_key(
        "fk_user_sessions_user_id",
        "user_sessions",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_user_sessions_parent_session_id",
        "user_sessions",
        "user_sessions",
        ["parent_session_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_user_sessions_replaced_by_session_id",
        "user_sessions",
        "user_sessions",
        ["replaced_by_session_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.execute("DELETE FROM user_sessions")
    op.drop_constraint(
        "fk_user_sessions_replaced_by_session_id", "user_sessions", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_user_sessions_parent_session_id", "user_sessions", type_="foreignkey"
    )
    op.drop_constraint("fk_user_sessions_user_id", "user_sessions", type_="foreignkey")
    op.drop_index("ix_user_sessions_expires_at", table_name="user_sessions")
    op.drop_index("ix_user_sessions_family_id", table_name="user_sessions")
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_constraint("uq_user_sessions_token_hash", "user_sessions", type_="unique")

    op.drop_column("user_sessions", "user_agent")
    op.drop_column("user_sessions", "replaced_by_session_id")
    op.drop_column("user_sessions", "revoked_at")
    op.drop_column("user_sessions", "absolute_expires_at")
    op.drop_column("user_sessions", "issued_at")
    op.drop_column("user_sessions", "parent_session_id")
    op.drop_column("user_sessions", "family_id")
    op.drop_column("user_sessions", "token_hash")

    op.add_column(
        "user_sessions",
        sa.Column("session_id", sa.String(255), nullable=False),
    )
    op.add_column(
        "user_sessions",
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true()),
    )
    op.create_unique_constraint(
        "user_sessions_session_id_key", "user_sessions", ["session_id"]
    )
    op.create_foreign_key(
        "user_sessions_user_id_fkey",
        "user_sessions",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    for column_name in ("expires_at", "last_used_at", "created_at"):
        op.alter_column(
            "user_sessions",
            column_name,
            existing_type=sa.TIMESTAMP(timezone=True),
            type_=sa.TIMESTAMP(timezone=False),
            nullable=True,
        )
