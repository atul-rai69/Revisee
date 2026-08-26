import json
from dataclasses import dataclass
import re
from typing import Any
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from src.core.exceptions import ProviderOutputError


class ValidatedGeneratedQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    question: str = Field(min_length=1)
    options: tuple[str, str, str, str]
    correct_answer: str
    difficulty_level: int = Field(ge=1, le=3)
    expected_time_seconds: int = Field(gt=0)
    explanation: str = Field(min_length=1)

    @field_validator("question", "explanation")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("options")
    @classmethod
    def validate_options(
        cls,
        value: tuple[str, str, str, str],
    ) -> tuple[str, str, str, str]:
        normalized = tuple(option.strip() for option in value)
        if any(not option for option in normalized):
            raise ValueError("options must not be blank")
        comparison_values = {
            re.sub(
                r"\s+",
                " ",
                unicodedata.normalize("NFKC", option).casefold(),
            ).strip()
            for option in normalized
        }
        if len(comparison_values) != 4:
            raise ValueError("options must be distinct")
        return normalized

    @field_validator("correct_answer", mode="before")
    @classmethod
    def normalize_correct_answer(cls, value: object) -> str:
        normalized = str(value).strip().upper()
        letter_mapping = {"A": "0", "B": "1", "C": "2", "D": "3"}
        normalized = letter_mapping.get(normalized, normalized)
        if normalized not in {"0", "1", "2", "3"}:
            raise ValueError("correct_answer must identify one of four options")
        return normalized

    @field_validator("expected_time_seconds")
    @classmethod
    def bound_expected_time(cls, value: int, info) -> int:
        maximum = (info.context or {}).get("maximum_expected_time_seconds")
        if maximum is not None and value > maximum:
            raise ValueError("expected_time_seconds exceeds the configured limit")
        return value


@dataclass(frozen=True, slots=True)
class ParsedQuestionBatch:
    questions: tuple[ValidatedGeneratedQuestion, ...]
    rejected_count: int
    excess_count: int


def parse_question_response(
    raw_response: str,
    *,
    requested_count: int,
    maximum_response_characters: int,
    maximum_expected_time_seconds: int,
) -> ParsedQuestionBatch:
    if requested_count < 1:
        raise ValueError("requested_count must be positive")
    if not isinstance(raw_response, str) or not raw_response:
        raise ProviderOutputError("Revision provider returned invalid data")
    if len(raw_response) > maximum_response_characters:
        raise ProviderOutputError("Revision provider returned invalid data")

    try:
        decoded: Any = json.loads(raw_response)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ProviderOutputError("Revision provider returned invalid data") from exc
    if not isinstance(decoded, dict) or set(decoded) != {"questions"}:
        raise ProviderOutputError("Revision provider returned invalid data")
    entries = decoded["questions"]
    if not isinstance(entries, list):
        raise ProviderOutputError("Revision provider returned invalid data")

    accepted: list[ValidatedGeneratedQuestion] = []
    rejected_count = 0
    for entry in entries[:requested_count]:
        try:
            accepted.append(
                ValidatedGeneratedQuestion.model_validate(
                    entry,
                    context={
                        "maximum_expected_time_seconds": (
                            maximum_expected_time_seconds
                        )
                    },
                )
            )
        except (ValidationError, TypeError):
            rejected_count += 1

    return ParsedQuestionBatch(
        questions=tuple(accepted),
        rejected_count=rejected_count,
        excess_count=max(0, len(entries) - requested_count),
    )
