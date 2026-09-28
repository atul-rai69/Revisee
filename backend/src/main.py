from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from src.api.router import api_router
from src.core.config import get_settings
from src.core.exceptions import ApplicationError, AuthenticationError

# Register every SQLAlchemy table in shared metadata for migrations and tests.
import src.db.models  # noqa: F401

settings = get_settings()
app = FastAPI(debug=settings.DEBUG)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Revisee-CSRF"],
    expose_headers=["X-Auth-Error"],
)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Lightweight process health check; does not expose configuration."""
    return {"status": "ok"}

@app.exception_handler(ApplicationError)
async def application_error_handler(
    _request: Request,
    exc: ApplicationError,
) -> JSONResponse:
    headers = None
    if isinstance(exc, AuthenticationError):
        headers = {
            "WWW-Authenticate": "Bearer",
            "X-Auth-Error": exc.auth_code,
        }
    response = JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=headers,
    )
    if isinstance(exc, AuthenticationError) and exc.clear_refresh_cookie:
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
    return response


app.include_router(api_router)
