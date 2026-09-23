"""Import every model module so SQLAlchemy and Alembic see complete metadata."""

from src.modules.auth.models import User, UserSession
from src.modules.ai_credentials.models import AICredential, AICredentialUsage
from src.modules.ai_generation.models import AIGenerationCall, AIGenerationEvent
from src.modules.labels.models import Label
from src.modules.learning_items.models import (
    LearningItem,
    LearningItemKeyPoint,
    LearningItemLabel,
    Media,
    PdfNote,
)
from src.modules.mastery.models import MasteryHistory, UserLabelMastery, UserLearningItemMastery
from src.modules.revisions.models import (
    Question,
    QuestionStatistics,
    RevisionSession,
    RevisionSessionLabel,
    RevisionSessionQuestion,
    UserAttempt,
)


__all__ = [
    "AICredential",
    "AICredentialUsage",
    "AIGenerationCall",
    "AIGenerationEvent",
    "Label",
    "LearningItem",
    "LearningItemKeyPoint",
    "LearningItemLabel",
    "Media",
    "PdfNote",
    "MasteryHistory",
    "Question",
    "QuestionStatistics",
    "RevisionSession",
    "RevisionSessionLabel",
    "RevisionSessionQuestion",
    "User",
    "UserAttempt",
    "UserLabelMastery",
    "UserLearningItemMastery",
    "UserSession",
]
