"""Preserve original filenames for uploaded media.

Revision ID: 20260920_0010
Revises: 20260920_0009
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260920_0010"
down_revision: str | None = "20260920_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "media",
        sa.Column("original_filename", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM media WHERE original_filename IS NOT NULL
            ) THEN
                RAISE EXCEPTION
                    'downgrade refused: original media filenames would be lost';
            END IF;
        END $$;
        """
    )
    op.drop_column("media", "original_filename")
