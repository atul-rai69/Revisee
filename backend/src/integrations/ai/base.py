from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class AIOperation(StrEnum):
    LEARNING_ITEM_CREATE = "LEARNING_ITEM_CREATE"
    LEARNING_ITEM_REGENERATE = "LEARNING_ITEM_REGENERATE"
    LEARNING_ITEM_QUESTIONS = "LEARNING_ITEM_QUESTIONS"
    SESSION_SHORTAGE = "SESSION_SHORTAGE"
    LABEL_PROACTIVE = "LABEL_PROACTIVE"


@dataclass(frozen=True, slots=True)
class StructuredAIRequest:
    prompt: str
    operation: AIOperation
    max_output_tokens: int


@dataclass(frozen=True, slots=True)
class AIUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cached_tokens: int | None = None
    thought_tokens: int | None = None
    tool_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class StructuredAIResult:
    text: str
    provider: str
    model: str | None
    response_id: str | None
    usage: AIUsage


class AIProvider(Protocol):
    def generate(self, prompt: str) -> str:
        """Return the provider's raw structured-text response."""
        ...

    def generate_structured(
        self,
        request: StructuredAIRequest,
    ) -> StructuredAIResult:
        """Return provider-neutral structured content and usage metadata."""
        ...
