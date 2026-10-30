import logging
import time

from fastapi import HTTPException, Request, status

from app.config import get_settings

log = logging.getLogger(__name__)


class RateLimiter:
    """Fixed-window limiter. Uses Redis when configured (shared across workers), memory otherwise."""

    def __init__(self) -> None:
        self._redis = None
        self._memory: dict[str, tuple[int, float]] = {}
        url = get_settings().redis_url
        if url:
            try:
                import redis.asyncio as redis

                self._redis = redis.from_url(url)
            except Exception:  # pragma: no cover
                log.warning("Redis unavailable, using in-memory rate limiting")

    async def hit(self, key: str, limit: int, window_s: int) -> bool:
        """Count one hit; return True if still within the limit."""
        bucket = f"rl:{key}:{int(time.time() // window_s)}"
        if self._redis is not None:
            try:
                count = await self._redis.incr(bucket)
                if count == 1:
                    await self._redis.expire(bucket, window_s)
                return count <= limit
            except Exception:
                log.warning("Redis rate-limit error, falling back to memory")
        now = time.time()
        if len(self._memory) > 10_000:
            self._memory = {k: v for k, v in self._memory.items() if v[1] > now}
        count, expires = self._memory.get(bucket, (0, now + window_s))
        self._memory[bucket] = (count + 1, expires)
        return count + 1 <= limit

    def reset(self) -> None:
        self._memory.clear()


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def enforce(key: str, limit: int, window_s: int) -> None:
    if not await limiter.hit(key, limit, window_s):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests. Please slow down and try again shortly.")
