from datetime import datetime

from sqlalchemy.orm import Session

from src.modules.auth.models import User, UserSession


def find_user_by_username_or_email(db: Session, username: str, email: str) -> User | None:
    return db.query(User).filter(
        (User.username == username) | (User.email == email)
    ).first()


def find_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def find_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def find_refresh_session_for_update(db: Session, token_hash: str) -> UserSession | None:
    return (
        db.query(UserSession)
        .filter(UserSession.token_hash == token_hash)
        .with_for_update()
        .one_or_none()
    )


def family_has_active_session(
    db: Session,
    *,
    user_id: int,
    family_id: str,
    now: datetime,
) -> bool:
    return db.query(UserSession.id).filter(
        UserSession.user_id == user_id,
        UserSession.family_id == family_id,
        UserSession.revoked_at.is_(None),
        UserSession.replaced_by_session_id.is_(None),
        UserSession.expires_at > now,
        UserSession.absolute_expires_at > now,
    ).first() is not None


def revoke_family(db: Session, family_id: str, revoked_at: datetime) -> int:
    return (
        db.query(UserSession)
        .filter(
            UserSession.family_id == family_id,
            UserSession.revoked_at.is_(None),
        )
        .update({UserSession.revoked_at: revoked_at}, synchronize_session=False)
    )


def add_user(db: Session, user: User) -> None:
    db.add(user)


def add_session(db: Session, user_session: UserSession) -> None:
    db.add(user_session)
