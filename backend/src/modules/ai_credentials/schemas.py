from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CredentialUsageResponse(BaseModel):
    request_count: int
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    updated_at: datetime | None


class CredentialResponse(BaseModel):
    id: int
    provider: Literal["GEMINI"]
    name: str
    masked_identifier: str
    status: Literal["VALID", "INVALID"]
    is_default: bool
    last_validated_at: datetime
    last_used_at: datetime | None
    created_at: datetime
    usage: CredentialUsageResponse


class CredentialListResponse(BaseModel):
    credentials: list[CredentialResponse]
    provider_console_url: str
    quota_remaining_available: Literal[False] = False


class CredentialCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["GEMINI"] = "GEMINI"
    name: str = Field(min_length=1, max_length=80)
    api_key: str = Field(min_length=10, max_length=500)
    make_default: bool = False

    @field_validator("name", "api_key")
    @classmethod
    def trim_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value


class CredentialUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=80)
    api_key: str | None = Field(default=None, min_length=10, max_length=500)
    make_default: bool | None = None

    @field_validator("name", "api_key")
    @classmethod
    def trim_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value

    @model_validator(mode="after")
    def require_change(self) -> "CredentialUpdateRequest":
        if self.name is None and self.api_key is None and self.make_default is None:
            raise ValueError("at least one field is required")
        return self


class GenerationChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generation_source: Literal["REVISEE", "PERSONAL"] = "REVISEE"
    credential_id: int | None = Field(default=None, gt=0)
    personal_remarks: str | None = Field(default=None, max_length=2000)

    @field_validator("personal_remarks")
    @classmethod
    def normalize_remarks(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def validate_choice(self) -> "GenerationChoice":
        if self.generation_source == "PERSONAL" and self.credential_id is None:
            raise ValueError("credential_id is required for personal generation")
        if self.generation_source == "REVISEE" and self.credential_id is not None:
            raise ValueError("credential_id is only valid for personal generation")
        if self.generation_source == "REVISEE" and self.personal_remarks is not None:
            raise ValueError("personal remarks require a personal credential")
        return self
