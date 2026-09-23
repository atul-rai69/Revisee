from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import and_, case, func, or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.modules.mastery.models import MasteryHistory, UserLabelMastery, UserLearningItemMastery
from src.modules.labels.models import Label
from src.modules.learning_items.models import LearningItem, LearningItemLabel
from src.modules.revisions.models import (
    Question,
    RevisionSession,
    RevisionSessionQuestion,
    UserAttempt,
)
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


@dataclass(frozen=True, slots=True)
class MasteryAnalyticsRow:
    entity_id: int
    display_name: str
    question_count: int
    mastery_score: Decimal | None
    total_attempts: int
    correct_attempts: int
    last_attempted_at: datetime | None
    next_review_at: datetime | None


@dataclass(frozen=True, slots=True)
class RevisionActivityRow:
    activity_date: date
    completed_session_count: int
    answered_count: int
    correct_count: int


@dataclass(frozen=True, slots=True)
class TopicPracticeRow:
    topic_id: int
    topic_name: str
    attempt_count: int
    correct_count: int
    session_count: int


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


def add_mastery_history(db: Session, rows: Sequence[MasteryHistory]) -> None:
    if rows:
        db.add_all(rows)


def list_owned_mastery_analytics(
    db: Session,
    *,
    user_id: int,
    entity_type: str,
    limit: int,
    offset: int,
) -> tuple[list[MasteryAnalyticsRow], int]:
    if entity_type == "LEARNING_ITEM":
        total = db.query(func.count(LearningItem.id)).filter(
            LearningItem.user_id == user_id
        ).scalar() or 0
        rows = (
            db.query(
                LearningItem.id.label("entity_id"),
                LearningItem.title.label("display_name"),
                func.count(func.distinct(Question.id)).label("question_count"),
                UserLearningItemMastery.mastery_score,
                UserLearningItemMastery.total_attempts,
                UserLearningItemMastery.correct_attempts,
                UserLearningItemMastery.last_attempt_at,
                UserLearningItemMastery.next_review_at,
            )
            .outerjoin(Question, Question.learning_item_id == LearningItem.id)
            .outerjoin(
                UserLearningItemMastery,
                and_(
                    UserLearningItemMastery.learning_item_id == LearningItem.id,
                    UserLearningItemMastery.user_id == user_id,
                ),
            )
            .filter(LearningItem.user_id == user_id)
            .group_by(LearningItem.id, UserLearningItemMastery.id)
            .order_by(
                UserLearningItemMastery.last_attempt_at.desc().nullslast(),
                LearningItem.id.desc(),
            )
            .offset(offset).limit(limit).all()
        )
    else:
        total = db.query(func.count(Label.id)).filter(Label.user_id == user_id).scalar() or 0
        rows = (
            db.query(
                Label.id.label("entity_id"),
                Label.label_name.label("display_name"),
                func.count(func.distinct(Question.id)).label("question_count"),
                UserLabelMastery.mastery_score,
                UserLabelMastery.total_attempts,
                UserLabelMastery.correct_attempts,
                UserLabelMastery.last_attempt_at,
                UserLabelMastery.next_review_at,
            )
            .outerjoin(LearningItemLabel, LearningItemLabel.label_id == Label.id)
            .outerjoin(Question, Question.learning_item_id == LearningItemLabel.learning_item_id)
            .outerjoin(
                UserLabelMastery,
                and_(
                    UserLabelMastery.label_id == Label.id,
                    UserLabelMastery.user_id == user_id,
                ),
            )
            .filter(Label.user_id == user_id)
            .group_by(Label.id, UserLabelMastery.id)
            .order_by(
                UserLabelMastery.last_attempt_at.desc().nullslast(), Label.id.desc()
            )
            .offset(offset).limit(limit).all()
        )
    return ([
        MasteryAnalyticsRow(
            entity_id=row.entity_id,
            display_name=row.display_name,
            question_count=int(row.question_count or 0),
            mastery_score=Decimal(row.mastery_score) if row.mastery_score is not None else None,
            total_attempts=int(row.total_attempts or 0),
            correct_attempts=int(row.correct_attempts or 0),
            last_attempted_at=row.last_attempt_at,
            next_review_at=row.next_review_at,
        ) for row in rows
    ], int(total))


def list_mastery_history(
    db: Session,
    *,
    user_id: int,
    entity_type: str,
    entity_ids: Sequence[int],
) -> dict[int, list[MasteryHistory]]:
    if not entity_ids:
        return {}
    rows = (
        db.query(MasteryHistory)
        .filter(
            MasteryHistory.user_id == user_id,
            MasteryHistory.entity_type == entity_type,
            MasteryHistory.entity_id.in_(entity_ids),
        )
        .order_by(MasteryHistory.recorded_at, MasteryHistory.id)
        .all()
    )
    result: dict[int, list[MasteryHistory]] = {entity_id: [] for entity_id in entity_ids}
    for row in rows:
        result[row.entity_id].append(row)
    return result


def list_owned_revision_activity(
    db: Session,
    *,
    user_id: int,
) -> tuple[list[RevisionActivityRow], int]:
    activity_date = func.date(RevisionSession.ended_at)
    rows = (
        db.query(
            activity_date.label("activity_date"),
            func.count(func.distinct(RevisionSession.id)).label("session_count"),
            func.count(UserAttempt.id).label("answered_count"),
            func.sum(case((UserAttempt.is_correct.is_(True), 1), else_=0)).label(
                "correct_count"
            ),
        )
        .join(
            UserAttempt,
            and_(
                UserAttempt.session_id == RevisionSession.id,
                UserAttempt.user_id == user_id,
            ),
        )
        .filter(
            RevisionSession.user_id == user_id,
            RevisionSession.status == "COMPLETED",
            RevisionSession.ended_at.is_not(None),
        )
        .group_by(activity_date)
        .order_by(activity_date)
        .all()
    )
    total = (
        db.query(func.count(RevisionSession.id))
        .filter(
            RevisionSession.user_id == user_id,
            RevisionSession.status == "COMPLETED",
        )
        .scalar()
        or 0
    )
    return (
        [
            RevisionActivityRow(
                activity_date=row.activity_date,
                completed_session_count=int(row.session_count or 0),
                answered_count=int(row.answered_count or 0),
                correct_count=int(row.correct_count or 0),
            )
            for row in rows
        ],
        int(total),
    )


def list_owned_topic_practice(
    db: Session,
    *,
    user_id: int,
    session_limit: int,
) -> tuple[list[TopicPracticeRow], int]:
    selected_session_ids = [
        row.id
        for row in (
            db.query(RevisionSession.id)
            .filter(
                RevisionSession.user_id == user_id,
                RevisionSession.status == "COMPLETED",
            )
            .order_by(RevisionSession.ended_at.desc(), RevisionSession.id.desc())
            .limit(session_limit)
            .all()
        )
    ]
    if not selected_session_ids:
        return [], 0

    rows = (
        db.query(
            Label.id.label("topic_id"),
            Label.label_name.label("topic_name"),
            func.count(UserAttempt.id).label("attempt_count"),
            func.sum(case((UserAttempt.is_correct.is_(True), 1), else_=0)).label(
                "correct_count"
            ),
            func.count(func.distinct(UserAttempt.session_id)).label("session_count"),
        )
        .join(LearningItemLabel, LearningItemLabel.label_id == Label.id)
        .join(
            RevisionSessionQuestion,
            RevisionSessionQuestion.learning_item_id
            == LearningItemLabel.learning_item_id,
        )
        .join(
            UserAttempt,
            and_(
                UserAttempt.session_question_id == RevisionSessionQuestion.id,
                UserAttempt.session_id == RevisionSessionQuestion.session_id,
            ),
        )
        .join(RevisionSession, RevisionSession.id == UserAttempt.session_id)
        .filter(
            Label.user_id == user_id,
            RevisionSession.user_id == user_id,
            RevisionSession.status == "COMPLETED",
            UserAttempt.user_id == user_id,
            UserAttempt.session_id.in_(selected_session_ids),
        )
        .group_by(Label.id, Label.label_name)
        .order_by(func.count(UserAttempt.id).desc(), Label.id)
        .all()
    )
    return (
        [
            TopicPracticeRow(
                topic_id=row.topic_id,
                topic_name=row.topic_name,
                attempt_count=int(row.attempt_count or 0),
                correct_count=int(row.correct_count or 0),
                session_count=int(row.session_count or 0),
            )
            for row in rows
        ],
        len(selected_session_ids),
    )


def count_owned_measured_learning_items(db: Session, *, user_id: int) -> int:
    return int(
        db.query(func.count(UserLearningItemMastery.id))
        .join(
            LearningItem,
            LearningItem.id == UserLearningItemMastery.learning_item_id,
        )
        .filter(
            UserLearningItemMastery.user_id == user_id,
            LearningItem.user_id == user_id,
            UserLearningItemMastery.total_attempts >= MINIMUM_ATTEMPTS,
        )
        .scalar()
        or 0
    )
