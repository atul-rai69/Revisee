from src.integrations.ai.base import AIUsage, StructuredAIResult
from src.modules.ai_generation.models import AIGenerationEvent
from src.modules.revisions.generation.service import QuestionGenerationService


def _event() -> AIGenerationEvent:
    return AIGenerationEvent(
        user_id=1,
        operation_type="SESSION_SHORTAGE",
        prompt_template_version="question-only-v1",
        status="PROCESSING",
        requested_count=1,
    )


def test_actual_provider_usage_is_not_marked_as_estimated() -> None:
    event = _event()
    result = StructuredAIResult(
        text="{}",
        provider="fake",
        model="model",
        response_id="response",
        usage=AIUsage(input_tokens=11, output_tokens=22, total_tokens=33),
    )

    QuestionGenerationService._apply_result_metadata(event, "x" * 100, result)

    assert event.input_tokens == 11
    assert event.estimated_input_tokens is None
    assert event.input_token_count_estimated is False


def test_missing_actual_input_usage_uses_separate_estimate_field() -> None:
    event = _event()
    result = StructuredAIResult(
        text="{}",
        provider="fake",
        model=None,
        response_id=None,
        usage=AIUsage(),
    )

    QuestionGenerationService._apply_result_metadata(event, "x" * 101, result)

    assert event.input_tokens is None
    assert event.estimated_input_tokens == 26
    assert event.input_token_count_estimated is True
