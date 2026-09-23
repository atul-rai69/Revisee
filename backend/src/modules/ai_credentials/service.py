from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.config import Settings
from src.core.exceptions import (
    ConflictError,
    InvalidProviderCredentialError,
    ResourceNotFoundError,
)
from src.integrations.ai.base import AIProvider, StructuredAIRequest, StructuredAIResult
from src.modules.ai_credentials import repository
from src.modules.ai_credentials.crypto import CredentialCipher
from src.modules.ai_credentials.models import AICredential, AICredentialUsage
from src.modules.ai_credentials.provider import PersonalAIProviderFactory
from src.modules.ai_credentials.schemas import (
    CredentialCreateRequest,
    CredentialListResponse,
    CredentialResponse,
    CredentialUpdateRequest,
    CredentialUsageResponse,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class UsageRecordingProvider:
    def __init__(
        self,
        db: Session,
        delegate: AIProvider,
        credential: AICredential,
    ) -> None:
        self.db = db
        self.delegate = delegate
        self.credential = credential

    def generate(self, prompt: str) -> str:
        return self.delegate.generate(prompt)

    def generate_structured(self, request: StructuredAIRequest) -> StructuredAIResult:
        try:
            result = self.delegate.generate_structured(request)
        except InvalidProviderCredentialError:
            self.db.rollback()
            credential = repository.find_owned(
                self.db, self.credential.user_id, self.credential.id
            )
            if credential is not None:
                credential.status = "INVALID"
                self.db.commit()
            raise
        now = _utc_now()
        self.credential.last_used_at = now
        self.db.add(
            AICredentialUsage(
                user_id=self.credential.user_id,
                credential_id=self.credential.id,
                operation_type=request.operation.value,
                provider="GEMINI",
                model=result.model,
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
                total_tokens=result.usage.total_tokens,
                created_at=now,
            )
        )
        return result


class AICredentialService:
    PROVIDER_CONSOLE_URL = "https://aistudio.google.com/usage"

    def __init__(
        self,
        db: Session,
        settings: Settings,
        provider_factory: PersonalAIProviderFactory,
    ) -> None:
        self.db = db
        self.settings = settings
        self.provider_factory = provider_factory

    @property
    def cipher(self) -> CredentialCipher:
        return CredentialCipher(self.settings)

    def list(self, user_id: int) -> CredentialListResponse:
        credentials = repository.list_owned(self.db, user_id)
        usage = repository.usage_by_credential(self.db, user_id)
        response = CredentialListResponse(
            credentials=[
                self._response(
                    credential,
                    usage.get(credential.id),
                )
                for credential in credentials
            ],
            provider_console_url=self.PROVIDER_CONSOLE_URL,
        )
        self.db.rollback()
        return response

    def create(self, user_id: int, request: CredentialCreateRequest) -> CredentialResponse:
        self.provider_factory.validate(request.api_key)
        now = _utc_now()
        existing = repository.list_owned(self.db, user_id)
        credential = AICredential(
            user_id=user_id,
            provider=request.provider,
            name=request.name,
            encrypted_secret=b"pending",
            encryption_nonce=b"pending",
            encryption_key_version="pending",
            key_fingerprint=self.cipher.fingerprint(request.api_key),
            key_hint=request.api_key[-4:],
            status="VALID",
            is_default=request.make_default or not existing,
            last_validated_at=now,
        )
        try:
            if credential.is_default:
                repository.clear_default(self.db, user_id, request.provider)
            repository.add(self.db, credential)
            self.db.flush()
            encrypted = self.cipher.encrypt(
                request.api_key,
                user_id=user_id,
                credential_id=credential.id,
                provider=request.provider,
            )
            credential.encrypted_secret = encrypted.ciphertext
            credential.encryption_nonce = encrypted.nonce
            credential.encryption_key_version = encrypted.key_version
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("A credential with that name or key already exists") from exc
        return self._response(credential, None)

    def update(
        self,
        user_id: int,
        credential_id: int,
        request: CredentialUpdateRequest,
    ) -> CredentialResponse:
        credential = self._owned(user_id, credential_id)
        if request.api_key is not None:
            self.provider_factory.validate(request.api_key)
            encrypted = self.cipher.encrypt(
                request.api_key,
                user_id=user_id,
                credential_id=credential.id,
                provider=credential.provider,
            )
            credential.encrypted_secret = encrypted.ciphertext
            credential.encryption_nonce = encrypted.nonce
            credential.encryption_key_version = encrypted.key_version
            credential.key_fingerprint = self.cipher.fingerprint(request.api_key)
            credential.key_hint = request.api_key[-4:]
            credential.status = "VALID"
            credential.last_validated_at = _utc_now()
        if request.name is not None:
            credential.name = request.name
        if request.make_default is True:
            if credential.status != "VALID":
                self.db.rollback()
                raise InvalidProviderCredentialError()
            repository.clear_default(self.db, user_id, credential.provider)
            credential.is_default = True
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("A credential with that name or key already exists") from exc
        usage = repository.usage_by_credential(self.db, user_id).get(credential.id)
        return self._response(credential, usage)

    def set_default(self, user_id: int, credential_id: int) -> CredentialResponse:
        return self.update(
            user_id,
            credential_id,
            CredentialUpdateRequest(make_default=True),
        )

    def delete(self, user_id: int, credential_id: int) -> None:
        credential = self._owned(user_id, credential_id)
        was_default = credential.is_default
        provider = credential.provider
        self.db.delete(credential)
        self.db.flush()
        if was_default:
            replacement = (
                self.db.query(AICredential)
                .filter(
                    AICredential.user_id == user_id,
                    AICredential.provider == provider,
                )
                .order_by(AICredential.created_at.asc())
                .first()
            )
            if replacement is not None:
                replacement.is_default = True
        self.db.commit()

    def resolve_provider(self, user_id: int, credential_id: int) -> AIProvider:
        credential = self._owned(user_id, credential_id)
        if credential.status != "VALID":
            self.db.rollback()
            raise InvalidProviderCredentialError()
        secret = self.cipher.decrypt(
            credential.encrypted_secret,
            credential.encryption_nonce,
            credential.encryption_key_version,
            user_id=user_id,
            credential_id=credential.id,
            provider=credential.provider,
        )
        return UsageRecordingProvider(
            self.db,
            self.provider_factory.create(secret),
            credential,
        )

    def _owned(self, user_id: int, credential_id: int) -> AICredential:
        credential = repository.find_owned(self.db, user_id, credential_id)
        if credential is None:
            self.db.rollback()
            raise ResourceNotFoundError("AI credential not found")
        return credential

    @staticmethod
    def _response(credential: AICredential, usage) -> CredentialResponse:
        return CredentialResponse(
            id=credential.id,
            provider="GEMINI",
            name=credential.name,
            masked_identifier=f"•••• {credential.key_hint}",
            status=credential.status,
            is_default=credential.is_default,
            last_validated_at=credential.last_validated_at,
            last_used_at=credential.last_used_at,
            created_at=credential.created_at,
            usage=CredentialUsageResponse(
                request_count=usage.request_count if usage else 0,
                input_tokens=usage.input_tokens if usage else None,
                output_tokens=usage.output_tokens if usage else None,
                total_tokens=usage.total_tokens if usage else None,
                updated_at=usage.updated_at if usage else None,
            ),
        )
