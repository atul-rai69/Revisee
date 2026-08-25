from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.dependencies import get_ai_provider, get_current_user
from src.db.session import get_db
from src.integrations.ai.base import AIProvider
from src.modules.auth.models import User
from src.modules.revisions.schemas import (
    GenerateRevisionRequest,
    RevisionGenerationResponse,
)
from src.modules.revisions.service import RevisionService


router = APIRouter(tags=["revisions"])


@router.post("/generate", response_model=RevisionGenerationResponse)
def generate_revision(
    request: GenerateRevisionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider),
) -> dict[str, str]:
    return RevisionService(db, provider).generate_for_owned_item(
        current_user.id,
        request.learning_item_id,
        request.title,
        request.description,
    )
