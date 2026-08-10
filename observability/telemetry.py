"""
observability/telemetry.py
==========================
Track C — C-0: Structured Production Observability

Provides per-request telemetry emission to stdout as structured JSON.
All log lines are safe to stream into any log aggregator (Render, CloudWatch, Datadog, etc.).

ZERO-SECRET INVARIANT:
  - API keys are NEVER logged.
  - JWT tokens are NEVER logged.
  - Raw user_id integers are NEVER logged — only SHA-256 hashes.
  - Passwords and OTP codes are NEVER logged.
"""

import hashlib
import json
import uuid
import time
from contextvars import ContextVar
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Per-request context variable — accumulated across middleware layers
# ---------------------------------------------------------------------------
request_telemetry: ContextVar["TelemetryEvent"] = ContextVar("request_telemetry")


# ---------------------------------------------------------------------------
# TelemetryEvent — the canonical telemetry schema
# ---------------------------------------------------------------------------
@dataclass
class TelemetryEvent:
    """
    One structured telemetry record per HTTP request.
    Fields match the schema defined in the Track C implementation plan.
    """
    # Request identity
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Routing
    endpoint: str = ""
    method: str = ""
    http_status: int = 0

    # Timing
    latency_ms: float = 0.0
    db_latency_ms: float = 0.0
    pdf_latency_ms: float = 0.0

    # Privacy-safe identity (SHA-256 of user_id, not the raw integer)
    user_id_hash: Optional[str] = None

    # Gemini / AI metrics
    model: Optional[str] = None
    key_slot: Optional[int] = None           # 1 / 2 / 3 (slot index, not the key itself)
    prompt_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    fallback_used: bool = False

    # Safety signals
    rate_limit_hit: bool = False
    auth_failure: bool = False

    # Internal marker
    _start_time: float = field(default_factory=time.monotonic, repr=False)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def hash_user_id(user_id: int) -> str:
    """
    Return the SHA-256 hex digest of a user_id integer.
    This produces a stable, privacy-safe token for log correlation
    that cannot be reversed to the original integer without brute-force.
    """
    return hashlib.sha256(str(user_id).encode()).hexdigest()


def new_event(endpoint: str = "", method: str = "") -> TelemetryEvent:
    """Create a fresh TelemetryEvent and bind it to the request context."""
    event = TelemetryEvent(endpoint=endpoint, method=method)
    request_telemetry.set(event)
    return event


def get_event() -> Optional[TelemetryEvent]:
    """Retrieve the TelemetryEvent bound to this request context, or None."""
    return request_telemetry.get(None)


def emit(event: TelemetryEvent) -> None:
    """
    Serialize the TelemetryEvent as a single-line JSON log entry and write to stdout.
    The output is safe to ingest by any structured log aggregator.

    Fields excluded from serialization:
      - _start_time  (internal monotonic timer, not meaningful in logs)
    """
    payload = asdict(event)
    payload.pop("_start_time", None)

    # Enforce zero-secret invariant: remove any field that looks like a secret.
    # (Belt-and-suspenders; callers should never set these in the first place.)
    for dangerous_key in ("api_key", "password", "token", "secret", "otp"):
        payload.pop(dangerous_key, None)

    print(json.dumps(payload, default=str), flush=True)


def finalize_and_emit(event: TelemetryEvent, http_status: int) -> None:
    """
    Fill latency_ms, set the final http_status, then emit.
    Called at the end of TelemetryMiddleware after calling call_next().
    """
    elapsed = time.monotonic() - event._start_time
    event.latency_ms = round(elapsed * 1000, 2)
    event.http_status = http_status
    emit(event)
