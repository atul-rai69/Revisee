from collections.abc import Sequence

from sqlalchemy.orm import Session

from src.modules.labels.models import Label


def list_for_user(db: Session, user_id: int) -> list[Label]:
    return db.query(Label).filter(Label.user_id == user_id).all()


def find_owned(db: Session, label_id: int, user_id: int) -> Label | None:
    return db.query(Label).filter(
        Label.id == label_id,
        Label.user_id == user_id,
    ).first()


def owned_ids(db: Session, label_ids: Sequence[int], user_id: int) -> set[int]:
    if not label_ids:
        return set()
    rows = db.query(Label.id).filter(
        Label.id.in_(label_ids),
        Label.user_id == user_id,
    ).all()
    return {row.id for row in rows}


def add(db: Session, label: Label) -> None:
    db.add(label)
