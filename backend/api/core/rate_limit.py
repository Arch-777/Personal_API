from __future__ import annotations

import hashlib
import logging
import time
import uuid

from redis import Redis
from redis.exceptions import RedisError

from api.core.config import get_settings


logger = logging.getLogger(__name__)

_redis_client: Redis | None = None


def _get_redis_client() -> Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def _sliding_window_allow(key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    """Return (allowed, retry_after_seconds) for a Redis sorted-set sliding window."""
    if limit <= 0 or window_seconds <= 0:
        return True, 0

    now_ms = int(time.time() * 1000)
    window_ms = int(window_seconds * 1000)
    window_start_ms = now_ms - window_ms
    member = f"{now_ms}:{uuid.uuid4().hex}"

    client = _get_redis_client()
    pipeline = client.pipeline(transaction=True)
    pipeline.zremrangebyscore(key, 0, window_start_ms)
    pipeline.zadd(key, {member: now_ms})
    pipeline.zcard(key)
    pipeline.expire(key, max(window_seconds, 1))
    _, _, current_count, _ = pipeline.execute()

    if int(current_count) <= limit:
        return True, 0

    # Remove current request marker so rejected traffic does not inflate usage.
    client.zrem(key, member)
    oldest = client.zrange(key, 0, 0, withscores=True)
    if oldest:
        oldest_ms = int(oldest[0][1])
        retry_after_ms = max(0, (oldest_ms + window_ms) - now_ms)
        retry_after_seconds = int((retry_after_ms + 999) / 1000)
    else:
        retry_after_seconds = max(1, window_seconds)

    return False, max(1, retry_after_seconds)


def check_inbound_api_key_limit(raw_api_key: str) -> tuple[bool, int]:
    """Apply inbound request limits keyed by API key hash."""
    settings = get_settings()
    if not settings.api_rate_limit_enabled:
        return True, 0
    if not raw_api_key.strip():
        return True, 0

    key_hash = hashlib.sha256(raw_api_key.encode("utf-8")).hexdigest()
    redis_key = f"{settings.api_rate_limit_namespace}:{key_hash}"
    try:
        return _sliding_window_allow(
            key=redis_key,
            limit=settings.api_rate_limit_requests,
            window_seconds=settings.api_rate_limit_window_seconds,
        )
    except RedisError:
        logger.exception("Inbound rate limit check failed; allowing request")
        return True, 0


def check_outbound_connector_limit(user_id: str, platform: str) -> tuple[bool, int]:
    """Apply outbound connector request limits keyed by user_id + platform."""
    settings = get_settings()
    if not settings.connector_rate_limit_enabled:
        return True, 0

    safe_platform = platform.strip().lower()
    if not user_id.strip() or not safe_platform:
        return True, 0

    redis_key = f"{settings.connector_rate_limit_namespace}:{user_id}:{safe_platform}"
    try:
        return _sliding_window_allow(
            key=redis_key,
            limit=settings.connector_rate_limit_requests,
            window_seconds=settings.connector_rate_limit_window_seconds,
        )
    except RedisError:
        logger.exception("Outbound connector rate limit check failed; allowing sync")
        return True, 0
