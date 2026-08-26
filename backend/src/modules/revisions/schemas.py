from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    field_validator,
    model_validator,
)


class GenerateRevisionRequest(BaseModel):
    learning_item_id: int
    title: str
    description: str


class GeneratedQuestion(BaseModel):
    question: str = Field(min_length=1)
    options: list[str] = Field(min_length=4, max_length=4)
    correct_answer: str
    explanation: str
    expected_time: int = Field(gt=0)
    difficulty_level: int = Field(ge=1, le=3)

    @field_validator("correct_answer", mode="before")
    @classmethod
    def normalize_correct_answer(cls, value: object) -> str:
        normalized = str(value)
        if normalized not in {"0", "1", "2", "3"}:
            raise ValueError("correct_answer must be an index from 0 to 3")
        return normalized


class GeneratedRevisionResponse(BaseModel):
    theory: str = Field(min_length=1)
    key_points: list[str] = Field(min_length=1)
    questions: list[GeneratedQuestion] = Field(min_length=1)


class RevisionGenerationResponse(BaseModel):
    message: str


class RandomRevisionSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quiz_type: Literal["RANDOM"]
    question_count: int = Field(ge=1, le=50)
    allow_ai_generation: bool = False


class LabelRevisionSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quiz_type: Literal["LABEL"]
    label_ids: list[PositiveInt] = Field(min_length=1, max_length=10)
    questions_per_label: int = Field(ge=1, le=20)
    allow_ai_generation: bool = False

    @field_validator("label_ids")
    @classmethod
    def require_unique_labels(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("label_ids must be unique")
        return value

    @model_validator(mode="after")
    def limit_derived_question_count(self) -> "LabelRevisionSessionRequest":
        if len(self.label_ids) * self.questions_per_label > 50:
            raise ValueError("derived question_count must not exceed 50")
        return self

    @property
    def question_count(self) -> int:
        return len(self.label_ids) * self.questions_per_label


RevisionSessionRequest = Annotated[
    RandomRevisionSessionRequest | LabelRevisionSessionRequest,
    Field(discriminator="quiz_type"),
]


class RevisionSessionOptionResponse(BaseModel):
    label: Literal["A", "B", "C", "D"]
    text: str


class RevisionSessionQuestionResponse(BaseModel):
    session_question_id: int
    position: int
    question: str
    options: list[RevisionSessionOptionResponse]
    difficulty: int
    expected_time_seconds: int


class RevisionSessionLabelResponse(BaseModel):
    label_id: int | None
    label_name: str
    question_quota: int


class RevisionSessionResponse(BaseModel):
    session_id: int
    requested_strategy: Literal["RANDOM", "LABEL"]
    strategy_used: Literal["RANDOM", "LABEL"]
    question_count: int
    questions_per_label: int | None
    generated_question_count: int
    status: Literal["IN_PROGRESS", "COMPLETED"]
    labels: list[RevisionSessionLabelResponse] | None
    questions: list[RevisionSessionQuestionResponse]


class RevisionSessionLabelShortageResponse(BaseModel):
    label_id: int
    requested: int
    eligible_unique: int
    assigned: int
    shortage: int


class RevisionSessionShortageDetail(BaseModel):
    code: Literal["INSUFFICIENT_QUESTION_BANK"]
    requested_question_count: int
    assignable_question_count: int
    total_shortage: int
    label_shortages: list[RevisionSessionLabelShortageResponse] | None
    ai_generation_available: Literal[False]


class RevisionSessionShortageResponse(BaseModel):
    detail: RevisionSessionShortageDetail
