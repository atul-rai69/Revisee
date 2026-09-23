import base64
from types import SimpleNamespace

import pytest

from src.core.exceptions import CredentialConfigurationError
from src.modules.ai_credentials.crypto import CredentialCipher


def _settings(keys=None, active="v1"):
    encoded = base64.urlsafe_b64encode(b"a" * 32).decode()
    return SimpleNamespace(
        BYOK_ACTIVE_ENCRYPTION_KEY_VERSION=active,
        BYOK_ENCRYPTION_KEYS=keys if keys is not None else {"v1": encoded},
    )


def test_cipher_round_trip_is_bound_to_owner_and_row() -> None:
    cipher = CredentialCipher(_settings())
    encrypted = cipher.encrypt(
        "gemini-secret-value",
        user_id=7,
        credential_id=11,
        provider="GEMINI",
    )
    assert b"gemini-secret-value" not in encrypted.ciphertext
    assert cipher.decrypt(
        encrypted.ciphertext,
        encrypted.nonce,
        encrypted.key_version,
        user_id=7,
        credential_id=11,
        provider="GEMINI",
    ) == "gemini-secret-value"
    with pytest.raises(CredentialConfigurationError):
        cipher.decrypt(
            encrypted.ciphertext,
            encrypted.nonce,
            encrypted.key_version,
            user_id=8,
            credential_id=11,
            provider="GEMINI",
        )


def test_missing_or_invalid_keyring_fails_closed() -> None:
    with pytest.raises(CredentialConfigurationError):
        CredentialCipher(_settings(keys={}, active=None))
    bad = base64.urlsafe_b64encode(b"too-short").decode()
    with pytest.raises(CredentialConfigurationError):
        CredentialCipher(_settings(keys={"v1": bad}))
