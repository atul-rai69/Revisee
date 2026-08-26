"""Import every model module so SQLAlchemy and Alembic see complete metadata."""

from src.modules.auth.models import User, UserSession
from src.modules.labels.models import Label
from src.modules.learning_items.models import (
    LearningItem,
    LearningItemKeyPoint,
    LearningItemLabel,
    Media,
)
from src.modules.mastery.models import UserLabelMastery, UserLearningItemMastery
from src.modules.revisions.models import (
    Question,
    RevisionSession,
    RevisionSessionLabel,
    RevisionSessionQuestion,
    UserAttempt,
)


__all__ = [
    "Label",
    "LearningItem",
    "LearningItemKeyPoint",
    "LearningItemLabel",
    "Media",
    "Question",
    "RevisionSession",
    "RevisionSessionLabel",
    "RevisionSessionQuestion",
    "User",
    "UserAttempt",
    "UserLabelMastery",
    "UserLearningItemMastery",
    "UserSession",
]
