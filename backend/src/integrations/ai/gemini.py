from functools import lru_cache
from threading import BoundedSemaphore

from google import genai
from google.genai import types

from src.core.config import Settings
from src.core.exceptions import (
    InvalidProviderCredentialError,
    ProviderBusyError,
    ProviderOutageError,
    ProviderQuotaError,
    ProviderUnavailableError,
)
from src.integrations.ai.base import (
    AIUsage,
    StructuredAIRequest,
    StructuredAIResult,
)


@lru_cache(maxsize=8)
def _request_gate(maximum_concurrency: int) -> BoundedSemaphore:
    return BoundedSemaphore(maximum_concurrency)


class GeminiAIProvider:
    def __init__(
        self,
        settings: Settings,
        *,
        api_key: str | None = None,
        personal_credential: bool = False,
    ) -> None:
        self._model = settings.GEMINI_MODEL
        self._personal_credential = personal_credential
        self._gate = _request_gate(settings.AI_MAX_CONCURRENT_PROVIDER_REQUESTS)
        self._client = genai.Client(
            api_key=api_key or settings.GOOGLE_API_KEY,
            http_options=types.HttpOptions(
                timeout=settings.AI_PROVIDER_TIMEOUT_SECONDS * 1000,
                retry_options=types.HttpRetryOptions(
                    attempts=settings.AI_PROVIDER_ATTEMPTS,
                ),
            ),
        )

    def generate(self, prompt: str) -> str:
        gate = getattr(self, "_gate", _request_gate(2))
        if not gate.acquire(timeout=1):
            raise ProviderBusyError()
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    thinking_config=types.ThinkingConfig(thinking_budget=256),
                ),
            )
            text = response.text
        except Exception as exc:
            raise self._provider_error(exc) from exc
        finally:
            gate.release()

        if not text:
            raise ProviderUnavailableError("Revision provider returned no content")
        return text

    def generate_structured(
        self,
        request: StructuredAIRequest,
    ) -> StructuredAIResult:
        gate = getattr(self, "_gate", _request_gate(2))
        if not gate.acquire(timeout=1):
            raise ProviderBusyError()
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=request.prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    max_output_tokens=request.max_output_tokens,
                    thinking_config=types.ThinkingConfig(thinking_budget=256),
                ),
            )
            text = response.text
            metadata = response.usage_metadata
            model = response.model_version
            response_id = response.response_id
        except Exception as exc:
            raise self._provider_error(exc) from exc
        finally:
            gate.release()

        if not text:
            raise ProviderUnavailableError("Revision provider returned no content")

        usage = AIUsage(
            input_tokens=(metadata.prompt_token_count if metadata else None),
            output_tokens=(metadata.candidates_token_count if metadata else None),
            total_tokens=(metadata.total_token_count if metadata else None),
            cached_tokens=(
                metadata.cached_content_token_count if metadata else None
            ),
            thought_tokens=(metadata.thoughts_token_count if metadata else None),
            tool_tokens=(
                metadata.tool_use_prompt_token_count if metadata else None
            ),
        )
        return StructuredAIResult(
            text=text,
            provider="gemini",
            model=model,
            response_id=response_id,
            usage=usage,
        )

    def validate_credential(self) -> None:
        """Verify authentication without sending user learning content."""
        gate = getattr(self, "_gate", _request_gate(2))
        if not gate.acquire(timeout=1):
            raise ProviderBusyError()
        try:
            self._client.models.get(model=self._model)
        except Exception as exc:
            raise self._provider_error(exc) from exc
        finally:
            gate.release()

    def _provider_error(self, exc: Exception) -> Exception:
        status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
        try:
            status_code = int(status)
        except (TypeError, ValueError):
            status_code = None
        if getattr(self, "_personal_credential", False) and status_code in {400, 401, 403}:
            return InvalidProviderCredentialError()
        if status_code == 429:
            return ProviderQuotaError()
        return ProviderOutageError("Revision provider is unavailable")
