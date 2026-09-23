from types import SimpleNamespace

import pytest

from src.core.exceptions import ProviderUnavailableError
from src.integrations.ai.base import AIOperation, StructuredAIRequest
from src.integrations.ai.gemini import GeminiAIProvider
from src.core.exceptions import InvalidProviderCredentialError, ProviderQuotaError


class _Models:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.requests = []

    def generate_content(self, **kwargs):
        self.requests.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def _provider(models: _Models) -> GeminiAIProvider:
    provider = object.__new__(GeminiAIProvider)
    provider._model = "configured-model"
    provider._client = SimpleNamespace(models=models)
    return provider


def _request() -> StructuredAIRequest:
    return StructuredAIRequest(
        prompt="prompt",
        operation=AIOperation.SESSION_SHORTAGE,
        max_output_tokens=1_234,
    )


def test_structured_provider_maps_all_available_metadata() -> None:
    metadata = SimpleNamespace(
        prompt_token_count=10,
        candidates_token_count=20,
        total_token_count=35,
        cached_content_token_count=2,
        thoughts_token_count=3,
        tool_use_prompt_token_count=4,
    )
    models = _Models(
        SimpleNamespace(
            text='{"questions": []}',
            usage_metadata=metadata,
            model_version="gemini-version",
            response_id="response-1",
        )
    )

    result = _provider(models).generate_structured(_request())

    assert result.provider == "gemini"
    assert result.model == "gemini-version"
    assert result.response_id == "response-1"
    assert result.usage.input_tokens == 10
    assert result.usage.output_tokens == 20
    assert result.usage.total_tokens == 35
    assert result.usage.cached_tokens == 2
    assert result.usage.thought_tokens == 3
    assert result.usage.tool_tokens == 4
    assert models.requests[0]["config"].max_output_tokens == 1_234


def test_missing_provider_metadata_remains_none() -> None:
    response = SimpleNamespace(
        text='{"questions": []}',
        usage_metadata=None,
        model_version=None,
        response_id=None,
    )
    result = _provider(_Models(response)).generate_structured(_request())

    assert result.model is None
    assert result.response_id is None
    assert result.usage.input_tokens is None
    assert result.usage.total_tokens is None


def test_provider_exception_is_sanitized() -> None:
    provider = _provider(_Models(error=RuntimeError("secret provider URL and key")))

    with pytest.raises(ProviderUnavailableError) as error:
        provider.generate_structured(_request())

    assert str(error.value) == "Revision provider is unavailable"
    assert "secret" not in str(error.value)


def test_legacy_generate_contract_is_preserved() -> None:
    provider = _provider(
        _Models(
            SimpleNamespace(
                text='{"theory": "legacy"}',
                usage_metadata=None,
                model_version=None,
                response_id=None,
            )
        )
    )
    assert provider.generate("legacy prompt") == '{"theory": "legacy"}'


class _ProviderStatusError(RuntimeError):
    def __init__(self, code: int) -> None:
        self.code = code
        super().__init__("sensitive provider detail")


def test_personal_key_and_quota_errors_are_distinguished_without_leaking_details() -> None:
    invalid = _provider(_Models(error=_ProviderStatusError(401)))
    invalid._personal_credential = True
    with pytest.raises(InvalidProviderCredentialError) as invalid_error:
        invalid.generate_structured(_request())
    assert "sensitive" not in invalid_error.value.detail

    quota = _provider(_Models(error=_ProviderStatusError(429)))
    quota._personal_credential = True
    with pytest.raises(ProviderQuotaError) as quota_error:
        quota.generate_structured(_request())
    assert "sensitive" not in quota_error.value.detail
