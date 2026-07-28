"""
Feynman Cognitive Engine — Gemini LLM Provider Implementation
"""

import os
from typing import Dict, Any, Optional
from google import genai
from .base_provider import BaseProvider

class GeminiProvider(BaseProvider):
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.model_name = model_name

    async def generate(self, prompt: str, schema: Any = None) -> Dict[str, Any]:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY missing from environment.")
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=self.model_name,
            contents=prompt
        )
        return {"raw_text": response.text}
