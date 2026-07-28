"""
Feynman Cognitive Engine — Ollama/Local LLM Provider Implementation
"""

import urllib.request
import json
from typing import Dict, Any
from .base_provider import BaseProvider

class OllamaProvider(BaseProvider):
    def __init__(self, model_name: str = "llama3:latest", host: str = "http://localhost:11434"):
        self.model_name = model_name
        self.host = host

    async def generate(self, prompt: str, schema: Any = None) -> Dict[str, Any]:
        """
        Executes local Ollama model generation via HTTP POST endpoint.
        """
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False
        }
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                res_body = response.read().decode('utf-8')
                res_json = json.loads(res_body)
                return {"raw_text": res_json.get("response", "")}
        except Exception as err:
            print(f"[OLLAMA PROVIDER NOTICE] Local model offline ({err}). Provider fallback active.")
            raise RuntimeError(f"Ollama local service unavailable: {err}")
