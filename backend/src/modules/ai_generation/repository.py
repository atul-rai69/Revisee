from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.modules.ai_generation.models import AIGenerationCall, AIGenerationEvent
from src.modules.learning_items.models import LearningItem, LearningItemKeyPoint


@dataclass(frozen=True, slots=True)
class OwnedGenerationSource:
    item_id: int
    title: str
    theory: str | None
    description_text: str | None
    key_points: tuple[str, ...]


def find_owned_source(
    db: Session,
    user_id: int,
    learning_item_id: int,
) -> OwnedGenerationSource | None:
    item = (
        db.query(LearningItem)
        .filter(
            LearningItem.id == learning_item_id,
            LearningItem.user_id == user_id,
        )
        .first()
    )
    if item is None:
        return None
    points = (
        db.query(LearningItemKeyPoint.key_point)
        .filter(LearningItemKeyPoint.learning_item_id == item.id)
        .order_by(LearningItemKeyPoint.id)
        .all()
    )
    return OwnedGenerationSource(
        item_id=item.id,
        title=item.title,
        theory=item.theory,
        description_text=item.description_text,
        key_points=tuple(row.key_point for row in points),
    )


def add_event(db: Session, event: AIGenerationEvent) -> None:
    db.add(event)


def add_call(db: Session, call: AIGenerationCall) -> None:
    db.add(call)


def find_event(db: Session, event_id: int) -> AIGenerationEvent | None:
    return (
        db.query(AIGenerationEvent)
        .filter(AIGenerationEvent.id == event_id)
        .first()
    )


def find_call(db: Session, call_id: int) -> AIGenerationCall | None:
    return (
        db.query(AIGenerationCall)
        .filter(AIGenerationCall.id == call_id)
        .first()
    )


def flush(db: Session) -> None:
    db.flush()
