"""Async WebSocket notification server with an HTTP health endpoint."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
from collections.abc import Iterable
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from websockets.asyncio.server import ServerConnection, serve
from websockets.http11 import Request, Response

from broker import Broker, LocalBroker, RedisBroker
from storage import MessageStore
from transport import BaseTransport, ClientRegistry, WebSocketTransport, create_transport

SUPPORTED_TYPES = frozenset(
    {"broadcast", "direct", "system", "subscribe", "unsubscribe"}
)


def utc_timestamp() -> str:
    """Return an ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def make_message(message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Build a message in the public wire format."""
    return {
        "type": message_type,
        "payload": payload,
        "timestamp": utc_timestamp(),
    }


class NotificationServer:
    """Manage clients and route notifications independently of transport."""

    def __init__(
        self,
        registry: ClientRegistry | None = None,
        broker: Broker | None = None,
        store: MessageStore | None = None,
        transport: BaseTransport | None = None,
    ) -> None:
        if transport is not None and registry is not None:
            raise ValueError("registry must be configured on the transport")
        self.transport = transport or create_transport(os.getenv("TRANSPORT"))
        if registry is not None:
            self.transport.registry = registry
        self.registry = self.transport.registry
        redis_url = os.getenv("REDIS_URL")
        self.broker = broker or (RedisBroker(redis_url) if redis_url else LocalBroker())
        self.store = store or MessageStore(
            os.getenv("DATABASE_URL", "sqlite:///:memory:")
        )
        self._started = False
        self._start_lock = asyncio.Lock()

    async def start(self) -> None:
        """Start this server instance's broker subscriber worker."""
        if self._started:
            return
        async with self._start_lock:
            if not self._started:
                await self.broker.start(self._deliver)
                self._started = True

    async def close(self) -> None:
        """Release broker and database resources."""
        await self.broker.close()
        self.store.close()
        self._started = False

    async def process_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        """Serve REST endpoints before the WebSocket upgrade."""
        parsed_url = urlsplit(request.path)
        path = parsed_url.path
        if path == "/health":
            await self.start()
            body = json.dumps(
                {"connected_clients": await self.broker.connected_count()}
            )
        elif path == "/channels":
            await self.start()
            body = json.dumps({"channels": await self.broker.channels()})
        elif path.startswith("/channels/") and path.endswith("/subscribers"):
            encoded_name = path[len("/channels/") : -len("/subscribers")]
            if not encoded_name or "/" in encoded_name:
                return None
            channel = unquote(encoded_name)
            await self.start()
            body = json.dumps(
                {
                    "channel": channel,
                    "subscribers": await self.broker.subscribers(channel),
                }
            )
        elif path == "/messages":
            try:
                query = parse_qs(parsed_url.query, keep_blank_values=True)
                limit = self._query_integer(query, "limit", 50)
                offset = self._query_integer(query, "offset", 0)
                if limit < 0 or offset < 0:
                    raise ValueError
            except ValueError:
                return self._json_response(
                    connection,
                    HTTPStatus.BAD_REQUEST,
                    {"error": "limit and offset must be non-negative integers"},
                )
            body = json.dumps({"messages": self.store.list(limit, offset)})
        else:
            return None

        return self._json_response(connection, HTTPStatus.OK, body)

    @staticmethod
    def _query_integer(query: dict[str, list[str]], name: str, default: int) -> int:
        values = query.get(name)
        if values is None:
            return default
        if len(values) != 1:
            raise ValueError
        return int(values[0])

    @staticmethod
    def _json_response(
        connection: ServerConnection,
        status: HTTPStatus,
        content: str | dict[str, Any],
    ) -> Response:
        body = content if isinstance(content, str) else json.dumps(content)
        response = connection.respond(status, body)
        del response.headers["Content-Type"]
        response.headers["Content-Type"] = "application/json"
        return response

    async def handler(self, connection: ServerConnection) -> None:
        """Handle a connection using the configured transport."""
        await self.transport.handle_connection(
            connection, self._on_connect, self.handle_message, self._on_disconnect
        )

    async def _on_connect(self, connection: Any) -> str:
        await self.start()
        client_id = await self.transport.on_connect(connection)
        await self.broker.add_client(client_id)
        try:
            await self.transport.send_message(
                client_id,
                make_message(
                    "system", {"event": "connected", "client_id": client_id}
                ),
            )
        except BaseException:
            await self.transport.on_disconnect(client_id)
            await self.broker.remove_client(client_id)
            raise
        return client_id

    async def _on_disconnect(self, client_id: str) -> None:
        await self.transport.on_disconnect(client_id)
        await self.broker.remove_client(client_id)

    async def handle_message(self, sender_id: str, raw_message: str | bytes) -> None:
        if self.registry.get(sender_id) is None:
            return

        try:
            message = self._parse_message(raw_message)
        except ValueError as exc:
            await self._send_error(sender_id, str(exc))
            return

        message_type = message["type"]
        self.store.save(message)
        if message_type == "subscribe":
            self.registry.subscribe(sender_id, message["channel"])
            await self.broker.subscribe_client(sender_id, message["channel"])
        elif message_type == "unsubscribe":
            self.registry.unsubscribe(sender_id, message["channel"])
            await self.broker.unsubscribe_client(sender_id, message["channel"])
        elif message_type == "direct":
            await self._send_direct(sender_id, message)
        else:
            await self.broadcast(message, message.get("channel"))

    @staticmethod
    def _parse_message(raw_message: str | bytes) -> dict[str, Any]:
        if isinstance(raw_message, bytes):
            try:
                raw_message = raw_message.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("message must be UTF-8 JSON") from exc

        try:
            message = json.loads(raw_message)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError("message must be valid JSON") from exc

        if not isinstance(message, dict):
            raise ValueError("message must be a JSON object")
        required_fields = {"type", "payload", "timestamp"}
        if not required_fields.issubset(message) or not set(message).issubset(
            required_fields | {"channel"}
        ):
            raise ValueError(
                "message must contain type, payload, and timestamp, with optional channel"
            )
        if not isinstance(message["type"], str) or message["type"] not in SUPPORTED_TYPES:
            raise ValueError("unsupported message type")
        if not isinstance(message["payload"], dict):
            raise ValueError("payload must be a JSON object")
        if not isinstance(message["timestamp"], str):
            raise ValueError("timestamp must be a string")
        channel = message.get("channel")
        if channel is not None and (not isinstance(channel, str) or not channel):
            raise ValueError("channel must be a non-empty string")
        if message["type"] in {"subscribe", "unsubscribe"} and channel is None:
            raise ValueError(f'{message["type"]} requires channel')
        return message

    async def _send_direct(
        self, sender_id: str, message: dict[str, Any]
    ) -> None:
        payload = message["payload"]
        target_id = payload.get("client_id") or payload.get("target_id")
        if not isinstance(target_id, str) or not target_id:
            await self._send_error(sender_id, "direct payload requires client_id")
            return

        if not await self.broker.client_exists(target_id):
            await self._send_error(sender_id, "target client is not connected")
            return
        channel = message.get("channel")
        if channel is not None and not await self.broker.is_subscribed(
            target_id, channel
        ):
            await self._send_error(
                sender_id, "target client is not subscribed to channel"
            )
            return
        await self.broker.publish(
            {"message": message, "channel": channel, "target_id": target_id}
        )

    async def broadcast(
        self, message: dict[str, Any], channel: str | None = None
    ) -> None:
        """Publish a message for delivery by every server instance's worker."""
        await self.start()
        await self.broker.publish(
            {"message": message, "channel": channel, "target_id": None}
        )

    async def _deliver(self, delivery: dict[str, Any]) -> None:
        """Deliver a broker publication to sockets owned by this instance."""
        await self.transport.broadcast(
            delivery["message"], delivery.get("channel"), delivery.get("target_id")
        )

    async def _send_error(self, client_id: str, detail: str) -> None:
        try:
            await self.transport.send_message(
                client_id,
                make_message("system", {"event": "error", "detail": detail}),
            )
        except Exception:
            # A client may disconnect between validation and error delivery.
            pass


async def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Run until SIGINT or SIGTERM is received."""
    notifications = NotificationServer()
    stop = asyncio.get_running_loop().create_future()

    def request_stop() -> None:
        if not stop.done():
            stop.set_result(None)

    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            asyncio.get_running_loop().add_signal_handler(signum, request_stop)
        except NotImplementedError:
            pass

    try:
        async with serve(
            notifications.handler,
            host,
            port,
            process_request=notifications.process_request,
        ):
            await notifications.start()
            await stop
    finally:
        await notifications.close()


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    asyncio.run(run(args.host, args.port))


if __name__ == "__main__":
    main()
