from pydantic import BaseModel, Field, field_validator


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
