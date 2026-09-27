import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


QuestionType = Literal[
    "THEORY",
    "NUMERICAL",
    "CODING",
    "APPLICATION",
    "FACT_RECALL",
    "PYQ_STYLE",
]
DifficultyMode = Literal["EASY", "MEDIUM", "HARD", "MIXED"]
GenerationGoal = Literal[
    "UNDERSTANDING",
    "EXAM_PREPARATION",
    "REVISION",
    "INTERVIEWS",
    "PRACTICAL_APPLICATION",
]
AudienceLevel = Literal["BEGINNER", "INTERMEDIATE", "ADVANCED"]
DetailLevel = Literal["CONCISE", "STANDARD", "DETAILED"]
ContentTone = Literal["ACADEMIC", "EXAM_FOCUSED", "INTERVIEW_FOCUSED", "PRACTICAL"]
ContentSection = Literal[
    "THEORY",
    "KEY_POINTS",
    "REVISION_NOTES",
    "QUESTIONS",
    "EXAMPLES",
    "FORMULA_SUMMARY",
    "CODE_EXAMPLES",
]
ProgrammingLanguage = Literal[
    "INFER_FROM_SOURCE",
    "PYTHON",
    "JAVASCRIPT",
    "TYPESCRIPT",
    "JAVA",
    "C_SHARP",
    "C_PLUS_PLUS",
    "GO",
    "RUST",
    "SQL",
]
CodingQuestionFormat = Literal[
    "OUTPUT_PREDICTION",
    "DEBUGGING",
    "CONCEPTUAL_CODE",
    "COMPLEXITY_ANALYSIS",
    "IMPLEMENTATION",
]

BoundedPreferenceText = Annotated[str, Field(min_length=1, max_length=120)]


class DifficultyDistribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit: Literal["PERCENTAGE", "COUNT"] = "PERCENTAGE"
    easy: int = Field(ge=0, le=100)
    medium: int = Field(ge=0, le=100)
    hard: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def validate_percentage_total(self) -> "DifficultyDistribution":
        if self.unit == "PERCENTAGE" and self.easy + self.medium + self.hard != 100:
            raise ValueError("difficulty percentages must total 100")
        if self.easy + self.medium + self.hard <= 0:
            raise ValueError("difficulty distribution must include at least one question")
        return self


class NumericalPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    complexity: Literal["BASIC", "INTERMEDIATE", "ADVANCED"] = "INTERMEDIATE"
    include_formulas: bool = True
    include_unit_conversions: bool = False
    step_by_step_explanations: bool = True
    allow_calculator: bool = False


class CodingPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: ProgrammingLanguage
    question_formats: list[CodingQuestionFormat] = Field(min_length=1, max_length=5)
    experience_level: Literal["BEGINNER", "INTERMEDIATE", "ADVANCED"] = "INTERMEDIATE"
    code_explanations_required: bool = True

    @field_validator("question_formats")
    @classmethod
    def unique_formats(cls, value: list[CodingQuestionFormat]) -> list[CodingQuestionFormat]:
        if len(value) != len(set(value)):
            raise ValueError("coding question formats must be unique")
        return value


class GenerationPreferences(BaseModel):
    """Request-scoped, provider-neutral generation preferences."""

    model_config = ConfigDict(extra="forbid")

    question_count: int | None = Field(default=None, ge=1, le=10)
    question_types: list[QuestionType] | None = Field(default=None, min_length=1, max_length=6)
    difficulty_mode: DifficultyMode | None = None
    difficulty_distribution: DifficultyDistribution | None = None
    explanations_required: bool | None = None
    preferred_expected_time_seconds: int | None = Field(default=None, ge=1, le=3600)
    generation_goal: GenerationGoal | None = None
    audience_level: AudienceLevel | None = None
    detail_level: DetailLevel | None = None
    tone: ContentTone | None = None
    content_sections: list[ContentSection] | None = Field(default=None, min_length=1, max_length=7)
    numerical_preferences: NumericalPreferences | None = None
    coding_preferences: CodingPreferences | None = None
    focus_areas: list[BoundedPreferenceText] = Field(default_factory=list, max_length=10)
    avoid_areas: list[BoundedPreferenceText] = Field(default_factory=list, max_length=10)
    additional_instructions: str | None = Field(default=None, max_length=2000)
    output_language: Literal["ENGLISH"] | None = None

    @field_validator("question_types", "content_sections")
    @classmethod
    def unique_selections(cls, value):
        if value is not None and len(value) != len(set(value)):
            raise ValueError("preference selections must be unique")
        return value

    @field_validator("focus_areas", "avoid_areas")
    @classmethod
    def normalize_areas(cls, value: list[str]) -> list[str]:
        normalized = [entry.strip() for entry in value]
        if any(not entry for entry in normalized):
            raise ValueError("focus and avoidance areas must not be blank")
        return normalized

    @field_validator("additional_instructions")
    @classmethod
    def normalize_instructions(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        normalized = re.sub(r"\s+", " ", value.casefold())
        authenticity = r"(?:genuine|authentic|actual|real)"
        previous_year = r"(?:pyq|previous[- ]year|past[- ]year)"
        request_verb = r"(?:generate|create|label|call|present|claim)"
        if (
            re.search(rf"{request_verb}.{{0,50}}{authenticity}.{{0,30}}{previous_year}", normalized)
            or re.search(rf"{request_verb}.{{0,50}}{previous_year}.{{0,30}}{authenticity}", normalized)
        ):
            raise ValueError(
                "generated questions cannot be claimed as genuine previous-year questions"
            )
        return value or None

    @model_validator(mode="after")
    def validate_dependencies(self) -> "GenerationPreferences":
        types = set(self.question_types or [])
        if self.difficulty_distribution is not None and self.difficulty_mode != "MIXED":
            raise ValueError("difficulty_distribution requires MIXED difficulty")
        if self.numerical_preferences is not None and "NUMERICAL" not in types:
            raise ValueError("numerical_preferences require NUMERICAL question type")
        if self.coding_preferences is not None and "CODING" not in types:
            raise ValueError("coding_preferences require CODING question type")
        if (
            self.explanations_required is False
            and self.numerical_preferences is not None
            and self.numerical_preferences.step_by_step_explanations
        ):
            raise ValueError("step-by-step numerical working requires explanations")
        if (
            self.explanations_required is False
            and self.coding_preferences is not None
            and self.coding_preferences.code_explanations_required
        ):
            raise ValueError("code explanations require explanations")
        return self

    def validate_for_question_count(self, question_count: int) -> None:
        distribution = self.difficulty_distribution
        if distribution is not None and distribution.unit == "COUNT":
            if distribution.easy + distribution.medium + distribution.hard != question_count:
                raise ValueError("difficulty counts must total question_count")

    def validate_question_only(self) -> None:
        if self.content_sections not in (None, ["QUESTIONS"]):
            raise ValueError("content_sections are not supported for question-only generation")


DEFAULT_CONTENT_SECTIONS: tuple[ContentSection, ...] = (
    "THEORY",
    "KEY_POINTS",
    "QUESTIONS",
)


def effective_question_count(
    preferences: GenerationPreferences | None,
    fallback: int = 5,
) -> int:
    return preferences.question_count if preferences and preferences.question_count else fallback
