from __future__ import annotations

from app.core.config import Settings
from app.core.errors import LLMProviderUnavailableError
from app.providers.base import LLMProvider
from app.providers.fake import FakeProvider
from app.providers.groq import GroqProvider


def create_llm_provider(settings: Settings) -> LLMProvider:
    provider = settings.llm_provider.lower().strip()
    if provider == "fake":
        return FakeProvider()
    if provider == "groq":
        return GroqProvider(settings)
    raise LLMProviderUnavailableError(f"Provedor de LLM desconhecido: {settings.llm_provider}")
