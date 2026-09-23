from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.dependencies import get_auth_context
from src.db.session import get_db
from src.modules.auth.schemas import (
    MessageResponse,
    RegistrationResponse,
    TokenResponse,
    UserLogin,
    UserRegistration,
)
from src.modules.auth.service import AuthContext, AuthService


router = APIRouter(tags=["auth"])


@router.post("/register", response_model=RegistrationResponse)
def register(
    data: UserRegistration,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    return AuthService(db).register(data.username, data.email, data.password)


@router.post("/login", response_model=TokenResponse)
def login(data: UserLogin, db: Session = Depends(get_db)) -> dict[str, str]:
    return AuthService(db).login(data.username, data.password)


@router.post("/logout", response_model=MessageResponse)
def logout(
    context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    return AuthService(db).logout(context)
