from google import genai
from google.genai import types

from src.core.config import Settings
from src.core.exceptions import ProviderUnavailableError
from src.integrations.ai.base import (
    AIUsage,
    StructuredAIRequest,
    StructuredAIResult,
)


class GeminiAIProvider:
    def __init__(self, settings: Settings) -> None:
        self._model = settings.GEMINI_MODEL
        self._client = genai.Client(
            api_key=settings.GOOGLE_API_KEY,
            http_options=types.HttpOptions(
                timeout=settings.AI_PROVIDER_TIMEOUT_SECONDS * 1000,
                retry_options=types.HttpRetryOptions(
                    attempts=settings.AI_PROVIDER_ATTEMPTS,
                ),
            ),
        )

    def generate(self, prompt: str) -> str:
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
            raise ProviderUnavailableError("Revision provider is unavailable") from exc

        if not text:
            raise ProviderUnavailableError("Revision provider returned no content")
        return text

    def generate_structured(
        self,
        request: StructuredAIRequest,
    ) -> StructuredAIResult:
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
            raise ProviderUnavailableError("Revision provider is unavailable") from exc

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
