import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import ExpiredSignatureError, JWTError, jwt
from pwdlib import PasswordHash

from src.core.config import get_settings
from src.core.exceptions import AuthenticationError


_password_hash = PasswordHash.recommended()
_ARGON2ID_PATTERN = re.compile(r"^\$argon2id\$v=\d+\$[^$]+\$[^$]+\$[^$]+$")
_HASH_LIKE_PATTERN = re.compile(r"^\$(argon2|2[aby]|scrypt|pbkdf2)", re.IGNORECASE)


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def is_approved_password_hash(value: str) -> bool:
    return bool(_ARGON2ID_PATTERN.match(value))


def looks_like_unsupported_hash(value: str) -> bool:
    return bool(_HASH_LIKE_PATTERN.match(value)) and not is_approved_password_hash(value)


def verify_password(password: str, stored_value: str) -> tuple[bool, bool]:
    """Return (valid, needs_legacy_upgrade).

    The plaintext branch is temporary and must be removed after the reviewed
    password migration reports no remaining legacy rows.
    """
    if is_approved_password_hash(stored_value):
        try:
            return _password_hash.verify(password, stored_value), False
        except Exception:
            return False, False

    if looks_like_unsupported_hash(stored_value):
        return False, False

    return secrets.compare_digest(password, stored_value), True


def create_access_token(data: dict[str, Any]) -> str:
    settings = get_settings()
    payload = data.copy()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload.update({
        "iat": now,
        "exp": expires_at,
        "type": "access",
        "jti": secrets.token_urlsafe(16),
    })
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        if payload.get("type") != "access":
            raise AuthenticationError(auth_code="invalid_token_type")
        return payload
    except ExpiredSignatureError as exc:
        raise AuthenticationError(auth_code="access_token_expired") from exc
    except AuthenticationError:
        raise
    except JWTError as exc:
        raise AuthenticationError(auth_code="invalid_access_token") from exc
