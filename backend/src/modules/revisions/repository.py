from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from sqlalchemy import and_, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.modules.labels.models import Label
from src.modules.learning_items.models import LearningItem, LearningItemKeyPoint
from src.modules.learning_items.models import LearningItemLabel
from src.modules.revisions.models import (
    Question,
    RevisionSession,
    RevisionSessionLabel,
    RevisionSessionQuestion,
)
from src.modules.revisions.schemas import GeneratedRevisionResponse
from src.modules.revisions.selection import QuestionCandidate
from src.modules.revisions.smart_selection import SmartQuestionCandidate
from src.modules.mastery.models import UserLearningItemMastery


@dataclass(frozen=True, slots=True)
class QuestionFingerprintInput:
    question_text: str
    options: tuple[str, str, str, str]
    stored_fingerprint: str | None


def eligible_question_filters():
    return (
        func.length(func.trim(Question.question_text)) > 0,
        func.length(func.trim(Question.option_a)) > 0,
        func.length(func.trim(Question.option_b)) > 0,
        func.length(func.trim(Question.option_c)) > 0,
        func.length(func.trim(Question.option_d)) > 0,
        Question.correct_option.in_(("0", "1", "2", "3", "A", "B", "C", "D")),
        Question.difficulty.between(1, 3),
        Question.expected_time_seconds > 0,
    )


def add_generated_content(
    db: Session,
    learning_item: LearningItem,
    content: GeneratedRevisionResponse,
) -> None:
    learning_item.theory = content.theory

    for point in content.key_points:
        db.add(
            LearningItemKeyPoint(
                learning_item_id=learning_item.id,
                key_point=point,
            )
        )

    for generated in content.questions:
        db.add(
            Question(
                learning_item_id=learning_item.id,
                question_text=generated.question,
                option_a=generated.options[0],
                option_b=generated.options[1],
                option_c=generated.options[2],
                option_d=generated.options[3],
                correct_option=generated.correct_answer,
                explanation=generated.explanation,
                difficulty=generated.difficulty_level,
                expected_time_seconds=generated.expected_time,
                source="future-ai",
            )
        )


def list_question_fingerprint_inputs(
    db: Session,
    learning_item_id: int,
) -> list[QuestionFingerprintInput]:
    rows = (
        db.query(
            Question.question_text,
            Question.option_a,
            Question.option_b,
            Question.option_c,
            Question.option_d,
            Question.content_fingerprint,
        )
        .filter(Question.learning_item_id == learning_item_id)
        .all()
    )
    return [
        QuestionFingerprintInput(
            question_text=row.question_text,
            options=(row.option_a, row.option_b, row.option_c, row.option_d),
            stored_fingerprint=row.content_fingerprint,
        )
        for row in rows
    ]


def insert_generated_questions_conflict_safe(
    db: Session,
    values: Sequence[Mapping[str, object]],
) -> dict[str, int]:
    if not values:
        return {}
    statement = (
        insert(Question)
        .values(list(values))
        .on_conflict_do_nothing(
            index_elements=["learning_item_id", "content_fingerprint"],
            index_where=Question.content_fingerprint.is_not(None),
        )
        .returning(Question.id, Question.content_fingerprint)
    )
    rows = db.execute(statement).all()
    return {
        row.content_fingerprint: row.id
        for row in rows
        if row.content_fingerprint is not None
    }


def list_owned_eligible_candidates(
    db: Session,
    user_id: int,
) -> list[QuestionCandidate]:
    rows = (
        db.query(Question.id)
        .join(LearningItem, LearningItem.id == Question.learning_item_id)
        .filter(
            LearningItem.user_id == user_id,
            *eligible_question_filters(),
        )
        .order_by(Question.id)
        .all()
    )
    return [QuestionCandidate(question_id=row.id) for row in rows]


def list_owned_eligible_label_candidates(
    db: Session,
    user_id: int,
    label_ids: Sequence[int],
) -> list[QuestionCandidate]:
    if not label_ids:
        return []
    rows = (
        db.query(Question.id, LearningItemLabel.label_id)
        .join(LearningItem, LearningItem.id == Question.learning_item_id)
        .join(
            LearningItemLabel,
            LearningItemLabel.learning_item_id == LearningItem.id,
        )
        .filter(
            LearningItem.user_id == user_id,
            LearningItemLabel.label_id.in_(label_ids),
            *eligible_question_filters(),
        )
        .order_by(Question.id, LearningItemLabel.label_id)
        .all()
    )
    labels_by_question: dict[int, set[int]] = {}
    for row in rows:
        labels_by_question.setdefault(row.id, set()).add(row.label_id)
    return [
        QuestionCandidate(question_id=question_id, label_ids=frozenset(labels))
        for question_id, labels in labels_by_question.items()
    ]


def find_owned_labels(
    db: Session,
    user_id: int,
    label_ids: Sequence[int],
) -> list[Label]:
    if not label_ids:
        return []
    return (
        db.query(Label)
        .filter(Label.user_id == user_id, Label.id.in_(label_ids))
        .all()
    )


def find_owned_questions_by_ids(
    db: Session,
    user_id: int,
    question_ids: Sequence[int],
) -> dict[int, tuple[Question, LearningItem]]:
    if not question_ids:
        return {}
    rows = (
        db.query(Question, LearningItem)
        .join(LearningItem, LearningItem.id == Question.learning_item_id)
        .filter(
            LearningItem.user_id == user_id,
            Question.id.in_(question_ids),
            *eligible_question_filters(),
        )
        .all()
    )
    return {question.id: (question, item) for question, item in rows}


def list_owned_eligible_smart_candidates(
    db: Session,
    user_id: int,
) -> list[SmartQuestionCandidate]:
    rows = (
        db.query(
            Question.id.label("question_id"),
            LearningItem.id.label("learning_item_id"),
            UserLearningItemMastery.mastery_score,
            UserLearningItemMastery.total_attempts,
            UserLearningItemMastery.next_review_at,
        )
        .join(LearningItem, LearningItem.id == Question.learning_item_id)
        .outerjoin(
            UserLearningItemMastery,
            and_(
                UserLearningItemMastery.learning_item_id == LearningItem.id,
                UserLearningItemMastery.user_id == user_id,
            ),
        )
        .filter(
            LearningItem.user_id == user_id,
            *eligible_question_filters(),
        )
        .order_by(Question.id)
        .all()
    )
    return [
        SmartQuestionCandidate(
            question_id=row.question_id,
            learning_item_id=row.learning_item_id,
            mastery_score=row.mastery_score,
            total_attempts=row.total_attempts or 0,
            next_review_at=row.next_review_at,
        )
        for row in rows
    ]


def add_session(db: Session, session: RevisionSession) -> None:
    db.add(session)


def add_session_label(db: Session, session_label: RevisionSessionLabel) -> None:
    db.add(session_label)


def add_session_question(
    db: Session,
    session_question: RevisionSessionQuestion,
) -> None:
    db.add(session_question)


def flush(db: Session) -> None:
    db.flush()


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
