from sqlalchemy import case, distinct, extract, func
from sqlalchemy.orm import Session

from src.modules.auth.models import UserSession
from src.modules.labels.models import Label
from src.modules.learning_items.models import LearningItem, LearningItemLabel, Media


def count_learning_items(db: Session, user_id: int) -> int:
    return db.query(LearningItem).filter(LearningItem.user_id == user_id).count()


def count_labels(db: Session, user_id: int) -> int:
    return db.query(Label).filter(Label.user_id == user_id).count()


def list_login_sessions(db: Session, user_id: int) -> list[UserSession]:
    return (
        db.query(UserSession)
        .filter(UserSession.user_id == user_id)
        .order_by(UserSession.created_at.desc())
        .all()
    )


def list_learning_item_summaries(db: Session, user_id: int) -> list[object]:
    return (
        db.query(
            LearningItem.id,
            LearningItem.title,
            LearningItem.description_text,
            func.string_agg(distinct(Label.label_name), ", ").label("labels"),
            func.string_agg(
                case((Media.type == "image", Media.url), else_=None),
                ",",
            ).label("image_urls"),
            func.min(
                case((Media.type == "image", Media.url), else_=None)
            ).label("first_image_url"),
            func.count(
                distinct(case((Media.type == "image", Media.id), else_=None))
            ).label("image_count"),
            func.count(
                distinct(case((Media.type == "pdf", Media.id), else_=None))
            ).label("pdf_count"),
            func.floor(
                extract("epoch", func.now() - LearningItem.created_at) / 3600
            ).label("hours_ago"),
        )
        .outerjoin(
            LearningItemLabel,
            LearningItem.id == LearningItemLabel.learning_item_id,
        )
        .outerjoin(Label, LearningItemLabel.label_id == Label.id)
        .outerjoin(Media, LearningItem.id == Media.learning_item_id)
        .filter(LearningItem.user_id == user_id)
        .group_by(LearningItem.id)
        .all()
    )
