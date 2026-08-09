import time
import asyncio
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class SlidingWindowRateLimiter:
    """Per-key sliding-window rate limiter (in-process, O(1) amortized).
    
    Not distributed — for a multi-worker deployment, swap in Redis.
    """

    def __init__(self, max_requests: int = 30, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        async with self._lock:
            bucket = self._buckets[key]
            cutoff = now - self.window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.pop(0)
            if len(bucket) >= self.max_requests:
                return False
            bucket.append(now)
            return True


create_limiter = SlidingWindowRateLimiter(max_requests=10, window_seconds=60)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply a stricter rate limit to URL-creation endpoints."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method == "POST" and request.url.path.rstrip("/") in ("/api/urls", "/api/shorten"):
            client_ip = request.client.host if request.client else "unknown"
            if not await create_limiter.is_allowed(client_ip):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please slow down."},
                    headers={"Retry-After": "60"},
                )
        return await call_next(request)
