"""
Feynman Cognitive Engine — Provider Factory Pattern
"""

from typing import Dict, Type
from .base_provider import BaseProvider
from .gemini_provider import GeminiProvider
from .ollama_provider import OllamaProvider

class ProviderFactory:
    _providers: Dict[str, Type[BaseProvider]] = {
        "gemini": GeminiProvider,
        "ollama": OllamaProvider,
        "llama": OllamaProvider
    }

    @classmethod
    def register_provider(cls, name: str, provider_cls: Type[BaseProvider]):
        cls._providers[name.lower()] = provider_cls

    @classmethod
    def create(cls, name: str = "gemini", model_name: str = "gemini-2.5-flash") -> BaseProvider:
        provider_cls = cls._providers.get(name.lower(), GeminiProvider)
        return provider_cls(model_name=model_name)
