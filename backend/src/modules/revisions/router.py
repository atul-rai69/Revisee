from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.dependencies import get_ai_provider, get_current_user
from src.db.session import get_db
from src.integrations.ai.base import AIProvider
from src.modules.auth.models import User
from src.modules.revisions.schemas import (
    GenerateRevisionRequest,
    RevisionSessionRequest,
    RevisionSessionResponse,
    RevisionSessionShortageResponse,
    RevisionGenerationResponse,
)
from src.modules.revisions.service import (
    InsufficientQuestionBankError,
    RevisionService,
    RevisionSessionService,
)
from src.modules.revisions.submission_schemas import (
    RevisionSessionErrorResponse,
    RevisionSessionResultResponse,
    RevisionSessionSubmitRequest,
)
from src.modules.revisions.submission_service import (
    RevisionSubmissionError,
    RevisionSubmissionService,
)


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


@router.post(
    "/revision-sessions",
    response_model=RevisionSessionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_409_CONFLICT: {"model": RevisionSessionShortageResponse},
    },
)
def create_revision_session(
    request: RevisionSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RevisionSessionResponse:
    try:
        return RevisionSessionService(db).create(current_user.id, request)
    except InsufficientQuestionBankError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.detail,
        ) from exc


@router.get(
    "/revision-sessions/{session_id}",
    response_model=RevisionSessionResponse,
)
def resume_revision_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RevisionSessionResponse:
    return RevisionSessionService(db).resume(current_user.id, session_id)


@router.post(
    "/revision-sessions/{session_id}/submit",
    response_model=RevisionSessionResultResponse,
    responses={
        status.HTTP_409_CONFLICT: {"model": RevisionSessionErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Request validation error or answer-set mismatch",
            "content": {
                "application/json": {
                    "schema": {
                        "anyOf": [
                            {
                                "$ref": "#/components/schemas/HTTPValidationError"
                            },
                            {
                                "$ref": "#/components/schemas/RevisionSessionErrorResponse"
                            },
                        ]
                    }
                }
            },
        },
    },
)
def submit_revision_session(
    session_id: int,
    request: RevisionSessionSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RevisionSessionResultResponse:
    try:
        return RevisionSubmissionService(db).submit(
            current_user.id,
            session_id,
            request,
        )
    except RevisionSubmissionError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc


@router.get(
    "/revision-sessions/{session_id}/result",
    response_model=RevisionSessionResultResponse,
    responses={
        status.HTTP_409_CONFLICT: {"model": RevisionSessionErrorResponse},
    },
)
def get_revision_session_result(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RevisionSessionResultResponse:
    try:
        return RevisionSubmissionService(db).result(current_user.id, session_id)
    except RevisionSubmissionError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
