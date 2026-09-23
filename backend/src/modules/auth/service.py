import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.exceptions import AuthenticationError, ConflictError
from src.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from src.modules.auth import repository
from src.modules.auth.models import User, UserSession


@dataclass(frozen=True)
class AuthContext:
    user: User
    session_id: str


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def register(self, username: str, email: str, password: str) -> dict[str, str]:
        if repository.find_user_by_username_or_email(self.db, username, email):
            self.db.rollback()
            raise ConflictError("An account with that username or email already exists")

        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
        )
        repository.add_user(self.db, user)

        try:
            self.db.flush()
            user_session = self._new_session(user.id)
            repository.add_session(self.db, user_session)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("An account with that username or email already exists") from exc
        except Exception:
            self.db.rollback()
            raise

        return {
            "message": "Registration successful",
            "access_token": self._token(user.id, user_session.session_id),
            "token_type": "bearer",
        }

    def login(self, username: str, password: str) -> dict[str, str]:
        user = repository.find_user_by_username(self.db, username)
        if not user:
            self.db.rollback()
            raise AuthenticationError("Invalid credentials")

        valid, needs_upgrade = verify_password(password, user.password_hash)
        if not valid:
            self.db.rollback()
            raise AuthenticationError("Invalid credentials")

        if needs_upgrade:
            user.password_hash = hash_password(password)

        user_session = self._new_session(user.id)
        repository.add_session(self.db, user_session)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return {
            "access_token": self._token(user.id, user_session.session_id),
            "token_type": "bearer",
        }

    def authenticate(self, token: str) -> AuthContext:
        payload = decode_access_token(token)
        raw_user_id = payload.get("sub")
        session_id = payload.get("session_id")
        if not raw_user_id or not session_id:
            raise AuthenticationError()

        try:
            user_id = int(raw_user_id)
        except (TypeError, ValueError) as exc:
            raise AuthenticationError() from exc

        user_session = repository.find_active_session(self.db, session_id, user_id)
        if not user_session:
            self.db.rollback()
            raise AuthenticationError()

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if user_session.expires_at and user_session.expires_at < now:
            user_session.is_active = False
            self.db.commit()
            raise AuthenticationError("Session expired")

        user = repository.find_user_by_id(self.db, user_id)
        if not user:
            self.db.rollback()
            raise AuthenticationError()

        user_session.last_used_at = now
        self.db.commit()
        return AuthContext(user=user, session_id=session_id)

    def logout(self, context: AuthContext) -> dict[str, str]:
        user_session = repository.find_active_session(
            self.db,
            context.session_id,
            context.user.id,
        )
        if not user_session:
            self.db.rollback()
            raise AuthenticationError("Session already inactive")
        user_session.is_active = False
        self.db.commit()
        return {"message": "Logged out successfully"}

    @staticmethod
    def _token(user_id: int, session_id: str) -> str:
        return create_access_token({"sub": str(user_id), "session_id": session_id})

    @staticmethod
    def _new_session(user_id: int) -> UserSession:
        settings = get_settings()
        return UserSession(
            user_id=user_id,
            session_id=str(uuid.uuid4()),
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None)
            + timedelta(minutes=settings.SESSION_EXPIRE_MINUTES),
        )
