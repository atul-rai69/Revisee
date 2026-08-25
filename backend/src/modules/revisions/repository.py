from sqlalchemy.orm import Session

from src.modules.learning_items.models import LearningItem, LearningItemKeyPoint
from src.modules.revisions.models import Question
from src.modules.revisions.schemas import GeneratedRevisionResponse


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
