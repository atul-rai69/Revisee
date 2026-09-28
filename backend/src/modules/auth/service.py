import hashlib
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.exceptions import AuthenticationError, ConflictError
from src.core.security import create_access_token, decode_access_token, hash_password, verify_password
from src.modules.auth import repository
from src.modules.auth.models import User, UserSession


@dataclass(frozen=True)
class AuthContext:
    user: User
    family_id: str


@dataclass(frozen=True)
class IssuedAuthentication:
    access_token: str
    expires_in: int
    user: User
    refresh_token: str = field(repr=False)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def register(
        self,
        username: str,
        email: str,
        password: str,
        *,
        user_agent: str | None = None,
    ) -> tuple[str, IssuedAuthentication]:
        if repository.find_user_by_username_or_email(self.db, username, email):
            self.db.rollback()
            raise ConflictError("An account with that username or email already exists")
        user = User(username=username, email=email, password_hash=hash_password(password))
        repository.add_user(self.db, user)
        try:
            self.db.flush()
            authentication = self._create_family(user, user_agent)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("An account with that username or email already exists") from exc
        except Exception:
            self.db.rollback()
            raise
        return "Registration successful", authentication

    def login(
        self,
        username: str,
        password: str,
        *,
        user_agent: str | None = None,
    ) -> IssuedAuthentication:
        user = repository.find_user_by_username(self.db, username)
        if not user:
            self.db.rollback()
            raise AuthenticationError("Invalid credentials", auth_code="invalid_credentials")
        valid, needs_upgrade = verify_password(password, user.password_hash)
        if not valid:
            self.db.rollback()
            raise AuthenticationError("Invalid credentials", auth_code="invalid_credentials")
        if needs_upgrade:
            user.password_hash = hash_password(password)
        try:
            authentication = self._create_family(user, user_agent)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return authentication

    def refresh(
        self,
        refresh_token: str,
        *,
        user_agent: str | None = None,
    ) -> IssuedAuthentication:
        current = repository.find_refresh_session_for_update(
            self.db,
            hash_refresh_token(refresh_token),
        )
        if current is None:
            self.db.rollback()
            raise AuthenticationError(auth_code="invalid_refresh_session")
        now = _utc_now()
        if current.revoked_at is not None or current.replaced_by_session_id is not None:
            repository.revoke_family(self.db, current.family_id, now)
            self.db.commit()
            raise AuthenticationError(auth_code="invalid_refresh_session")
        if current.expires_at <= now or current.absolute_expires_at <= now:
            repository.revoke_family(self.db, current.family_id, now)
            self.db.commit()
            raise AuthenticationError(auth_code="invalid_refresh_session")
        user = repository.find_user_by_id(self.db, current.user_id)
        if user is None:
            repository.revoke_family(self.db, current.family_id, now)
            self.db.commit()
            raise AuthenticationError(auth_code="invalid_refresh_session")

        raw_replacement, replacement = self._new_session(
            user_id=user.id,
            family_id=current.family_id,
            absolute_expires_at=current.absolute_expires_at,
            parent_session_id=current.id,
            user_agent=user_agent,
            now=now,
        )
        current.revoked_at = now
        current.last_used_at = now
        repository.add_session(self.db, replacement)
        try:
            self.db.flush()
            current.replaced_by_session_id = replacement.id
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self._authentication(user, current.family_id, raw_replacement)

    def authenticate(self, token: str) -> AuthContext:
        payload = decode_access_token(token)
        raw_user_id = payload.get("sub")
        family_id = payload.get("sid")
        if not raw_user_id or not isinstance(family_id, str):
            raise AuthenticationError(auth_code="invalid_access_token")
        try:
            user_id = int(raw_user_id)
        except (TypeError, ValueError) as exc:
            raise AuthenticationError(auth_code="invalid_access_token") from exc
        if not repository.family_has_active_session(
            self.db,
            user_id=user_id,
            family_id=family_id,
            now=_utc_now(),
        ):
            self.db.rollback()
            raise AuthenticationError(auth_code="session_revoked")
        user = repository.find_user_by_id(self.db, user_id)
        if user is None:
            self.db.rollback()
            raise AuthenticationError(auth_code="session_revoked")
        return AuthContext(user=user, family_id=family_id)

    def logout(self, refresh_token: str | None) -> None:
        if not refresh_token:
            self.db.rollback()
            return
        current = repository.find_refresh_session_for_update(
            self.db,
            hash_refresh_token(refresh_token),
        )
        if current is None:
            self.db.rollback()
            return
        repository.revoke_family(self.db, current.family_id, _utc_now())
        self.db.commit()

    def _create_family(self, user: User, user_agent: str | None) -> IssuedAuthentication:
        now = _utc_now()
        settings = get_settings()
        absolute_expires_at = now + timedelta(
            days=settings.REFRESH_TOKEN_ABSOLUTE_EXPIRE_DAYS
        )
        family_id = str(uuid.uuid4())
        raw_token, session = self._new_session(
            user_id=user.id,
            family_id=family_id,
            absolute_expires_at=absolute_expires_at,
            parent_session_id=None,
            user_agent=user_agent,
            now=now,
        )
        repository.add_session(self.db, session)
        return self._authentication(user, family_id, raw_token)

    def _new_session(
        self,
        *,
        user_id: int,
        family_id: str,
        absolute_expires_at: datetime,
        parent_session_id: int | None,
        user_agent: str | None,
        now: datetime,
    ) -> tuple[str, UserSession]:
        settings = get_settings()
        raw_token = secrets.token_urlsafe(48)
        idle_expiry = now + timedelta(days=settings.REFRESH_TOKEN_IDLE_EXPIRE_DAYS)
        return raw_token, UserSession(
            user_id=user_id,
            token_hash=hash_refresh_token(raw_token),
            family_id=family_id,
            parent_session_id=parent_session_id,
            issued_at=now,
            expires_at=min(idle_expiry, absolute_expires_at),
            absolute_expires_at=absolute_expires_at,
            last_used_at=now,
            revoked_at=None,
            replaced_by_session_id=None,
            user_agent=(user_agent or "")[:255] or None,
        )

    @staticmethod
    def _authentication(user: User, family_id: str, refresh_token: str) -> IssuedAuthentication:
        settings = get_settings()
        return IssuedAuthentication(
            access_token=create_access_token({"sub": str(user.id), "sid": family_id}),
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user,
            refresh_token=refresh_token,
        )
