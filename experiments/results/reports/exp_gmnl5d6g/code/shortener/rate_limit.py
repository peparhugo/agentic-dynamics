import time
import asyncio
from collections import defaultdict

from fastapi import Request, HTTPException


class RateLimiter:
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: defaultdict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def _clean_bucket(self, client_id: str, now: float) -> None:
        cutoff = now - self.window_seconds
        bucket = self._buckets[client_id]
        self._buckets[client_id] = [t for t in bucket if t > cutoff]

    async def check(self, client_id: str) -> bool:
        now = time.time()
        async with self._lock:
            await self._clean_bucket(client_id, now)
            bucket = self._buckets[client_id]
            if len(bucket) >= self.max_requests:
                return False
            bucket.append(now)
            return True

    async def __call__(self, request: Request):
        client_id = request.client.host if request.client else "unknown"
        allowed = await self.check(client_id)
        if not allowed:
            raise HTTPException(status_code=429, detail="Too many requests")
