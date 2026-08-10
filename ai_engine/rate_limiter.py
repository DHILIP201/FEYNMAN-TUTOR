"""
Feynman Cognitive Engine — Rate Limiter & Token Budgeting Subsystem
Provides tiered sliding-window rate limiting, daily query/token budgets, and Redis-ready state storage.
"""

import os
import time
import threading
from typing import Dict, Any, Tuple, Optional
from datetime import datetime


class RateLimitTier:
    GUEST = "GUEST"
    FREE = "FREE"
    PRO = "PRO"
    ADMIN = "ADMIN"

    CONFIGS = {
        GUEST: {
            "requests_per_minute": int(os.getenv("RATE_LIMIT_GUEST_RPM", "10")),
            "daily_requests_max": int(os.getenv("BUDGET_GUEST_DAILY_REQ", "25")),
            "daily_tokens_max": int(os.getenv("BUDGET_GUEST_DAILY_TOKENS", "25000")),
        },
        FREE: {
            "requests_per_minute": int(os.getenv("RATE_LIMIT_FREE_RPM", "30")),
            "daily_requests_max": int(os.getenv("BUDGET_FREE_DAILY_REQ", "150")),
            "daily_tokens_max": int(os.getenv("BUDGET_FREE_DAILY_TOKENS", "150000")),
        },
        PRO: {
            "requests_per_minute": int(os.getenv("RATE_LIMIT_PRO_RPM", "120")),
            "daily_requests_max": int(os.getenv("BUDGET_PRO_DAILY_REQ", "1000")),
            "daily_tokens_max": int(os.getenv("BUDGET_PRO_DAILY_TOKENS", "1000000")),
        },
        ADMIN: {
            "requests_per_minute": 300,
            "daily_requests_max": 10000,
            "daily_tokens_max": 10000000,
        }
    }


class BaseRateLimitStorage:
    def increment_window(self, key: str, window_seconds: int) -> int:
        raise NotImplementedError

    def get_window_count(self, key: str) -> int:
        raise NotImplementedError

    def add_token_usage(self, key: str, tokens: int, ttl_seconds: int) -> int:
        raise NotImplementedError

    def get_token_usage(self, key: str) -> int:
        raise NotImplementedError


class InMemoryRateLimitStorage(BaseRateLimitStorage):
    """Thread-safe in-memory rate limiting and token budgeting cache."""

    def __init__(self):
        self._lock = threading.Lock()
        self._sliding_windows: Dict[str, list] = {}
        self._daily_counters: Dict[str, Dict[str, Any]] = {}

    def _cleanup_expired_requests(self, key: str, now: float, window_seconds: int):
        if key in self._sliding_windows:
            cutoff = now - window_seconds
            self._sliding_windows[key] = [t for t in self._sliding_windows[key] if t > cutoff]
            if not self._sliding_windows[key]:
                del self._sliding_windows[key]

    def increment_window(self, key: str, window_seconds: int) -> int:
        now = time.time()
        with self._lock:
            self._cleanup_expired_requests(key, now, window_seconds)
            timestamps = self._sliding_windows.setdefault(key, [])
            timestamps.append(now)
            return len(timestamps)

    def get_window_count(self, key: str, window_seconds: int = 60) -> int:
        now = time.time()
        with self._lock:
            self._cleanup_expired_requests(key, now, window_seconds)
            return len(self._sliding_windows.get(key, []))

    def add_token_usage(self, key: str, tokens: int, ttl_seconds: int = 86400) -> int:
        now = time.time()
        with self._lock:
            entry = self._daily_counters.setdefault(key, {"tokens": 0, "requests": 0, "expires_at": now + ttl_seconds})
            if now > entry["expires_at"]:
                entry["tokens"] = 0
                entry["requests"] = 0
                entry["expires_at"] = now + ttl_seconds
            entry["tokens"] += tokens
            entry["requests"] += 1
            return entry["tokens"]

    def get_token_usage(self, key: str) -> Dict[str, Any]:
        now = time.time()
        with self._lock:
            entry = self._daily_counters.get(key)
            if not entry or now > entry["expires_at"]:
                return {"tokens": 0, "requests": 0, "expires_at": now + 86400}
            return dict(entry)


class RedisRateLimitStorage(BaseRateLimitStorage):
    """Redis-backed distributed state adapter for multi-instance deployments."""

    def __init__(self, redis_client):
        self.redis = redis_client

    def increment_window(self, key: str, window_seconds: int) -> int:
        try:
            pipe = self.redis.pipeline()
            now = time.time()
            cutoff = now - window_seconds
            pipe.zremrangebyscore(key, 0, cutoff)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, window_seconds + 5)
            results = pipe.execute()
            return results[2]
        except Exception:
            return 1

    def get_window_count(self, key: str, window_seconds: int = 60) -> int:
        try:
            now = time.time()
            cutoff = now - window_seconds
            self.redis.zremrangebyscore(key, 0, cutoff)
            return self.redis.zcard(key)
        except Exception:
            return 0

    def add_token_usage(self, key: str, tokens: int, ttl_seconds: int = 86400) -> int:
        try:
            pipe = self.redis.pipeline()
            pipe.hincrby(key, "tokens", tokens)
            pipe.hincrby(key, "requests", 1)
            pipe.expire(key, ttl_seconds)
            results = pipe.execute()
            return results[0]
        except Exception:
            return tokens

    def get_token_usage(self, key: str) -> Dict[str, Any]:
        try:
            data = self.redis.hgetall(key)
            if not data:
                return {"tokens": 0, "requests": 0}
            return {
                "tokens": int(data.get(b"tokens", data.get("tokens", 0))),
                "requests": int(data.get(b"requests", data.get("requests", 0)))
            }
        except Exception:
            return {"tokens": 0, "requests": 0}


def create_rate_limit_storage() -> BaseRateLimitStorage:
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        try:
            import redis
            client = redis.from_url(redis_url)
            client.ping()
            print("[RateLimiter] Connected to distributed Redis storage backend.")
            return RedisRateLimitStorage(client)
        except Exception as e:
            print(f"[RateLimiter] Redis connection failed ({e}). Falling back to InMemory storage.")
    return InMemoryRateLimitStorage()


class RateLimiter:
    """Core rate limiting and budget checking coordinator."""

    def __init__(self, storage: Optional[BaseRateLimitStorage] = None):
        self.storage = storage or create_rate_limit_storage()

    def check_rate_limit(self, identifier: str, tier: str = RateLimitTier.FREE) -> Tuple[bool, Dict[str, Any]]:
        """
        Validates requests per minute using sliding window.
        Returns (is_allowed, rate_limit_metadata).
        """
        cfg = RateLimitTier.CONFIGS.get(tier, RateLimitTier.CONFIGS[RateLimitTier.FREE])
        rpm_limit = cfg["requests_per_minute"]
        key = f"rate_limit:{tier}:{identifier}"
        
        current_count = self.storage.increment_window(key, window_seconds=60)
        remaining = max(0, rpm_limit - current_count)
        is_allowed = current_count <= rpm_limit

        info = {
            "limit": rpm_limit,
            "remaining": remaining,
            "reset_seconds": 60,
            "retry_after": 60 if not is_allowed else 0,
            "tier": tier
        }
        return is_allowed, info

    def check_budget(self, identifier: str, estimated_tokens: int = 500, tier: str = RateLimitTier.FREE) -> Tuple[bool, Dict[str, Any]]:
        """
        Validates daily query and token budgets for the user.
        Returns (is_allowed, budget_metadata).
        """
        cfg = RateLimitTier.CONFIGS.get(tier, RateLimitTier.CONFIGS[RateLimitTier.FREE])
        max_daily_requests = cfg["daily_requests_max"]
        max_daily_tokens = cfg["daily_tokens_max"]
        today = datetime.utcnow().strftime("%Y-%m-%d")
        key = f"budget:{tier}:{identifier}:{today}"

        usage = self.storage.get_token_usage(key)
        curr_requests = usage.get("requests", 0)
        curr_tokens = usage.get("tokens", 0)

        is_allowed = (curr_requests + 1 <= max_daily_requests) and (curr_tokens + estimated_tokens <= max_daily_tokens)

        if is_allowed:
            self.storage.add_token_usage(key, estimated_tokens, ttl_seconds=86400)
            curr_tokens += estimated_tokens
            curr_requests += 1

        info = {
            "daily_requests_limit": max_daily_requests,
            "daily_requests_used": curr_requests,
            "daily_requests_remaining": max(0, max_daily_requests - curr_requests),
            "daily_tokens_limit": max_daily_tokens,
            "daily_tokens_used": curr_tokens,
            "daily_tokens_remaining": max(0, max_daily_tokens - curr_tokens),
            "tier": tier
        }
        return is_allowed, info


# Singleton Rate Limiter
rate_limiter = RateLimiter()
