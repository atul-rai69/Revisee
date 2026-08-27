"""Allow SMART revision-session strategies.

Revision ID: 20260827_0005
Revises: 20260826_0004
"""
from collections.abc import Sequence

from alembic import op


revision: str = "20260827_0005"
down_revision: str | None = "20260826_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_revision_session_requested_strategy",
        "revision_sessions",
        type_="check",
    )
    op.drop_constraint(
        "ck_revision_session_strategy_used",
        "revision_sessions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_revision_session_requested_strategy",
        "revision_sessions",
        "requested_strategy IN ('RANDOM', 'LABEL', 'SMART')",
    )
    op.create_check_constraint(
        "ck_revision_session_strategy_used",
        "revision_sessions",
        "strategy_used IN ('RANDOM', 'LABEL', 'SMART')",
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM revision_sessions
                WHERE requested_strategy = 'SMART'
                   OR strategy_used = 'SMART'
            ) THEN
                RAISE EXCEPTION
                    'downgrade refused: SMART revision-session history exists';
            END IF;
        END $$
        """
    )
    op.drop_constraint(
        "ck_revision_session_requested_strategy",
        "revision_sessions",
        type_="check",
    )
    op.drop_constraint(
        "ck_revision_session_strategy_used",
        "revision_sessions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_revision_session_requested_strategy",
        "revision_sessions",
        "requested_strategy IN ('RANDOM', 'LABEL')",
    )
    op.create_check_constraint(
        "ck_revision_session_strategy_used",
        "revision_sessions",
        "strategy_used IN ('RANDOM', 'LABEL')",
    )
