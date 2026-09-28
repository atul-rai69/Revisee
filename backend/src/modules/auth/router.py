from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from src.core.config import Settings, get_settings
from src.core.exceptions import AuthenticationError, CsrfError
from src.db.session import get_db
from src.modules.auth.schemas import (
    MessageResponse,
    RegistrationResponse,
    TokenResponse,
    UserLogin,
    UserRegistration,
)
from src.modules.auth.service import AuthService, IssuedAuthentication


router = APIRouter(tags=["auth"])
CSRF_HEADER = "X-Revisee-CSRF"
CSRF_HEADER_VALUE = "spa"


def _validate_cookie_request(request: Request, settings: Settings) -> None:
    origin = request.headers.get("origin")
    csrf_header = request.headers.get(CSRF_HEADER)
    if origin not in settings.CORS_ORIGINS or csrf_header != CSRF_HEADER_VALUE:
        raise CsrfError()


def _set_refresh_cookie(
    response: Response,
    refresh_token: str,
    settings: Settings,
) -> None:
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_IDLE_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        path=settings.AUTH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value="",
        max_age=0,
        expires=0,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        path=settings.AUTH_COOKIE_PATH,
    )


def _token_response(authentication: IssuedAuthentication) -> dict[str, object]:
    return {
        "access_token": authentication.access_token,
        "token_type": "bearer",
        "expires_in": authentication.expires_in,
        "user": authentication.user,
    }


@router.post("/register", response_model=RegistrationResponse)
def register(
    data: UserRegistration,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    message, authentication = AuthService(db).register(
        data.username,
        data.email,
        data.password,
        user_agent=request.headers.get("user-agent"),
    )
    _set_refresh_cookie(response, authentication.refresh_token, settings)
    return {"message": message, **_token_response(authentication)}


@router.post("/login", response_model=TokenResponse)
def login(
    data: UserLogin,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    authentication = AuthService(db).login(
        data.username,
        data.password,
        user_agent=request.headers.get("user-agent"),
    )
    _set_refresh_cookie(response, authentication.refresh_token, settings)
    return _token_response(authentication)


@router.post("/auth/refresh", response_model=TokenResponse)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    _validate_cookie_request(request, settings)
    raw_token = request.cookies.get(settings.AUTH_COOKIE_NAME)
    if not raw_token:
        raise AuthenticationError(
            auth_code="invalid_refresh_session",
            clear_refresh_cookie=True,
        )
    try:
        authentication = AuthService(db).refresh(
            raw_token,
            user_agent=request.headers.get("user-agent"),
        )
    except AuthenticationError as exc:
        exc.clear_refresh_cookie = True
        raise
    _set_refresh_cookie(response, authentication.refresh_token, settings)
    return _token_response(authentication)


@router.post("/auth/logout", response_model=MessageResponse)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    _validate_cookie_request(request, settings)
    AuthService(db).logout(request.cookies.get(settings.AUTH_COOKIE_NAME))
    _clear_refresh_cookie(response, settings)
    return {"message": "Logged out successfully"}
