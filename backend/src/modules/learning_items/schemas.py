from datetime import datetime

from typing import Literal
import re
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DeleteLearningItem(BaseModel):
    id: int


class QuestionOptionResponse(BaseModel):
    label: str
    text: str
    isCorrect: bool


class QuestionResponse(BaseModel):
    question_id: int
    number: int
    question: str
    options: list[QuestionOptionResponse]
    explanation: str | None
    difficulty: int
    expected_time_seconds: int
    total_attempts: int
    correct_attempts: int
    accuracy_percent: float | None


class ManualQuestionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=5000)
    option_a: str = Field(min_length=1, max_length=255)
    option_b: str = Field(min_length=1, max_length=255)
    option_c: str = Field(min_length=1, max_length=255)
    option_d: str = Field(min_length=1, max_length=255)
    correct_option: Literal["A", "B", "C", "D"]
    explanation: str = Field(min_length=1, max_length=10000)
    difficulty: int = Field(ge=1, le=3)
    expected_time_seconds: int = Field(gt=0, le=3600)

    @field_validator(
        "question", "option_a", "option_b", "option_c", "option_d", "explanation"
    )
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value

    @field_validator("option_d")
    @classmethod
    def require_distinct_options(cls, value: str, info) -> str:
        options = [info.data.get(name) for name in ("option_a", "option_b", "option_c")] + [value]
        normalized = {
            re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(option)).casefold()).strip()
            for option in options
        }
        if len(normalized) != 4:
            raise ValueError("options must be distinct")
        return value


class ManualQuestionCreatedResponse(BaseModel):
    message: str
    question_id: int


class PdfResourceResponse(BaseModel):
    id: int
    url: str
    original_filename: str | None = None


class PdfNoteCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    media_id: int = Field(gt=0)
    page_number: int = Field(gt=0, le=100_000)
    note_text: str = Field(min_length=1, max_length=4000)
    source_excerpt: str | None = Field(default=None, max_length=500)

    @field_validator("note_text")
    @classmethod
    def trim_note_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("note_text must not be blank")
        return value

    @field_validator("source_excerpt")
    @classmethod
    def trim_excerpt(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class PdfNoteUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note_text: str = Field(min_length=1, max_length=4000)
    source_excerpt: str | None = Field(default=None, max_length=500)

    _trim_note_text = field_validator("note_text")(PdfNoteCreateRequest.trim_note_text.__func__)
    _trim_excerpt = field_validator("source_excerpt")(PdfNoteCreateRequest.trim_excerpt.__func__)


class PdfNoteResponse(BaseModel):
    id: int
    learning_item_id: int
    media_id: int
    page_number: int
    source_excerpt: str | None
    note_text: str
    created_at: datetime
    updated_at: datetime


class PdfNotesResponse(BaseModel):
    notes: list[PdfNoteResponse]


class LearningItemView(BaseModel):
    id: int
    title: str
    description_text: str | None
    labels: str | None
    image_urls: str | None
    pdf_urls: str | None
    pdf_resources: list[PdfResourceResponse] = Field(default_factory=list)
    first_image_url: str | None
    image_count: int
    pdf_count: int
    hours_ago: int
    theory: str | None = None
    key_points: list[str] = Field(default_factory=list)
    questions: list[QuestionResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class LearningItemViewResponse(BaseModel):
    message: str
    data: LearningItemView


class LearningItemSummary(BaseModel):
    id: int
    title: str
    description_text: str | None
    labels: str | None
    image_urls: str | None
    first_image_url: str | None
    image_count: int
    pdf_count: int
    hours_ago: int


class LearningItemsSummaryResponse(BaseModel):
    message: str
    data: list[LearningItemSummary]


class LearningItemCreatedResponse(BaseModel):
    message: str
