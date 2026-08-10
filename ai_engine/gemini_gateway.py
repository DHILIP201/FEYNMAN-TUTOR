"""
Feynman Cognitive Engine — Multi-Credential Gemini API Gateway
Manages a backend credential pool, failure detection, slot cooldowns, exponential retries, and fallback integration.
"""

import os
import time
import asyncio
import json
import uuid
import logging
from typing import Dict, Any, List, Optional
from google import genai
from google.genai import types as genai_types

logger = logging.getLogger("GeminiGateway")


class KeySlotStatus:
    HEALTHY = "HEALTHY"
    COOLDOWN = "COOLDOWN"
    QUARANTINED = "QUARANTINED"


class KeySlot:
    def __init__(self, slot_id: int, api_key: str):
        self.slot_id = slot_id
        self.api_key = api_key
        self.status = KeySlotStatus.HEALTHY
        self.failure_count = 0
        self.cooldown_until: float = 0.0
        self.last_used: float = 0.0
        self.last_success: float = 0.0
        self.client: Optional[genai.Client] = None
        self._init_client()

    def _init_client(self):
        try:
            if self.api_key and self.api_key.strip():
                self.client = genai.Client(api_key=self.api_key.strip())
            else:
                self.client = None
        except Exception as e:
            logger.error(f"[GeminiGateway] slot={self.slot_id} client init failed: {e}")
            self.client = None

    def is_available(self) -> bool:
        if not self.api_key or not self.client:
            return False
        now = time.time()
        if self.status == KeySlotStatus.QUARANTINED:
            return False
        if self.status == KeySlotStatus.COOLDOWN:
            if now >= self.cooldown_until:
                self.status = KeySlotStatus.HEALTHY
                self.failure_count = 0
                return True
            return False
        return True

    def mark_success(self):
        self.status = KeySlotStatus.HEALTHY
        self.failure_count = 0
        self.last_success = time.time()
        self.last_used = time.time()

    def mark_rate_limited(self, retry_after_seconds: float = 60.0):
        self.status = KeySlotStatus.COOLDOWN
        self.failure_count += 1
        self.last_used = time.time()
        self.cooldown_until = time.time() + retry_after_seconds

    def mark_quarantined(self):
        self.status = KeySlotStatus.QUARANTINED
        self.failure_count += 1
        self.last_used = time.time()

    def mark_transient_failure(self):
        self.failure_count += 1
        self.last_used = time.time()


class GeminiKeyPool:
    """Manages pool of multiple Gemini API keys/credentials with slot status and failover."""

    def __init__(self, keys: Optional[List[str]] = None):
        self.slots: List[KeySlot] = []
        self._current_index = 0
        self.load_keys(keys)

    def load_keys(self, custom_keys: Optional[List[str]] = None):
        raw_keys = []
        if custom_keys is not None:
            raw_keys = [k for k in custom_keys if k and k.strip()]
        else:
            # Load GEMINI_API_KEY_1, GEMINI_API_KEY_2, GEMINI_API_KEY_3, fallback to GEMINI_API_KEY
            for key_env in ("GEMINI_API_KEY_1", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3"):
                val = os.getenv(key_env)
                if val and val.strip() and val.strip() not in raw_keys:
                    raw_keys.append(val.strip())
            
            # Fallback legacy GEMINI_API_KEY if not in pool
            legacy_key = os.getenv("GEMINI_API_KEY")
            if legacy_key and legacy_key.strip() and legacy_key.strip() not in raw_keys:
                raw_keys.append(legacy_key.strip())

        self.slots = [KeySlot(slot_id=i + 1, api_key=k) for i, k in enumerate(raw_keys)]
        self._current_index = 0

    def get_available_slots(self) -> List[KeySlot]:
        return [s for s in self.slots if s.is_available()]

    def get_next_slot(self) -> Optional[KeySlot]:
        avail = self.get_available_slots()
        if not avail:
            return None
        # Round-robin across available healthy slots
        slot = avail[self._current_index % len(avail)]
        self._current_index = (self._current_index + 1) % len(avail)
        return slot

    def get_pool_status(self) -> List[Dict[str, Any]]:
        return [
            {
                "slot_id": s.slot_id,
                "status": s.status,
                "failure_count": s.failure_count,
                "cooldown_remaining_sec": max(0.0, s.cooldown_until - time.time()) if s.status == KeySlotStatus.COOLDOWN else 0.0,
                "is_available": s.is_available()
            }
            for s in self.slots
        ]


class GeminiGateway:
    """Production Gemini API Gateway orchestrating multi-key failover and resilient retries."""

    def __init__(self, key_pool: Optional[GeminiKeyPool] = None):
        self.key_pool = key_pool or GeminiKeyPool()
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
        self.max_retries = int(os.getenv("GEMINI_MAX_RETRIES", "3"))
        self.timeout_seconds = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "45"))
        self.backoff_base = float(os.getenv("GEMINI_BACKOFF_BASE_SECONDS", "1.0"))
        self.last_usage: Dict[str, int] = {}

    def get_last_token_count(self) -> int:
        return self.last_usage.get("total_tokens", 0)

    async def generate(
        self,
        contents: List[Any],
        system_instruction: str,
        response_schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.7,
        request_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Executes generation against the Gemini credential pool with automatic failover across slots.
        Returns the raw string output or None if all slots failed.
        """
        req_id = request_id or str(uuid.uuid4())[:8]
        available_slots = self.key_pool.get_available_slots()

        if not available_slots:
            print(f"[GeminiGateway] request_id={req_id} status=NO_AVAILABLE_KEYS action=fallback")
            return None

        # Build generation config
        gen_config = genai_types.GenerateContentConfig(
            temperature=temperature,
            system_instruction=system_instruction,
            response_mime_type="application/json" if response_schema else None,
            response_schema=response_schema if response_schema else None
        )

        for slot in available_slots:
            if not slot.is_available():
                continue

            for attempt in range(1, self.max_retries + 1):
                t_start = time.time()
                try:
                    # Run sync generate_content in async worker thread with timeout
                    loop = asyncio.get_event_loop()
                    response = await asyncio.wait_for(
                        loop.run_in_executor(
                            None,
                            lambda: slot.client.models.generate_content(
                                model=self.model_name,
                                contents=contents,
                                config=gen_config
                            )
                        ),
                        timeout=float(self.timeout_seconds)
                    )

                    latency_ms = int((time.time() - t_start) * 1000)
                    slot.mark_success()

                    # Extract actual token usage metadata if provided by Gemini
                    prompt_tokens = 0
                    candidate_tokens = 0
                    total_tokens = 0
                    if hasattr(response, "usage_metadata") and response.usage_metadata:
                        prompt_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                        candidate_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
                        total_tokens = getattr(response.usage_metadata, "total_token_count", 0) or (prompt_tokens + candidate_tokens)
                    
                    self.last_usage = {
                        "prompt_tokens": prompt_tokens,
                        "candidate_tokens": candidate_tokens,
                        "total_tokens": total_tokens
                    }

                    print(
                        f"[GeminiGateway] request_id={req_id} key_slot={slot.slot_id} "
                        f"model={self.model_name} attempt={attempt} status=200 "
                        f"latency_ms={latency_ms} tokens={total_tokens} action=success"
                    )
                    if response and hasattr(response, "text") and response.text:
                        return response.text
                    return None

                except asyncio.TimeoutError:
                    latency_ms = int((time.time() - t_start) * 1000)
                    slot.mark_transient_failure()
                    print(
                        f"[GeminiGateway] request_id={req_id} key_slot={slot.slot_id} "
                        f"attempt={attempt} status=TIMEOUT latency_ms={latency_ms} action=failover"
                    )
                    break # Switch to next slot on timeout

                except Exception as exc:
                    latency_ms = int((time.time() - t_start) * 1000)
                    err_str = str(exc)

                    # Error classification
                    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                        # Extract retry delay if available
                        retry_delay = 60.0
                        slot.mark_rate_limited(retry_delay)
                        print(
                            f"[GeminiGateway] request_id={req_id} key_slot={slot.slot_id} "
                            f"attempt={attempt} status=429 latency_ms={latency_ms} action=cooldown retry_after={retry_delay}s"
                        )
                        break # Switch to next slot immediately

                    elif "401" in err_str or "403" in err_str or "API_KEY_INVALID" in err_str:
                        slot.mark_quarantined()
                        print(
                            f"[GeminiGateway] request_id={req_id} key_slot={slot.slot_id} "
                            f"status=AUTH_ERROR latency_ms={latency_ms} action=quarantine"
                        )
                        break # Quarantined; switch to next slot

                    elif "503" in err_str or "UNAVAILABLE" in err_str or "500" in err_str or "502" in err_str or "504" in err_str:
                        slot.mark_transient_failure()
                        if attempt < self.max_retries:
                            sleep_time = self.backoff_base * (2 ** (attempt - 1))
                            print(
                                f"[GeminiGateway] request_id={req_id} key_slot={slot.slot_id} "
                                f"attempt={attempt} status=5xx latency_ms={latency_ms} action=retry backoff={sleep_time:.1f}s"
                            )
                            await asyncio.sleep(sleep_time)
                        else:
                            print(
                                f"[GeminiGateway] request_id={req_id} key_slot={slot.slot_id} "
                                f"attempt={attempt} status=5xx_EXHAUSTED latency_ms={latency_ms} action=failover"
                            )
                            break

                    elif "400" in err_str or "INVALID_ARGUMENT" in err_str:
                        print(
                            f"[GeminiGateway] request_id={req_id} key_slot={slot.slot_id} "
                            f"status=400_BAD_REQUEST latency_ms={latency_ms} action=inspect_error err={err_str[:80]}"
                        )
                        return None # Application request error; do not blindly rotate

                    else:
                        slot.mark_transient_failure()
                        print(
                            f"[GeminiGateway] request_id={req_id} key_slot={slot.slot_id} "
                            f"status=EXCEPTION latency_ms={latency_ms} action=failover err={err_str[:80]}"
                        )
                        break

        print(f"[GeminiGateway] request_id={req_id} status=ALL_KEYS_EXHAUSTED action=trigger_feynman_fallback")
        return None


# Singleton instance
gemini_gateway = GeminiGateway()
