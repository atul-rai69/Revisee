"""Add user-owned PDF page notes.

Revision ID: 20260920_0009
Revises: 20260915_0008
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260920_0009"
down_revision: str | None = "20260915_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pdf_notes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("learning_item_id", sa.Integer(), nullable=False),
        sa.Column("media_id", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("source_excerpt", sa.String(length=500), nullable=True),
        sa.Column("note_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("page_number > 0", name="ck_pdf_note_page_positive"),
        sa.CheckConstraint(
            "length(btrim(note_text)) BETWEEN 1 AND 4000",
            name="ck_pdf_note_text_length",
        ),
        sa.CheckConstraint(
            "source_excerpt IS NULL OR length(source_excerpt) <= 500",
            name="ck_pdf_note_excerpt_length",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["learning_item_id"], ["learning_item.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["media_id"], ["media.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pdf_notes_user_item_updated",
        "pdf_notes",
        ["user_id", "learning_item_id", "updated_at"],
    )
    op.create_index(
        "ix_pdf_notes_media_page",
        "pdf_notes",
        ["media_id", "page_number"],
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pdf_notes) THEN
                RAISE EXCEPTION
                    'downgrade refused: personal PDF notes would be lost';
            END IF;
        END $$;
        """
    )
    op.drop_index("ix_pdf_notes_media_page", table_name="pdf_notes")
    op.drop_index("ix_pdf_notes_user_item_updated", table_name="pdf_notes")
    op.drop_table("pdf_notes")
