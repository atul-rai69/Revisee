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
