from sqlalchemy.orm import Session

from src.modules.auth.models import User, UserSession


def find_user_by_username_or_email(
    db: Session,
    username: str,
    email: str,
) -> User | None:
    return db.query(User).filter(
        (User.username == username) | (User.email == email)
    ).first()


def find_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def find_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def find_active_session(
    db: Session,
    session_id: str,
    user_id: int,
) -> UserSession | None:
    return db.query(UserSession).filter(
        UserSession.session_id == session_id,
        UserSession.user_id == user_id,
        UserSession.is_active.is_(True),
    ).first()


def add_user(db: Session, user: User) -> None:
    db.add(user)


def add_session(db: Session, user_session: UserSession) -> None:
    db.add(user_session)
