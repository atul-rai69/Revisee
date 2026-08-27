from collections.abc import Sequence

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.modules.mastery.models import UserLabelMastery, UserLearningItemMastery


def materialize_item_mastery(
    db: Session,
    user_id: int,
    learning_item_ids: Sequence[int],
) -> None:
    if not learning_item_ids:
        return
    statement = insert(UserLearningItemMastery).values(
        [
            {
                "user_id": user_id,
                "learning_item_id": item_id,
                "mastery_score": 50,
                "total_attempts": 0,
                "correct_attempts": 0,
            }
            for item_id in sorted(set(learning_item_ids))
        ]
    )
    db.execute(
        statement.on_conflict_do_nothing(
            constraint="uq_user_learning_item_mastery"
        )
    )


def materialize_label_mastery(
    db: Session,
    user_id: int,
    label_ids: Sequence[int],
) -> None:
    if not label_ids:
        return
    statement = insert(UserLabelMastery).values(
        [
            {
                "user_id": user_id,
                "label_id": label_id,
                "mastery_score": 50,
                "total_attempts": 0,
                "correct_attempts": 0,
            }
            for label_id in sorted(set(label_ids))
        ]
    )
    db.execute(
        statement.on_conflict_do_nothing(constraint="uq_user_label_mastery")
    )


def lock_item_mastery(
    db: Session,
    user_id: int,
    learning_item_ids: Sequence[int],
) -> list[UserLearningItemMastery]:
    if not learning_item_ids:
        return []
    return (
        db.query(UserLearningItemMastery)
        .filter(
            UserLearningItemMastery.user_id == user_id,
            UserLearningItemMastery.learning_item_id.in_(learning_item_ids),
        )
        .order_by(UserLearningItemMastery.learning_item_id)
        .with_for_update()
        .all()
    )


def lock_label_mastery(
    db: Session,
    user_id: int,
    label_ids: Sequence[int],
) -> list[UserLabelMastery]:
    if not label_ids:
        return []
    return (
        db.query(UserLabelMastery)
        .filter(
            UserLabelMastery.user_id == user_id,
            UserLabelMastery.label_id.in_(label_ids),
        )
        .order_by(UserLabelMastery.label_id)
        .with_for_update()
        .all()
    )
