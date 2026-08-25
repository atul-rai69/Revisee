from collections.abc import Sequence

from sqlalchemy.orm import Session

from src.modules.labels.models import Label
from src.modules.learning_items.models import (
    LearningItem,
    LearningItemKeyPoint,
    LearningItemLabel,
    Media,
)
from src.modules.revisions.models import Question


def find_owned(db: Session, item_id: int, user_id: int) -> LearningItem | None:
    return db.query(LearningItem).filter(
        LearningItem.id == item_id,
        LearningItem.user_id == user_id,
    ).first()


def add(db: Session, learning_item: LearningItem) -> None:
    db.add(learning_item)


def add_label_relations(
    db: Session,
    learning_item_id: int,
    label_ids: Sequence[int],
) -> None:
    for label_id in label_ids:
        db.add(
            LearningItemLabel(
                learning_item_id=learning_item_id,
                label_id=label_id,
            )
        )


def add_media(
    db: Session,
    learning_item_id: int,
    media_type: str,
    url: str,
    public_id: str,
) -> None:
    db.add(
        Media(
            learning_item_id=learning_item_id,
            type=media_type,
            url=url,
            public_id=public_id,
        )
    )


def list_label_names(db: Session, item_id: int) -> list[str]:
    rows = (
        db.query(Label.label_name)
        .join(LearningItemLabel, LearningItemLabel.label_id == Label.id)
        .filter(LearningItemLabel.learning_item_id == item_id)
        .order_by(Label.id)
        .all()
    )
    return [row.label_name for row in rows]


def list_media(db: Session, item_id: int) -> list[Media]:
    return (
        db.query(Media)
        .filter(Media.learning_item_id == item_id)
        .order_by(Media.id)
        .all()
    )


def list_key_points(db: Session, item_id: int) -> list[str]:
    rows = (
        db.query(LearningItemKeyPoint.key_point)
        .filter(LearningItemKeyPoint.learning_item_id == item_id)
        .order_by(LearningItemKeyPoint.id)
        .all()
    )
    return [row.key_point for row in rows]


def list_questions(db: Session, item_id: int) -> list[Question]:
    return (
        db.query(Question)
        .filter(Question.learning_item_id == item_id)
        .order_by(Question.id)
        .all()
    )


def delete_owned(db: Session, learning_item: LearningItem) -> None:
    db.query(LearningItemKeyPoint).filter(
        LearningItemKeyPoint.learning_item_id == learning_item.id
    ).delete(synchronize_session=False)
    db.delete(learning_item)
