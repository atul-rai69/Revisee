from google import genai
from google.genai import types

from src.core.config import Settings
from src.core.exceptions import ProviderUnavailableError


class GeminiAIProvider:
    def __init__(self, settings: Settings) -> None:
        self._model = settings.GEMINI_MODEL
        self._client = genai.Client(api_key=settings.GOOGLE_API_KEY)

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
        except Exception as exc:
            raise ProviderUnavailableError("Revision provider is unavailable") from exc

        if not response.text:
            raise ProviderUnavailableError("Revision provider returned no content")
        return response.text
