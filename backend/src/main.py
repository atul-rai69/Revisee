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
    allow_methods=["*"],
    allow_headers=["*"],
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
    headers = {"WWW-Authenticate": "Bearer"} if isinstance(
        exc,
        AuthenticationError,
    ) else None
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=headers,
    )


app.include_router(api_router)
