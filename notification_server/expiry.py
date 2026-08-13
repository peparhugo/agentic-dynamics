"""Background cleanup of persisted messages older than a configurable TTL.

Runs as an asyncio task started alongside the server: it deletes expired
rows once immediately (so a server that's been down doesn't wait a full
interval to catch up), then repeats on `interval_seconds` until stopped.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from datetime import datetime, timedelta, timezone

from .store import MessageStore

logger = logging.getLogger(__name__)

DEFAULT_TTL_DAYS = 7
DEFAULT_INTERVAL_SECONDS = 3600


class MessageExpiry:
    def __init__(
        self,
        store: MessageStore,
        ttl_days: int = DEFAULT_TTL_DAYS,
        interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    ) -> None:
        self.store = store
        self.ttl_days = ttl_days
        self.interval_seconds = interval_seconds
        self._task: asyncio.Task | None = None

    @classmethod
    def from_env(cls, store: MessageStore, interval_seconds: int = DEFAULT_INTERVAL_SECONDS) -> "MessageExpiry":
        ttl_days = int(os.environ.get("MESSAGE_TTL_DAYS", DEFAULT_TTL_DAYS))
        return cls(store, ttl_days=ttl_days, interval_seconds=interval_seconds)

    def _cutoff(self) -> str:
        return (datetime.now(timezone.utc) - timedelta(days=self.ttl_days)).isoformat()

    async def run_once(self) -> int:
        """Delete expired messages now; return how many rows were removed."""
        deleted = await self.store.adelete_older_than(self._cutoff())
        if deleted:
            logger.info("expired %d message(s) older than %d day(s)", deleted, self.ttl_days)
        return deleted

    async def _loop(self) -> None:
        while True:
            await self.run_once()
            await asyncio.sleep(self.interval_seconds)

    async def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
