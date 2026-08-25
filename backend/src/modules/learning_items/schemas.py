from datetime import datetime

from pydantic import BaseModel, Field


class DeleteLearningItem(BaseModel):
    id: int


class QuestionOptionResponse(BaseModel):
    label: str
    text: str
    isCorrect: bool


class QuestionResponse(BaseModel):
    number: int
    question: str
    options: list[QuestionOptionResponse]
    explanation: str | None
    difficulty: int
    expected_time_seconds: int


class LearningItemView(BaseModel):
    id: int
    title: str
    description_text: str | None
    labels: str | None
    image_urls: str | None
    pdf_urls: str | None
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
