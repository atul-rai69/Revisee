import base64
import hashlib
import os
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from src.core.config import Settings
from src.core.exceptions import CredentialConfigurationError


@dataclass(frozen=True, slots=True)
class EncryptedCredential:
    ciphertext: bytes
    nonce: bytes
    key_version: str


class CredentialCipher:
    """AES-256-GCM keyring; ciphertext is bound to its owner and database row."""

    def __init__(self, settings: Settings) -> None:
        self.active_version = settings.BYOK_ACTIVE_ENCRYPTION_KEY_VERSION
        self.keys: dict[str, bytes] = {}
        for version, encoded in settings.BYOK_ENCRYPTION_KEYS.items():
            try:
                key = base64.urlsafe_b64decode(encoded.encode("ascii"))
            except Exception as exc:
                raise CredentialConfigurationError(
                    "Personal credential encryption is misconfigured"
                ) from exc
            if len(key) != 32:
                raise CredentialConfigurationError(
                    "Personal credential encryption is misconfigured"
                )
            self.keys[version] = key

        if not self.active_version or self.active_version not in self.keys:
            raise CredentialConfigurationError()

    def encrypt(
        self,
        plaintext: str,
        *,
        user_id: int,
        credential_id: int,
        provider: str,
    ) -> EncryptedCredential:
        assert self.active_version is not None
        nonce = os.urandom(12)
        ciphertext = AESGCM(self.keys[self.active_version]).encrypt(
            nonce,
            plaintext.encode("utf-8"),
            self._associated_data(user_id, credential_id, provider),
        )
        return EncryptedCredential(ciphertext, nonce, self.active_version)

    def decrypt(
        self,
        ciphertext: bytes,
        nonce: bytes,
        key_version: str,
        *,
        user_id: int,
        credential_id: int,
        provider: str,
    ) -> str:
        key = self.keys.get(key_version)
        if key is None:
            raise CredentialConfigurationError(
                "The encryption key required for this credential is unavailable"
            )
        try:
            value = AESGCM(key).decrypt(
                nonce,
                ciphertext,
                self._associated_data(user_id, credential_id, provider),
            )
            return value.decode("utf-8")
        except (InvalidTag, UnicodeDecodeError) as exc:
            raise CredentialConfigurationError(
                "The stored personal credential could not be decrypted"
            ) from exc

    @staticmethod
    def fingerprint(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _associated_data(user_id: int, credential_id: int, provider: str) -> bytes:
        return f"revisee-ai-credential:v1:{user_id}:{credential_id}:{provider}".encode()
