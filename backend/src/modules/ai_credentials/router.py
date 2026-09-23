from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user, get_personal_ai_provider_factory
from src.core.config import Settings, get_settings
from src.db.session import get_db
from src.modules.ai_credentials.provider import PersonalAIProviderFactory
from src.modules.ai_credentials.schemas import (
    CredentialCreateRequest,
    CredentialListResponse,
    CredentialResponse,
    CredentialUpdateRequest,
)
from src.modules.ai_credentials.service import AICredentialService
from src.modules.auth.models import User


router = APIRouter(prefix="/ai-credentials", tags=["ai-credentials"])


def _service(
    db: Session,
    settings: Settings,
    factory: PersonalAIProviderFactory,
) -> AICredentialService:
    return AICredentialService(db, settings, factory)


@router.get("", response_model=CredentialListResponse)
def list_credentials(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    factory: PersonalAIProviderFactory = Depends(get_personal_ai_provider_factory),
) -> CredentialListResponse:
    return _service(db, settings, factory).list(current_user.id)


@router.post("", response_model=CredentialResponse, status_code=status.HTTP_201_CREATED)
def create_credential(
    request: CredentialCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    factory: PersonalAIProviderFactory = Depends(get_personal_ai_provider_factory),
) -> CredentialResponse:
    return _service(db, settings, factory).create(current_user.id, request)


@router.patch("/{credential_id}", response_model=CredentialResponse)
def update_credential(
    credential_id: int,
    request: CredentialUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    factory: PersonalAIProviderFactory = Depends(get_personal_ai_provider_factory),
) -> CredentialResponse:
    return _service(db, settings, factory).update(
        current_user.id, credential_id, request
    )


@router.put("/{credential_id}/default", response_model=CredentialResponse)
def select_default_credential(
    credential_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    factory: PersonalAIProviderFactory = Depends(get_personal_ai_provider_factory),
) -> CredentialResponse:
    return _service(db, settings, factory).set_default(current_user.id, credential_id)


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_credential(
    credential_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    factory: PersonalAIProviderFactory = Depends(get_personal_ai_provider_factory),
) -> Response:
    _service(db, settings, factory).delete(current_user.id, credential_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
