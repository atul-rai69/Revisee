from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator


AnswerOption = Literal["A", "B", "C", "D"]


class RevisionAnswerSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_question_id: int = Field(strict=True, gt=0)
    selected_option: AnswerOption
    time_taken_seconds: int = Field(strict=True, ge=0, le=3600)


class RevisionSessionSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: list[RevisionAnswerSubmission] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def require_unique_session_questions(self) -> "RevisionSessionSubmitRequest":
        ids = [answer.session_question_id for answer in self.answers]
        if len(ids) != len(set(ids)):
            raise ValueError("session_question_id values must be unique")
        return self


class CompletedRevisionOptionResponse(BaseModel):
    label: AnswerOption
    text: str


class CompletedRevisionQuestionResponse(BaseModel):
    session_question_id: int
    position: int
    learning_item_title: str
    question: str
    options: list[CompletedRevisionOptionResponse]
    selected_option: AnswerOption
    correct_option: AnswerOption
    is_correct: bool
    explanation: str | None
    difficulty: int
    expected_time_seconds: int
    time_taken_seconds: int
    mastery_delta: Decimal

    @field_serializer("mastery_delta")
    def serialize_mastery_delta(self, value: Decimal) -> float:
        return float(value)


class CompletedRevisionLabelResponse(BaseModel):
    label_id: int | None
    label_name: str
    question_quota: int


class RevisionSessionResultResponse(BaseModel):
    session_id: int
    status: Literal["COMPLETED"]
    requested_strategy: Literal["RANDOM", "LABEL", "SMART"]
    strategy_used: Literal["RANDOM", "LABEL", "SMART"]
    started_at: datetime | None
    completed_at: datetime
    question_count: int
    correct_count: int
    incorrect_count: int
    score_percentage: Decimal
    total_time_taken_seconds: int
    labels: list[CompletedRevisionLabelResponse] | None
    questions: list[CompletedRevisionQuestionResponse]

    @field_serializer("score_percentage")
    def serialize_score_percentage(self, value: Decimal) -> float:
        return float(value)


class RevisionSessionErrorDetail(BaseModel):
    code: Literal[
        "ANSWER_SET_MISMATCH",
        "REVISION_SESSION_ALREADY_COMPLETED",
        "REVISION_SESSION_NOT_COMPLETED",
        "REVISION_SESSION_RESULT_UNAVAILABLE",
    ]
    message: str


class RevisionSessionErrorResponse(BaseModel):
    detail: RevisionSessionErrorDetail
