from sqlalchemy import Column, ForeignKey, Integer, String

from src.db.base import Base


class Label(Base):
    __tablename__ = "label"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    label_name = Column(String(200), nullable=False)
