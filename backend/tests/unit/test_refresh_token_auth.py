from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import Response
from jose import jwt

from src.core.config import get_settings
from src.core.exceptions import AuthenticationError
from src.core.security import create_access_token, decode_access_token
from src.modules.auth import repository
from src.modules.auth.models import UserSession
from src.modules.auth.router import _clear_refresh_cookie, _set_refresh_cookie
from src.modules.auth.service import AuthService, hash_refresh_token


def test_access_token_contains_required_type_and_lifecycle_claims() -> None:
    payload = decode_access_token(
        create_access_token({"sub": "7", "sid": "family-id"})
    )

    assert payload["sub"] == "7"
    assert payload["sid"] == "family-id"
    assert payload["type"] == "access"
    assert isinstance(payload["iat"], int)
    assert isinstance(payload["exp"], int)
    assert payload["exp"] > payload["iat"]
    assert isinstance(payload["jti"], str) and payload["jti"]


def test_non_access_jwt_and_opaque_refresh_value_are_rejected() -> None:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    refresh_jwt = jwt.encode(
        {
            "sub": "7",
            "type": "refresh",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    with pytest.raises(AuthenticationError) as wrong_type:
        decode_access_token(refresh_jwt)
    assert wrong_type.value.auth_code == "invalid_token_type"

    with pytest.raises(AuthenticationError) as opaque:
        decode_access_token("opaque-refresh-token")
    assert opaque.value.auth_code == "invalid_access_token"


def test_refresh_tokens_are_random_and_only_the_hash_enters_the_model() -> None:
    service = AuthService(MagicMock())
    absolute_expiry = datetime.now(timezone.utc) + timedelta(days=30)

    first_raw, first_session = service._new_session(
        user_id=9,
        family_id="family-id",
        absolute_expires_at=absolute_expiry,
        parent_session_id=None,
        user_agent="test-agent",
        now=datetime.now(timezone.utc),
    )
    second_raw, second_session = service._new_session(
        user_id=9,
        family_id="family-id",
        absolute_expires_at=absolute_expiry,
        parent_session_id=None,
        user_agent="test-agent",
        now=datetime.now(timezone.utc),
    )

    assert first_raw != second_raw
    assert first_session.token_hash == hash_refresh_token(first_raw)
    assert second_session.token_hash == hash_refresh_token(second_raw)
    assert first_session.token_hash != first_raw
    assert len(first_session.token_hash) == 64


def test_refresh_lookup_takes_a_row_lock_before_rotation() -> None:
    db = MagicMock()
    query = db.query.return_value
    filtered = query.filter.return_value
    locked = filtered.with_for_update.return_value
    expected = UserSession(id=3)
    locked.one_or_none.return_value = expected

    result = repository.find_refresh_session_for_update(db, "a" * 64)

    assert result is expected
    filtered.with_for_update.assert_called_once_with()
    locked.one_or_none.assert_called_once_with()


def test_production_refresh_cookie_and_deletion_use_matching_attributes() -> None:
    settings = SimpleNamespace(
        AUTH_COOKIE_NAME="revisee_refresh",
        REFRESH_TOKEN_IDLE_EXPIRE_DAYS=14,
        AUTH_COOKIE_SECURE=True,
        AUTH_COOKIE_SAMESITE="none",
        AUTH_COOKIE_PATH="/auth",
    )
    issued = Response()
    cleared = Response()

    _set_refresh_cookie(issued, "not-a-real-secret", settings)  # type: ignore[arg-type]
    _clear_refresh_cookie(cleared, settings)  # type: ignore[arg-type]

    issued_cookie = issued.headers["set-cookie"]
    cleared_cookie = cleared.headers["set-cookie"]
    for cookie in (issued_cookie, cleared_cookie):
        assert "HttpOnly" in cookie
        assert "Secure" in cookie
        assert "SameSite=none" in cookie
        assert "Path=/auth" in cookie
    assert "Max-Age=0" in cleared_cookie


def test_rotation_rolls_back_when_replacement_cannot_be_persisted(monkeypatch) -> None:
    now = datetime.now(timezone.utc)
    current = SimpleNamespace(
        id=1,
        user_id=3,
        family_id="family-id",
        revoked_at=None,
        replaced_by_session_id=None,
        expires_at=now + timedelta(days=1),
        absolute_expires_at=now + timedelta(days=2),
        last_used_at=now,
    )
    user = SimpleNamespace(id=3)
    db = MagicMock()
    db.flush.side_effect = RuntimeError("synthetic persistence failure")
    monkeypatch.setattr(repository, "find_refresh_session_for_update", lambda *_args: current)
    monkeypatch.setattr(repository, "find_user_by_id", lambda *_args: user)
    monkeypatch.setattr(repository, "add_session", lambda database, session: database.add(session))

    with pytest.raises(RuntimeError, match="synthetic persistence failure"):
        AuthService(db).refresh("opaque-value")

    db.rollback.assert_called_once_with()
    db.commit.assert_not_called()
