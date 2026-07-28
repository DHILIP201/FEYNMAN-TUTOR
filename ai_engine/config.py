"""
Feynman Cognitive Engine — Centralized Configuration
"""

import os
from pydantic import BaseModel

class EngineConfig(BaseModel):
    provider_name: str = os.getenv("AI_PROVIDER", "gemini")
    model_name: str = os.getenv("AI_MODEL_NAME", "gemini-2.5-flash")
    temperature: float = 0.7
    max_output_tokens: int = 8192
    retry_attempts: int = 3
    embedding_model: str = "models/gemini-embedding-001"

engine_config = EngineConfig()
