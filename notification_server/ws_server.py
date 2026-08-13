"""Async WebSocket notification server built on the `websockets` library."""
from __future__ import annotations

import asyncio
import logging
import uuid

import websockets

from .messages import InvalidMessage, dumps, error_message, make_message, parse_message
from .registry import ClientRegistry

logger = logging.getLogger(__name__)


class NotificationServer:
    def __init__(self, registry: ClientRegistry | None = None) -> None:
        self.registry = registry or ClientRegistry()

    async def handler(self, websocket) -> None:
        client_id = str(uuid.uuid4())
        self.registry.add(client_id, websocket)
        try:
            await self._send(
                websocket, make_message("system", {"event": "connected", "client_id": client_id})
            )
            async for raw in websocket:
                await self._handle_raw(client_id, raw)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.registry.remove(client_id)

    async def _handle_raw(self, sender_id: str, raw: str) -> None:
        try:
            message = parse_message(raw)
        except InvalidMessage as exc:
            sender = self.registry.get(sender_id)
            if sender is not None:
                await self._send(sender, error_message(str(exc)))
            return
        await self._route(sender_id, message)

    async def _route(self, sender_id: str, message: dict) -> None:
        msg_type = message["type"]
        if msg_type == "broadcast":
            await self._broadcast(sender_id, message)
        elif msg_type == "direct":
            await self._direct(sender_id, message)
        elif msg_type == "subscribe":
            await self._subscribe(sender_id, message)
        elif msg_type == "unsubscribe":
            await self._unsubscribe(sender_id, message)
        else:  # "system" is server-reserved; clients may not originate it
            sender = self.registry.get(sender_id)
            if sender is not None:
                await self._send(
                    sender, error_message("type 'system' is reserved for the server")
                )

    async def _broadcast(self, sender_id: str, message: dict) -> None:
        outgoing = dict(message, sender_id=sender_id)
        channel = message.get("channel")
        targets = (
            self.registry.connections_for_channel(channel)
            if channel
            else self.registry.connections()
        )
        if not targets:
            return
        await asyncio.gather(*(self._send(ws, outgoing) for ws in targets), return_exceptions=True)

    async def _subscribe(self, sender_id: str, message: dict) -> None:
        channel = message.get("channel")
        sender = self.registry.get(sender_id)
        if not channel:
            if sender is not None:
                await self._send(sender, error_message("subscribe requires a 'channel' field"))
            return
        self.registry.subscribe(sender_id, channel)
        if sender is not None:
            await self._send(
                sender, make_message("system", {"event": "subscribed", "channel": channel})
            )

    async def _unsubscribe(self, sender_id: str, message: dict) -> None:
        channel = message.get("channel")
        sender = self.registry.get(sender_id)
        if not channel:
            if sender is not None:
                await self._send(sender, error_message("unsubscribe requires a 'channel' field"))
            return
        self.registry.unsubscribe(sender_id, channel)
        if sender is not None:
            await self._send(
                sender, make_message("system", {"event": "unsubscribed", "channel": channel})
            )

    async def _direct(self, sender_id: str, message: dict) -> None:
        target_id = message["payload"].get("target_id")
        target = self.registry.get(target_id) if target_id else None
        if target is None:
            sender = self.registry.get(sender_id)
            if sender is not None:
                await self._send(
                    sender, error_message(f"target_id {target_id!r} is not connected")
                )
            return
        outgoing = dict(message, sender_id=sender_id)
        await self._send(target, outgoing)

    @staticmethod
    async def _send(websocket, message: dict) -> None:
        try:
            await websocket.send(dumps(message))
        except websockets.exceptions.ConnectionClosed:
            pass

    def serve(self, host: str = "localhost", port: int = 8765):
        return websockets.serve(self.handler, host, port)
