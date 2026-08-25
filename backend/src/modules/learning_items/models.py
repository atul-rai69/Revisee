from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
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
    learning_item_id = Column(Integer, ForeignKey("learning_item.id"))
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
