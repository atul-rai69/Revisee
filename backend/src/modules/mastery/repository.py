from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import and_, case, func, or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.modules.mastery.models import UserLabelMastery, UserLearningItemMastery
from src.modules.labels.models import Label
from src.modules.learning_items.models import LearningItem
from src.modules.mastery.weak_areas import MINIMUM_ATTEMPTS, WEAK_MASTERY_BELOW


@dataclass(frozen=True, slots=True)
class WeakAreaRow:
    entity_id: int
    display_name: str
    has_mastery_record: bool
    mastery_score: Decimal | None
    total_attempts: int
    correct_attempts: int
    last_attempted_at: datetime | None
    last_reviewed_at: datetime | None
    next_review_at: datetime | None


def list_owned_weak_areas(
    db: Session,
    *,
    user_id: int,
    entity_type: str,
    classification: str,
    as_of: datetime,
    limit: int,
    offset: int,
) -> tuple[list[WeakAreaRow], int]:
    if entity_type == "LEARNING_ITEM":
        entity = LearningItem
        mastery = UserLearningItemMastery
        entity_key = LearningItem.id
        display_name = LearningItem.title
        join_condition = and_(
            mastery.learning_item_id == LearningItem.id,
            mastery.user_id == user_id,
        )
    else:
        entity = Label
        mastery = UserLabelMastery
        entity_key = Label.id
        display_name = Label.label_name
        join_condition = and_(
            mastery.label_id == Label.id,
            mastery.user_id == user_id,
        )

    due = and_(mastery.next_review_at.is_not(None), mastery.next_review_at <= as_of)
    insufficient = or_(
        mastery.id.is_(None),
        mastery.total_attempts < MINIMUM_ATTEMPTS,
    )
    weak = and_(
        mastery.id.is_not(None),
        mastery.total_attempts >= MINIMUM_ATTEMPTS,
        mastery.mastery_score < WEAK_MASTERY_BELOW,
    )
    due_review = and_(
        mastery.id.is_not(None),
        mastery.total_attempts >= MINIMUM_ATTEMPTS,
        mastery.mastery_score >= WEAK_MASTERY_BELOW,
        due,
    )
    predicates = {
        "INSUFFICIENT_EVIDENCE": insufficient,
        "DEMONSTRATED_WEAKNESS": weak,
        "DUE_REVIEW": due_review,
    }

    query = (
        db.query(
            entity_key.label("entity_id"),
            display_name.label("display_name"),
            mastery.id.label("mastery_id"),
            mastery.mastery_score,
            mastery.total_attempts,
            mastery.correct_attempts,
            mastery.last_attempt_at,
            mastery.last_reviewed_at,
            mastery.next_review_at,
        )
        .outerjoin(mastery, join_condition)
        .filter(entity.user_id == user_id, predicates[classification])
    )
    total = query.with_entities(func.count(entity_key)).order_by(None).scalar() or 0

    if classification == "DEMONSTRATED_WEAKNESS":
        ordering = (
            mastery.mastery_score.asc(),
            case((due, 1), else_=0).desc(),
            mastery.next_review_at.asc().nullslast(),
            mastery.total_attempts.desc(),
            entity_key.asc(),
        )
    elif classification == "DUE_REVIEW":
        ordering = (
            mastery.next_review_at.asc(),
            mastery.mastery_score.asc(),
            mastery.total_attempts.desc(),
            entity_key.asc(),
        )
    else:
        ordering = (
            func.coalesce(mastery.total_attempts, 0).desc(),
            mastery.last_attempt_at.asc().nullsfirst(),
            entity_key.asc(),
        )

    rows = query.order_by(*ordering).offset(offset).limit(limit).all()
    return (
        [
            WeakAreaRow(
                entity_id=row.entity_id,
                display_name=row.display_name,
                has_mastery_record=row.mastery_id is not None,
                mastery_score=(
                    Decimal(row.mastery_score)
                    if row.mastery_score is not None
                    else None
                ),
                total_attempts=row.total_attempts or 0,
                correct_attempts=row.correct_attempts or 0,
                last_attempted_at=row.last_attempt_at,
                last_reviewed_at=row.last_reviewed_at,
                next_review_at=row.next_review_at,
            )
            for row in rows
        ],
        total,
    )


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
