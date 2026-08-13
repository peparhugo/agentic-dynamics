"""The default transport: plain WebSocket connections via the `websockets` library.

Also serves a few plain-HTTP endpoints (`/health`, `/channels`, `/messages`)
off the same port, piggybacking on `websockets`' `process_request` hook —
that hook is a peculiarity of this specific wire protocol, so it lives here
rather than on `BaseTransport`.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Iterable
from urllib.parse import parse_qs, unquote, urlsplit

from websockets.asyncio.server import ServerConnection
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response

from .messages import encode
from .transport import BaseTransport

logger = logging.getLogger("notification_server.transport.websocket")

HEALTH_PATH = "/health"
CHANNELS_PATH = "/channels"
MESSAGES_PATH = "/messages"
HISTORY_PATH = "/history"
CHANNEL_SUBSCRIBERS_RE = re.compile(r"^/channels/([^/]+)/subscribers$")

DEFAULT_MESSAGES_LIMIT = 50
MAX_MESSAGES_LIMIT = 500


class WebSocketTransport(BaseTransport):
    async def on_connect(self, websocket: ServerConnection) -> None:
        await self.server.start()
        client_id = await self.server.registry.register(websocket)
        await self.server._client_connected(client_id)
        try:
            async for raw in websocket:
                await self.server._dispatch(client_id, raw)
        except ConnectionClosed:
            pass
        finally:
            await self.on_disconnect(client_id)

    async def on_disconnect(self, client_id: str) -> None:
        await self.server.registry.unregister(client_id)
        await self.server._client_disconnected(client_id)

    async def send_message(self, client_id: str, message: dict) -> None:
        websocket = await self.server.registry.get(client_id)
        if websocket is None:
            return
        try:
            await websocket.send(encode(message))
        except ConnectionClosed:
            pass

    async def broadcast(self, message: dict, *, channel: str | None = None, exclude: Iterable[str] = ()) -> None:
        text = encode(message)
        if channel:
            await self.server.registry.broadcast_channel(text, channel, exclude=exclude)
        else:
            await self.server.registry.broadcast(text, exclude=exclude)

    async def process_request(self, connection: ServerConnection, request: Request) -> Response | None:
        split = urlsplit(request.path)
        path = split.path
        query = parse_qs(split.query)
        registry = self.server.registry
        store = self.server.store

        if path == HEALTH_PATH:
            body = json.dumps({"connected_clients": await registry.global_count()})
            return self._json_response(connection, 200, body)

        if path == CHANNELS_PATH:
            channels = await registry.global_channels_snapshot()
            body = json.dumps({
                "channels": [
                    {"name": name, "subscribers": count}
                    for name, count in sorted(channels.items())
                ],
            })
            return self._json_response(connection, 200, body)

        if path == MESSAGES_PATH:
            limit = self._parse_query_int(query, "limit", DEFAULT_MESSAGES_LIMIT, minimum=1, maximum=MAX_MESSAGES_LIMIT)
            offset = self._parse_query_int(query, "offset", 0, minimum=0)
            messages = await asyncio.to_thread(store.get_messages, limit, offset)
            body = json.dumps({"messages": messages, "limit": limit, "offset": offset})
            return self._json_response(connection, 200, body)

        if path == HISTORY_PATH:
            channel = (query.get("channel", [None])[0] or "").strip()
            if not channel:
                body = json.dumps({"error": "channel is required"})
                return self._json_response(connection, 400, body)
            since = query.get("since", [None])[0]
            limit = self._parse_query_int(query, "limit", DEFAULT_MESSAGES_LIMIT, minimum=1, maximum=MAX_MESSAGES_LIMIT)
            messages, has_more = await asyncio.to_thread(store.get_history, channel, since, limit)
            body = json.dumps({
                "messages": messages,
                "channel": channel,
                "since": since,
                "limit": limit,
                "has_more": has_more,
            })
            return self._json_response(connection, 200, body)

        match = CHANNEL_SUBSCRIBERS_RE.match(path)
        if match:
            name = unquote(match.group(1))
            subscribers = await registry.global_subscribers(name)
            body = json.dumps({"channel": name, "subscribers": subscribers})
            return self._json_response(connection, 200, body)

        return None

    @staticmethod
    def _parse_query_int(query: dict, key: str, default: int, *, minimum: int, maximum: int | None = None) -> int:
        raw = query.get(key, [None])[0]
        if raw is None:
            value = default
        else:
            try:
                value = int(raw)
            except ValueError:
                value = default
        value = max(minimum, value)
        if maximum is not None:
            value = min(maximum, value)
        return value

    @staticmethod
    def _json_response(connection: ServerConnection, status: int, body: str) -> Response:
        response = connection.respond(status, body)
        response.headers["Content-Type"] = "application/json"
        return response
