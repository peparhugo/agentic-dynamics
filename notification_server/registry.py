"""Thread-safe registry of connected WebSocket clients."""
from __future__ import annotations

import asyncio
import uuid
from typing import Any, Iterable


class ClientRegistry:
    """Tracks connected clients behind an asyncio.Lock.

    All mutation and iteration goes through the lock so concurrent
    connects, disconnects, and broadcasts never observe a torn state.
    """

    def __init__(self) -> None:
        self._clients: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def register(self, websocket: Any) -> str:
        client_id = uuid.uuid4().hex
        async with self._lock:
            self._clients[client_id] = websocket
        return client_id

    async def unregister(self, client_id: str) -> None:
        async with self._lock:
            self._clients.pop(client_id, None)

    async def get(self, client_id: str) -> Any | None:
        async with self._lock:
            return self._clients.get(client_id)

    async def count(self) -> int:
        async with self._lock:
            return len(self._clients)

    async def snapshot(self) -> dict[str, Any]:
        async with self._lock:
            return dict(self._clients)

    async def broadcast(self, text: str, exclude: Iterable[str] = ()) -> list[str]:
        """Send `text` to every registered client except those in `exclude`.

        Clients whose send fails are dropped from the registry. Returns the
        list of client IDs that were dropped this way.
        """
        exclude = set(exclude)
        clients = await self.snapshot()
        targets = {cid: ws for cid, ws in clients.items() if cid not in exclude}
        if not targets:
            return []

        results = await asyncio.gather(
            *(self._safe_send(ws, text) for ws in targets.values()),
            return_exceptions=True,
        )

        dead = [cid for cid, ok in zip(targets.keys(), results) if ok is not True]
        for cid in dead:
            await self.unregister(cid)
        return dead

    @staticmethod
    async def _safe_send(websocket: Any, text: str) -> bool:
        try:
            await websocket.send(text)
            return True
        except Exception:
            return False
