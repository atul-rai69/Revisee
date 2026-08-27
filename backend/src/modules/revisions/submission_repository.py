from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Numeric, cast, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.modules.labels.models import Label
from src.modules.learning_items.models import LearningItem, LearningItemLabel
from src.modules.revisions.models import (
    Question,
    QuestionStatistics,
    RevisionSession,
    RevisionSessionLabel,
    RevisionSessionQuestion,
    UserAttempt,
)


@dataclass(frozen=True, slots=True)
class QuestionStatisticsUpdate:
    total_attempt_count: int
    correct_attempt_count: int
    total_time_seconds: int


def find_owned_session_for_update(
    db: Session,
    session_id: int,
    user_id: int,
) -> RevisionSession | None:
    return (
        db.query(RevisionSession)
        .filter(
            RevisionSession.id == session_id,
            RevisionSession.user_id == user_id,
        )
        .with_for_update()
        .first()
    )


def find_owned_session(
    db: Session,
    session_id: int,
    user_id: int,
) -> RevisionSession | None:
    return (
        db.query(RevisionSession)
        .filter(
            RevisionSession.id == session_id,
            RevisionSession.user_id == user_id,
        )
        .first()
    )


def list_session_questions(
    db: Session,
    session_id: int,
) -> list[RevisionSessionQuestion]:
    return (
        db.query(RevisionSessionQuestion)
        .filter(RevisionSessionQuestion.session_id == session_id)
        .order_by(RevisionSessionQuestion.question_order)
        .all()
    )


def list_session_labels(
    db: Session,
    session_id: int,
) -> list[RevisionSessionLabel]:
    return (
        db.query(RevisionSessionLabel)
        .filter(RevisionSessionLabel.session_id == session_id)
        .order_by(RevisionSessionLabel.label_order)
        .all()
    )


def list_session_attempts(
    db: Session,
    session_id: int,
    user_id: int,
) -> list[UserAttempt]:
    return (
        db.query(UserAttempt)
        .filter(
            UserAttempt.session_id == session_id,
            UserAttempt.user_id == user_id,
        )
        .order_by(UserAttempt.session_question_id)
        .all()
    )


def lock_owned_learning_items(
    db: Session,
    user_id: int,
    item_ids: Sequence[int],
) -> dict[int, LearningItem]:
    if not item_ids:
        return {}
    rows = (
        db.query(LearningItem)
        .filter(
            LearningItem.user_id == user_id,
            LearningItem.id.in_(item_ids),
        )
        .order_by(LearningItem.id)
        .with_for_update()
        .all()
    )
    return {row.id: row for row in rows}


def lock_owned_questions(
    db: Session,
    user_id: int,
    question_ids: Sequence[int],
) -> dict[int, Question]:
    if not question_ids:
        return {}
    rows = (
        db.query(Question)
        .join(LearningItem, LearningItem.id == Question.learning_item_id)
        .filter(
            LearningItem.user_id == user_id,
            Question.id.in_(question_ids),
        )
        .order_by(Question.id)
        .with_for_update(of=Question)
        .all()
    )
    return {row.id: row for row in rows}


def lock_current_labels_by_item(
    db: Session,
    user_id: int,
    item_ids: Sequence[int],
) -> dict[int, tuple[int, ...]]:
    if not item_ids:
        return {}
    rows = (
        db.query(LearningItemLabel.learning_item_id, Label)
        .join(Label, Label.id == LearningItemLabel.label_id)
        .filter(
            Label.user_id == user_id,
            LearningItemLabel.learning_item_id.in_(item_ids),
        )
        .order_by(Label.id, LearningItemLabel.learning_item_id)
        .with_for_update(of=(LearningItemLabel, Label))
        .all()
    )
    labels_by_item: dict[int, list[int]] = {item_id: [] for item_id in item_ids}
    for item_id, label in rows:
        labels_by_item.setdefault(item_id, []).append(label.id)
    return {
        item_id: tuple(label_ids)
        for item_id, label_ids in labels_by_item.items()
    }


def add_attempts(db: Session, attempts: Sequence[UserAttempt]) -> None:
    db.add_all(list(attempts))


def upsert_question_statistics(
    db: Session,
    updates: Mapping[int, QuestionStatisticsUpdate],
    attempted_at: datetime,
) -> None:
    for question_id in sorted(updates):
        update = updates[question_id]
        statement = insert(QuestionStatistics).values(
            question_id=question_id,
            total_attempt_count=update.total_attempt_count,
            correct_attempt_count=update.correct_attempt_count,
            total_time_seconds=update.total_time_seconds,
            average_time_seconds=Decimal(update.total_time_seconds)
            / Decimal(update.total_attempt_count),
            last_attempted_at=attempted_at,
        )
        excluded = statement.excluded
        new_total_count = (
            QuestionStatistics.total_attempt_count + excluded.total_attempt_count
        )
        new_total_time = (
            QuestionStatistics.total_time_seconds + excluded.total_time_seconds
        )
        db.execute(
            statement.on_conflict_do_update(
                index_elements=[QuestionStatistics.question_id],
                set_={
                    "total_attempt_count": new_total_count,
                    "correct_attempt_count": (
                        QuestionStatistics.correct_attempt_count
                        + excluded.correct_attempt_count
                    ),
                    "total_time_seconds": new_total_time,
                    "average_time_seconds": cast(new_total_time, Numeric(20, 2))
                    / new_total_count,
                    "last_attempted_at": func.greatest(
                        QuestionStatistics.last_attempted_at,
                        excluded.last_attempted_at,
                    ),
                },
            )
        )


def flush(db: Session) -> None:
    db.flush()
