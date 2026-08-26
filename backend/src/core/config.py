from functools import lru_cache
from pathlib import Path
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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=5, gt=0)
    SESSION_EXPIRE_MINUTES: int = Field(default=30, gt=0)

    GOOGLE_API_KEY: str = Field(min_length=1)
    GEMINI_MODEL: str = "gemini-2.5-flash"

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

    CLOUDINARY_CLOUD_NAME: str = Field(min_length=1)
    CLOUDINARY_API_KEY: str = Field(min_length=1)
    CLOUDINARY_API_SECRET: str = Field(min_length=1)

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
    def validate_test_database(self) -> "Settings":
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
