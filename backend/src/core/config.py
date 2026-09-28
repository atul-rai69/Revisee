from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    ENVIRONMENT: str = "development"
    DEBUG: bool = Field(
        default=False,
        validation_alias=AliasChoices("REVISEE_DEBUG", "APP_DEBUG"),
    )

    DATABASE_URL: str | None = None
    TEST_DATABASE_URL: str | None = None

    SECRET_KEY: str = Field(min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, ge=5, le=60)
    REFRESH_TOKEN_IDLE_EXPIRE_DAYS: int = Field(default=14, ge=1, le=30)
    REFRESH_TOKEN_ABSOLUTE_EXPIRE_DAYS: int = Field(default=30, ge=1, le=90)
    AUTH_COOKIE_NAME: str = Field(
        default="revisee_refresh",
        min_length=1,
        max_length=80,
        pattern=r"^[A-Za-z0-9!#$%&'*+.^_`|~-]+$",
    )
    AUTH_COOKIE_SECURE: bool = False
    AUTH_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    AUTH_COOKIE_PATH: str = "/auth"

    GOOGLE_API_KEY: str = Field(min_length=1)
    GEMINI_MODEL: str = "gemini-2.5-flash"
    BYOK_ACTIVE_ENCRYPTION_KEY_VERSION: str | None = None
    BYOK_ENCRYPTION_KEYS: dict[str, str] = Field(default_factory=dict)

    AI_GENERATION_ENABLED: bool = True
    AI_MAX_SOURCE_CHARACTERS: int = Field(default=8_000, gt=0)
    AI_MAX_THEORY_CHARACTERS: int = Field(default=6_000, gt=0)
    AI_MAX_KEY_POINT_CHARACTERS: int = Field(default=2_000, gt=0)
    AI_MAX_NOTES_CHARACTERS: int = Field(default=8_000, gt=0)
    AI_MAX_PROMPT_CHARACTERS: int = Field(default=12_000, gt=0)
    AI_MAX_RAW_RESPONSE_CHARACTERS: int = Field(default=40_000, gt=0)
    AI_MAX_OUTPUT_TOKENS: int = Field(default=4_800, gt=0)
    AI_MAX_QUESTIONS_PER_CALL: int = Field(default=10, ge=1, le=50)
    AI_MAX_SOURCE_ITEMS_PER_OPERATION: int = Field(default=5, ge=1, le=50)
    AI_PROVIDER_TIMEOUT_SECONDS: int = Field(default=20, gt=0)
    AI_OPERATION_DEADLINE_SECONDS: int = Field(default=120, gt=0)
    AI_PROVIDER_ATTEMPTS: int = Field(default=2, ge=1, le=5)
    AI_MAX_EXPECTED_TIME_SECONDS: int = Field(default=3_600, gt=0)
    AI_MAX_PERSONAL_REMARKS_CHARACTERS: int = Field(default=2_000, ge=100, le=10_000)
    AI_MAX_CONCURRENT_PROVIDER_REQUESTS: int = Field(default=2, ge=1, le=20)

    PDF_QUESTION_MAX_PAGES: int = Field(default=50, ge=1, le=200)
    PDF_QUESTION_MAX_PAGE_CHARACTERS: int = Field(default=20_000, ge=500, le=100_000)
    PDF_QUESTION_MAX_EXTRACTED_CHARACTERS: int = Field(default=120_000, ge=1_000)
    PDF_QUESTION_MAX_IMPORT_COUNT: int = Field(default=25, ge=1, le=100)
    PDF_QUESTION_MAX_COVERAGE_PAGES: int = Field(default=12, ge=1, le=50)

    CLOUDINARY_CLOUD_NAME: str = Field(min_length=1)
    CLOUDINARY_API_KEY: str = Field(min_length=1)
    CLOUDINARY_API_SECRET: str = Field(min_length=1)
    CLOUDINARY_MAX_IMAGE_BYTES: int = Field(default=10 * 1024 * 1024, gt=0)
    CLOUDINARY_MAX_RAW_BYTES: int = Field(default=10 * 1024 * 1024, gt=0)

    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:4200",
            "http://localhost:40211",
        ]
    )

    @field_validator("ENVIRONMENT")
    @classmethod
    def normalize_environment(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.lstrip().startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def validate_cors_origins(self) -> "Settings":
        if not self.CORS_ORIGINS:
            raise ValueError("CORS_ORIGINS must contain at least one origin")

        for origin in self.CORS_ORIGINS:
            parsed = urlsplit(origin)
            if (
                "*" in origin
                or parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(
                    "CORS_ORIGINS entries must be explicit HTTP(S) origins"
                )

            if self.ENVIRONMENT == "production":
                hostname = (parsed.hostname or "").casefold()
                if parsed.scheme != "https" or hostname in {
                    "localhost",
                    "127.0.0.1",
                    "::1",
                }:
                    raise ValueError(
                        "Production CORS_ORIGINS must use HTTPS and cannot "
                        "contain localhost"
                    )
        return self

    @field_validator("BYOK_ENCRYPTION_KEYS", mode="before")
    @classmethod
    def parse_byok_encryption_keys(cls, value: object) -> object:
        if value in (None, ""):
            return {}
        return value

    @model_validator(mode="after")
    def validate_test_database(self) -> "Settings":
        if self.REFRESH_TOKEN_IDLE_EXPIRE_DAYS > self.REFRESH_TOKEN_ABSOLUTE_EXPIRE_DAYS:
            raise ValueError(
                "REFRESH_TOKEN_IDLE_EXPIRE_DAYS must not exceed "
                "REFRESH_TOKEN_ABSOLUTE_EXPIRE_DAYS"
            )
        if self.AUTH_COOKIE_PATH != "/auth":
            raise ValueError("AUTH_COOKIE_PATH must be /auth")
        if self.AUTH_COOKIE_SAMESITE == "none" and not self.AUTH_COOKIE_SECURE:
            raise ValueError("SameSite=None refresh cookies must be Secure")
        if self.ENVIRONMENT == "production":
            if not self.AUTH_COOKIE_SECURE:
                raise ValueError("Production refresh cookies must be Secure")
            if self.AUTH_COOKIE_SAMESITE != "none":
                raise ValueError(
                    "Cross-origin production refresh cookies require SameSite=None"
                )
        if self.AI_MAX_THEORY_CHARACTERS > self.AI_MAX_SOURCE_CHARACTERS:
            raise ValueError(
                "AI_MAX_THEORY_CHARACTERS must not exceed "
                "AI_MAX_SOURCE_CHARACTERS"
            )
        if self.AI_MAX_KEY_POINT_CHARACTERS > self.AI_MAX_SOURCE_CHARACTERS:
            raise ValueError(
                "AI_MAX_KEY_POINT_CHARACTERS must not exceed "
                "AI_MAX_SOURCE_CHARACTERS"
            )
        if self.AI_MAX_NOTES_CHARACTERS > self.AI_MAX_SOURCE_CHARACTERS:
            raise ValueError(
                "AI_MAX_NOTES_CHARACTERS must not exceed "
                "AI_MAX_SOURCE_CHARACTERS"
            )
        if (
            self.AI_MAX_PROMPT_CHARACTERS - self.AI_MAX_SOURCE_CHARACTERS
            < 1_500
        ):
            raise ValueError(
                "AI_MAX_PROMPT_CHARACTERS must leave at least 1500 characters "
                "for question-generation instructions"
            )
        if self.AI_PROVIDER_TIMEOUT_SECONDS > self.AI_OPERATION_DEADLINE_SECONDS:
            raise ValueError(
                "AI_PROVIDER_TIMEOUT_SECONDS must not exceed "
                "AI_OPERATION_DEADLINE_SECONDS"
            )
        if bool(self.BYOK_ACTIVE_ENCRYPTION_KEY_VERSION) != bool(
            self.BYOK_ENCRYPTION_KEYS
        ):
            raise ValueError(
                "BYOK_ACTIVE_ENCRYPTION_KEY_VERSION and BYOK_ENCRYPTION_KEYS "
                "must be configured together"
            )
        if (
            self.BYOK_ACTIVE_ENCRYPTION_KEY_VERSION
            and self.BYOK_ACTIVE_ENCRYPTION_KEY_VERSION not in self.BYOK_ENCRYPTION_KEYS
        ):
            raise ValueError("Active BYOK encryption key version is not in the keyring")
        if self.ENVIRONMENT != "test":
            if not self.DATABASE_URL:
                raise ValueError("DATABASE_URL is required outside test mode")
            return self

        if not self.TEST_DATABASE_URL:
            raise ValueError("TEST_DATABASE_URL is required when ENVIRONMENT=test")
        if self.DATABASE_URL and self.TEST_DATABASE_URL == self.DATABASE_URL:
            raise ValueError("TEST_DATABASE_URL must not equal DATABASE_URL")

        database_name = urlsplit(self.TEST_DATABASE_URL).path.rsplit("/", 1)[-1]
        if "test" not in database_name.lower():
            raise ValueError("TEST_DATABASE_URL database name must contain 'test'")
        return self

    @property
    def active_database_url(self) -> str:
        if self.ENVIRONMENT == "test":
            if not self.TEST_DATABASE_URL:
                raise RuntimeError("TEST_DATABASE_URL is required in test mode")
            return self.TEST_DATABASE_URL
        if not self.DATABASE_URL:
            raise RuntimeError("DATABASE_URL is required outside test mode")
        return self.DATABASE_URL


@lru_cache
def get_settings() -> Settings:
    return Settings()
