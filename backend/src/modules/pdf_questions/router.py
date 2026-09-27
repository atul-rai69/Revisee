from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.dependencies import (
    get_ai_provider,
    get_current_user,
    get_personal_ai_provider_factory,
)
from src.core.config import Settings, get_settings
from src.db.session import get_db
from src.integrations.ai.base import AIProvider
from src.modules.ai_credentials.provider import PersonalAIProviderFactory
from src.modules.ai_credentials.service import AICredentialService
from src.modules.auth.models import User
from src.modules.pdf_questions.schemas import (
    PdfDraftGenerationRequest,
    PdfDraftGenerationResponse,
    PdfQuestionImportRequest,
    PdfQuestionImportResponse,
)
from src.modules.pdf_questions.service import PdfQuestionService


router = APIRouter(tags=["pdf-questions"])


@router.post(
    "/learning-items/{item_id}/pdf-question-drafts/generate",
    response_model=PdfDraftGenerationResponse,
)
def generate_pdf_question_drafts(
    item_id: int,
    request: PdfDraftGenerationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    revisee_provider: AIProvider = Depends(get_ai_provider),
    settings: Settings = Depends(get_settings),
    personal_factory: PersonalAIProviderFactory = Depends(
        get_personal_ai_provider_factory
    ),
) -> PdfDraftGenerationResponse:
    provider = revisee_provider
    if request.generation_source == "PERSONAL":
        provider = AICredentialService(db, settings, personal_factory).resolve_provider(
            current_user.id, request.credential_id or 0
        )
    return PdfQuestionService(db, settings).generate_drafts(
        user_id=current_user.id,
        learning_item_id=item_id,
        request=request,
        provider=provider,
    )


@router.post(
    "/learning-items/{item_id}/pdf-questions/import",
    response_model=PdfQuestionImportResponse,
)
def import_pdf_questions(
    item_id: int,
    request: PdfQuestionImportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PdfQuestionImportResponse:
    return PdfQuestionService(db, settings).import_questions(
        user_id=current_user.id,
        source_learning_item_id=item_id,
        request=request,
    )
