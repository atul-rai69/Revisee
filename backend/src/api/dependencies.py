from functools import lru_cache

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.core.config import get_settings
from src.integrations.ai.base import AIProvider
from src.integrations.storage.base import StorageProvider
from src.modules.auth.models import User
from src.modules.auth.service import AuthContext, AuthService
from src.modules.ai_credentials.provider import (
    GeminiPersonalAIProviderFactory,
    PersonalAIProviderFactory,
)


bearer_scheme = HTTPBearer(auto_error=False)


def get_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AuthContext:
    if credentials is None:
        from src.core.exceptions import AuthenticationError

        raise AuthenticationError()
    return AuthService(db).authenticate(credentials.credentials)


def get_current_user(context: AuthContext = Depends(get_auth_context)) -> User:
    return context.user


@lru_cache
def get_ai_provider() -> AIProvider:
    from src.integrations.ai.gemini import GeminiAIProvider

    return GeminiAIProvider(get_settings())


@lru_cache
def get_storage_provider() -> StorageProvider:
    from src.integrations.storage.cloudinary import CloudinaryStorageProvider

    return CloudinaryStorageProvider(get_settings())


@lru_cache
def get_personal_ai_provider_factory() -> PersonalAIProviderFactory:
    return GeminiPersonalAIProviderFactory(get_settings())
