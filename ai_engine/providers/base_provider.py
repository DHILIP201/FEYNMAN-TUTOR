"""
Feynman Cognitive Engine — Provider Abstraction Layer
"""

from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, schema: Any = None) -> Dict[str, Any]:
        """
        Abstract method to execute LLM generation and return structured output dictionary.
        """
        pass
