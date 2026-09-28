import pytest
from pydantic import ValidationError

from src.core.config import Settings


def _production_settings(**overrides) -> Settings:
    values = {
        "ENVIRONMENT": "production",
        "DATABASE_URL": "postgresql+psycopg://user:password@db.example/revisee",
        "SECRET_KEY": "s" * 32,
        "GOOGLE_API_KEY": "test-google-key",
        "CLOUDINARY_CLOUD_NAME": "test-cloud",
        "CLOUDINARY_API_KEY": "test-cloudinary-key",
        "CLOUDINARY_API_SECRET": "test-cloudinary-secret",
        "CORS_ORIGINS": ["https://revisee.example"],
        "AUTH_COOKIE_SECURE": True,
        "AUTH_COOKIE_SAMESITE": "none",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_accepts_explicit_https_cors_origins() -> None:
    settings = _production_settings(
        CORS_ORIGINS=[
            "https://revisee.vercel.app",
            "https://learn.revisee.example",
        ]
    )
    assert settings.CORS_ORIGINS == [
        "https://revisee.vercel.app",
        "https://learn.revisee.example",
    ]


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "https://*.vercel.app",
        "http://revisee.vercel.app",
        "http://localhost:4200",
        "https://revisee.vercel.app/path",
        "https://revisee.vercel.app/",
    ],
)
def test_production_rejects_unsafe_cors_origins(origin: str) -> None:
    with pytest.raises(ValidationError):
        _production_settings(CORS_ORIGINS=[origin])


def test_development_keeps_localhost_cors_defaults() -> None:
    settings = Settings(
        _env_file=None,
        ENVIRONMENT="development",
        DATABASE_URL="postgresql+psycopg://user:password@localhost/revisee",
        SECRET_KEY="s" * 32,
        GOOGLE_API_KEY="test-google-key",
        CLOUDINARY_CLOUD_NAME="test-cloud",
        CLOUDINARY_API_KEY="test-cloudinary-key",
        CLOUDINARY_API_SECRET="test-cloudinary-secret",
    )
    assert settings.CORS_ORIGINS == [
        "http://localhost:4200",
        "http://localhost:40211",
    ]
    assert settings.AUTH_COOKIE_SECURE is False
    assert settings.AUTH_COOKIE_SAMESITE == "lax"


@pytest.mark.parametrize(
    "overrides",
    [
        {"AUTH_COOKIE_SECURE": False},
        {"AUTH_COOKIE_SAMESITE": "lax"},
        {"AUTH_COOKIE_SAMESITE": "strict"},
    ],
)
def test_production_rejects_unsafe_refresh_cookie_settings(overrides) -> None:
    with pytest.raises(ValidationError):
        _production_settings(**overrides)


def test_refresh_idle_lifetime_cannot_exceed_absolute_lifetime() -> None:
    with pytest.raises(ValidationError):
        _production_settings(
            REFRESH_TOKEN_IDLE_EXPIRE_DAYS=20,
            REFRESH_TOKEN_ABSOLUTE_EXPIRE_DAYS=10,
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"AUTH_COOKIE_NAME": "invalid cookie"},
        {"AUTH_COOKIE_NAME": "refresh;admin=true"},
        {"AUTH_COOKIE_PATH": "/"},
        {"AUTH_COOKIE_PATH": "/unrelated"},
    ],
)
def test_auth_cookie_scope_rejects_unsafe_configuration(overrides) -> None:
    with pytest.raises(ValidationError):
        _production_settings(**overrides)
