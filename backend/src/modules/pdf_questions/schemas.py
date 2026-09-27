from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _validate_pdf_filename(value: str) -> str:
    value = value.strip()
    if not value or len(value) > 255:
        raise ValueError("source filename is required and must be at most 255 characters")
    if "/" in value or "\\" in value or any(ord(character) < 32 for character in value):
        raise ValueError("source filename must not contain a path")
    if not value.casefold().endswith(".pdf"):
        raise ValueError("source filename must use the .pdf extension")
    return value


class PdfSourcePage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_number: int = Field(gt=0, le=100_000)
    text: str = Field(max_length=20_000)

    @field_validator("text")
    @classmethod
    def reject_nul(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("page text contains unsupported characters")
        return value


class PdfDraftOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    A: str = Field(max_length=255)
    B: str = Field(max_length=255)
    C: str = Field(max_length=255)
    D: str = Field(max_length=255)

    def as_tuple(self) -> tuple[str, str, str, str]:
        return (self.A, self.B, self.C, self.D)


class PdfQuestionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(max_length=5_000)
    options: PdfDraftOptions
    correct_option: Literal["A", "B", "C", "D"] | None
    explanation: str | None = Field(default=None, max_length=10_000)
    difficulty: int = Field(default=2, ge=1, le=3)
    expected_time_seconds: int = Field(default=30, gt=0, le=3_600)
    source_page: int = Field(gt=0, le=100_000)
    source_excerpt: str = Field(max_length=500)
    confidence: float = Field(ge=0, le=1)
    validation_issues: list[Annotated[str, Field(max_length=300)]] = Field(
        default_factory=list,
        max_length=10,
    )


class PdfDraftGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_filename: str = Field(min_length=1, max_length=255)
    mode: Literal["PARSE", "GENERATE"] = "GENERATE"
    source_pages: list[PdfSourcePage] = Field(min_length=1, max_length=50)
    question_count: int = Field(default=5, ge=1, le=10)
    difficulty: int = Field(default=2, ge=1, le=3)
    focus_instructions: str | None = Field(default=None, max_length=2_000)
    generation_source: Literal["REVISEE", "PERSONAL"] = "REVISEE"
    credential_id: int | None = Field(default=None, gt=0)

    @field_validator("source_filename")
    @classmethod
    def validate_source_filename(cls, value: str) -> str:
        return _validate_pdf_filename(value)

    @field_validator("focus_instructions")
    @classmethod
    def normalize_focus(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def validate_provider_choice(self) -> "PdfDraftGenerationRequest":
        if self.generation_source == "PERSONAL" and self.credential_id is None:
            raise ValueError("credential_id is required for personal generation")
        if self.generation_source == "REVISEE" and self.credential_id is not None:
            raise ValueError("credential_id is only valid for personal generation")
        return self


class PdfDraftGenerationResponse(BaseModel):
    drafts: list[PdfQuestionDraft]
    requested_count: int
    returned_count: int
    rejected_count: int
    partial: bool
    coverage_page_numbers: list[int]


class PdfQuestionImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_filename: str = Field(min_length=1, max_length=255)
    destination_learning_item_id: int = Field(gt=0)
    source_pages: list[PdfSourcePage] = Field(min_length=1, max_length=50)
    questions: list[PdfQuestionDraft] = Field(min_length=1, max_length=25)

    @field_validator("source_filename")
    @classmethod
    def validate_source_filename(cls, value: str) -> str:
        return _validate_pdf_filename(value)


class PdfQuestionImportResponse(BaseModel):
    inserted_count: int
    duplicate_count: int
    rejected_count: int
    failed_count: int
    inserted_question_ids: list[int]
