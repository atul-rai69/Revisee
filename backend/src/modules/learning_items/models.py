from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from src.db.base import Base


class LearningItem(Base):
    __tablename__ = "learning_item"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title = Column(String(100), nullable=False)
    description_text = Column(Text)
    theory = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )


class LearningItemKeyPoint(Base):
    __tablename__ = "learning_item_key_points"

    id = Column(Integer, primary_key=True)
    learning_item_id = Column(
        Integer,
        ForeignKey("learning_item.id", ondelete="CASCADE"),
        nullable=False,
    )
    key_point = Column(Text, nullable=False)


class LearningItemLabel(Base):
    __tablename__ = "learning_item_label"

    id = Column(Integer, primary_key=True, index=True)
    learning_item_id = Column(
        Integer,
        ForeignKey("learning_item.id", ondelete="CASCADE"),
        nullable=False,
    )
    label_id = Column(
        Integer,
        ForeignKey("label.id", ondelete="CASCADE"),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "learning_item_id",
            "label_id",
            name="uq_learning_item_label",
        ),
    )


class Media(Base):
    __tablename__ = "media"

    id = Column(Integer, primary_key=True, index=True)
    learning_item_id = Column(
        Integer,
        ForeignKey("learning_item.id", ondelete="CASCADE"),
        nullable=False,
    )
    type = Column(
        Enum("image", "video", "pdf", name="media_type_enum"),
        nullable=False,
    )
    url = Column(String(500), nullable=False)
    public_id = Column(String(300), nullable=False)
    original_filename = Column(String(255))


class PdfNote(Base):
    __tablename__ = "pdf_notes"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    learning_item_id = Column(
        Integer,
        ForeignKey("learning_item.id", ondelete="CASCADE"),
        nullable=False,
    )
    media_id = Column(
        Integer,
        ForeignKey("media.id", ondelete="CASCADE"),
        nullable=False,
    )
    page_number = Column(Integer, nullable=False)
    source_excerpt = Column(String(500))
    note_text = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint("page_number > 0", name="ck_pdf_note_page_positive"),
        CheckConstraint(
            "length(btrim(note_text)) BETWEEN 1 AND 4000",
            name="ck_pdf_note_text_length",
        ),
        CheckConstraint(
            "source_excerpt IS NULL OR length(source_excerpt) <= 500",
            name="ck_pdf_note_excerpt_length",
        ),
        Index(
            "ix_pdf_notes_user_item_updated",
            "user_id",
            "learning_item_id",
            "updated_at",
        ),
        Index("ix_pdf_notes_media_page", "media_id", "page_number"),
    )
