from collections.abc import Sequence

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from src.modules.labels.models import Label
from src.modules.learning_items.models import (
    LearningItem,
    LearningItemKeyPoint,
    LearningItemLabel,
    Media,
    PdfNote,
)
from src.modules.revisions.models import Question, UserAttempt


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
    original_filename: str | None,
) -> None:
    db.add(
        Media(
            learning_item_id=learning_item_id,
            type=media_type,
            url=url,
            public_id=public_id,
            original_filename=original_filename,
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


def find_owned_pdf_media(
    db: Session,
    *,
    media_id: int,
    learning_item_id: int,
    user_id: int,
) -> Media | None:
    return (
        db.query(Media)
        .join(LearningItem, LearningItem.id == Media.learning_item_id)
        .filter(
            Media.id == media_id,
            Media.learning_item_id == learning_item_id,
            Media.type == "pdf",
            LearningItem.user_id == user_id,
        )
        .first()
    )


def list_pdf_notes(db: Session, *, user_id: int, item_id: int) -> list[PdfNote]:
    return (
        db.query(PdfNote)
        .filter(
            PdfNote.user_id == user_id,
            PdfNote.learning_item_id == item_id,
        )
        .order_by(PdfNote.updated_at.desc(), PdfNote.id.desc())
        .all()
    )


def find_owned_pdf_note(
    db: Session,
    *,
    note_id: int,
    item_id: int,
    user_id: int,
) -> PdfNote | None:
    return (
        db.query(PdfNote)
        .filter(
            PdfNote.id == note_id,
            PdfNote.learning_item_id == item_id,
            PdfNote.user_id == user_id,
        )
        .first()
    )


def add_pdf_note(db: Session, note: PdfNote) -> None:
    db.add(note)


def list_question_statistics_for_user(
    db: Session, user_id: int, question_ids: Sequence[int]
) -> dict[int, tuple[int, int]]:
    if not question_ids:
        return {}
    rows = (
        db.query(
            UserAttempt.question_id,
            func.count(UserAttempt.id).label("total_attempts"),
            func.sum(case((UserAttempt.is_correct.is_(True), 1), else_=0)).label("correct_attempts"),
        )
        .filter(
            UserAttempt.user_id == user_id,
            UserAttempt.question_id.in_(question_ids),
        )
        .group_by(UserAttempt.question_id)
        .all()
    )
    return {
        row.question_id: (int(row.total_attempts), int(row.correct_attempts or 0))
        for row in rows if row.question_id is not None
    }


def has_question_fingerprint(db: Session, item_id: int, fingerprint: str) -> bool:
    return db.query(Question.id).filter(
        Question.learning_item_id == item_id,
        Question.content_fingerprint == fingerprint,
    ).first() is not None


def add_question(db: Session, question: Question) -> None:
    db.add(question)


def delete_owned(db: Session, learning_item: LearningItem) -> None:
    db.query(LearningItemKeyPoint).filter(
        LearningItemKeyPoint.learning_item_id == learning_item.id
    ).delete(synchronize_session=False)
    db.delete(learning_item)
