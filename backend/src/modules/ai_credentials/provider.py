from typing import Protocol

from src.core.config import Settings
from src.integrations.ai.base import AIProvider
from src.integrations.ai.gemini import GeminiAIProvider


class PersonalAIProviderFactory(Protocol):
    def validate(self, api_key: str) -> None: ...

    def create(self, api_key: str) -> AIProvider: ...


class GeminiPersonalAIProviderFactory:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def validate(self, api_key: str) -> None:
        GeminiAIProvider(
            self.settings,
            api_key=api_key,
            personal_credential=True,
        ).validate_credential()

    def create(self, api_key: str) -> AIProvider:
        return GeminiAIProvider(
            self.settings,
            api_key=api_key,
            personal_credential=True,
        )
