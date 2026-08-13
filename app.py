"""Async WebSocket notification server with a SOAP health service."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import threading
import uuid
from collections.abc import Iterable
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit
from xml.etree import ElementTree
from xml.sax.saxutils import escape

import websockets
import aiosqlite
import redis.asyncio as redis
from websockets.exceptions import ConnectionClosed
from websockets.legacy.server import WebSocketServer, WebSocketServerProtocol


SOAP_ENV = "http://schemas.xmlsoap.org/soap/envelope/"
SERVICE_NS = "urn:notification-server"
SUPPORTED_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}
MAX_SOAP_REQUEST_SIZE = 64 * 1024
REDIS_MESSAGE_CHANNEL = "notification-server:messages"
REDIS_CLIENTS_KEY = "notification-server:clients"
REDIS_CHANNELS_KEY = "notification-server:channels"


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def message(
    message_type: str, payload: dict[str, Any], channel: str | None = None
) -> str:
    data = {"type": message_type, "payload": payload, "timestamp": utc_timestamp()}
    if channel is not None:
        data["channel"] = channel
    return json.dumps(data, separators=(",", ":"))


class ClientRegistry:
    """A registry safe to inspect or mutate from any thread."""

    def __init__(self) -> None:
        self._clients: dict[str, WebSocketServerProtocol] = {}
        self._channels: dict[str, set[str]] = {}
        self._lock = threading.RLock()

    def add(self, client: WebSocketServerProtocol) -> str:
        client_id = str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = client
        return client_id

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)
            for channel in list(self._channels):
                subscribers = self._channels[channel]
                subscribers.discard(client_id)
                if not subscribers:
                    del self._channels[channel]

    def get(self, client_id: str) -> WebSocketServerProtocol | None:
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> list[tuple[str, WebSocketServerProtocol]]:
        with self._lock:
            return list(self._clients.items())

    def subscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            if client_id in self._clients:
                self._channels.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            subscribers = self._channels.get(channel)
            if subscribers is None:
                return
            subscribers.discard(client_id)
            if not subscribers:
                del self._channels[channel]

    def channel_snapshot(self, channel: str) -> list[tuple[str, WebSocketServerProtocol]]:
        with self._lock:
            return [
                (client_id, self._clients[client_id])
                for client_id in self._channels.get(channel, set())
                if client_id in self._clients
            ]

    def channels(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"name": name, "subscriber_count": len(subscribers)}
                for name, subscribers in sorted(self._channels.items())
                if subscribers
            ]

    def subscribers(self, channel: str) -> list[str]:
        with self._lock:
            return sorted(self._channels.get(channel, set()))

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._clients)


class MessageStore:
    def __init__(self, database_url: str) -> None:
        self.path = self._sqlite_path(database_url)
        self._database: aiosqlite.Connection | None = None

    @staticmethod
    def _sqlite_path(database_url: str) -> str:
        if database_url.startswith("sqlite:///"):
            return database_url[len("sqlite:///") :]
        if database_url.startswith("sqlite://"):
            return database_url[len("sqlite://") :]
        return database_url

    async def start(self) -> None:
        self._database = await aiosqlite.connect(self.path)
        self._database.row_factory = aiosqlite.Row
        await self._database.execute(
            """CREATE TABLE IF NOT EXISTS messages (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   channel TEXT,
                   type TEXT NOT NULL,
                   payload TEXT NOT NULL,
                   timestamp TEXT NOT NULL
               )"""
        )
        await self._database.commit()

    async def stop(self) -> None:
        if self._database is not None:
            await self._database.close()
            self._database = None

    async def save(self, data: dict[str, Any]) -> None:
        if self._database is None:
            raise RuntimeError("message store is not running")
        await self._database.execute(
            "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
            (
                data.get("channel"),
                data["type"],
                json.dumps(data["payload"], separators=(",", ":")),
                data["timestamp"],
            ),
        )
        await self._database.commit()

    async def list(self, limit: int, offset: int) -> list[dict[str, Any]]:
        if self._database is None:
            raise RuntimeError("message store is not running")
        cursor = await self._database.execute(
            "SELECT id, channel, type, payload, timestamp FROM messages "
            "ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [
            {
                "id": row["id"],
                "channel": row["channel"],
                "type": row["type"],
                "payload": json.loads(row["payload"]),
                "timestamp": row["timestamp"],
            }
            for row in rows
        ]


class NotificationServer:
    def __init__(
        self,
        host: str = "127.0.0.1",
        websocket_port: int = 8765,
        soap_port: int = 8080,
        redis_url: str | None = None,
        database_url: str | None = None,
        redis_client: Any | None = None,
    ) -> None:
        self.host = host
        self.websocket_port = websocket_port
        self.soap_port = soap_port
        self.clients = ClientRegistry()
        self.instance_id = str(uuid.uuid4())
        self.redis = redis_client or redis.from_url(
            redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True,
        )
        self._owns_redis = redis_client is None
        self.messages = MessageStore(
            database_url or os.getenv("DATABASE_URL", "notifications.db")
        )
        self._websocket_server: WebSocketServer | None = None
        self._soap_server: asyncio.AbstractServer | None = None
        self._pubsub: Any | None = None
        self._broker_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        try:
            await self.messages.start()
            self._pubsub = self.redis.pubsub()
            await self._pubsub.subscribe(REDIS_MESSAGE_CHANNEL)
            self._broker_task = asyncio.create_task(self._consume_broker())
            self._websocket_server = await websockets.serve(
                self.handle_websocket, self.host, self.websocket_port
            )
            self._soap_server = await asyncio.start_server(
                self.handle_http_connection, self.host, self.soap_port
            )
        except Exception:
            if self._websocket_server is not None:
                self._websocket_server.close()
                await self._websocket_server.wait_closed()
                self._websocket_server = None
            await self._stop_backends()
            raise

    async def stop(self) -> None:
        if self._soap_server is not None:
            self._soap_server.close()
            await self._soap_server.wait_closed()
            self._soap_server = None
        if self._websocket_server is not None:
            self._websocket_server.close()
            await self._websocket_server.wait_closed()
            self._websocket_server = None
        for client_id, _ in self.clients.snapshot():
            await self._remove_client(client_id)
        await self._stop_backends()

    async def _stop_backends(self) -> None:
        if self._broker_task is not None:
            self._broker_task.cancel()
            await asyncio.gather(self._broker_task, return_exceptions=True)
            self._broker_task = None
        if self._pubsub is not None:
            await self._pubsub.aclose()
            self._pubsub = None
        await self.messages.stop()
        if self._owns_redis:
            await self.redis.aclose()

    @property
    def bound_websocket_port(self) -> int:
        if self._websocket_server is None or not self._websocket_server.sockets:
            raise RuntimeError("server is not running")
        return self._websocket_server.sockets[0].getsockname()[1]

    @property
    def bound_soap_port(self) -> int:
        if self._soap_server is None or not self._soap_server.sockets:
            raise RuntimeError("server is not running")
        return self._soap_server.sockets[0].getsockname()[1]

    async def handle_websocket(self, websocket: WebSocketServerProtocol) -> None:
        client_id = self.clients.add(websocket)
        await self.redis.hset(REDIS_CLIENTS_KEY, client_id, self.instance_id)
        await websocket.send(
            message("system", {"event": "connected", "client_id": client_id})
        )
        try:
            async for raw_message in websocket:
                await self._process_message(client_id, websocket, raw_message)
        except ConnectionClosed:
            pass
        finally:
            await self._remove_client(client_id)

    async def _remove_client(self, client_id: str) -> None:
        self.clients.remove(client_id)
        await self.redis.hdel(REDIS_CLIENTS_KEY, client_id)
        channels = await self.redis.hkeys(REDIS_CHANNELS_KEY)
        for channel in channels:
            await self.redis.srem(self._channel_key(channel), client_id)
            if not await self.redis.scard(self._channel_key(channel)):
                await self.redis.hdel(REDIS_CHANNELS_KEY, channel)

    @staticmethod
    def _channel_key(channel: str) -> str:
        return f"notification-server:channel:{channel}:subscribers"

    async def _process_message(
        self,
        client_id: str,
        websocket: WebSocketServerProtocol,
        raw_message: str | bytes,
    ) -> None:
        try:
            incoming = json.loads(raw_message)
            self._validate_message(incoming)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            await websocket.send(message("system", {"event": "error", "detail": str(exc)}))
            return

        message_type = incoming["type"]
        payload = incoming["payload"]
        channel = incoming.get("channel")
        if message_type == "system":
            await websocket.send(
                message(
                    "system",
                    {"event": "error", "detail": "system messages are server-only"},
                )
            )
        elif message_type == "broadcast":
            await self._publish_message(
                "broadcast", {"sender_id": client_id, **payload}, channel
            )
        elif message_type == "direct":
            await self._send_direct(client_id, websocket, payload, channel)
        elif channel is None:
            await websocket.send(
                message(
                    "system",
                    {"event": "error", "detail": f"{message_type} requires channel"},
                )
            )
        else:
            if message_type == "subscribe":
                self.clients.subscribe(client_id, channel)
                await self.redis.hset(REDIS_CHANNELS_KEY, channel, "1")
                await self.redis.sadd(self._channel_key(channel), client_id)
                event = "subscribed"
            else:
                self.clients.unsubscribe(client_id, channel)
                await self.redis.srem(self._channel_key(channel), client_id)
                if not await self.redis.scard(self._channel_key(channel)):
                    await self.redis.hdel(REDIS_CHANNELS_KEY, channel)
                event = "unsubscribed"
            await websocket.send(message("system", {"event": event}, channel))

    @staticmethod
    def _validate_message(incoming: Any) -> None:
        if not isinstance(incoming, dict):
            raise ValueError("message must be a JSON object")
        required = {"type", "payload", "timestamp"}
        fields = set(incoming)
        if not required.issubset(fields) or fields - required - {"channel"}:
            raise ValueError(
                "message must contain type, payload, timestamp, and optional channel"
            )
        if incoming["type"] not in SUPPORTED_TYPES:
            raise ValueError("unsupported message type")
        if not isinstance(incoming["payload"], dict):
            raise ValueError("payload must be an object")
        if not isinstance(incoming["timestamp"], str):
            raise ValueError("timestamp must be a string")
        if "channel" in incoming and (
            not isinstance(incoming["channel"], str) or not incoming["channel"]
        ):
            raise ValueError("channel must be a non-empty string")

    async def broadcast(self, encoded_message: str, channel: str | None = None) -> None:
        data = json.loads(encoded_message)
        if channel is not None:
            data["channel"] = channel
        await self.messages.save(data)
        await self.redis.publish(
            REDIS_MESSAGE_CHANNEL,
            json.dumps({"message": data, "recipient_id": None}, separators=(",", ":")),
        )

    async def _publish_message(
        self,
        message_type: str,
        payload: dict[str, Any],
        channel: str | None,
        recipient_id: str | None = None,
    ) -> None:
        data = json.loads(message(message_type, payload, channel))
        await self.messages.save(data)
        await self.redis.publish(
            REDIS_MESSAGE_CHANNEL,
            json.dumps(
                {"message": data, "recipient_id": recipient_id},
                separators=(",", ":"),
            ),
        )

    async def _consume_broker(self) -> None:
        assert self._pubsub is not None
        async for event in self._pubsub.listen():
            if event["type"] != "message":
                continue
            delivery = json.loads(event["data"])
            data = delivery["message"]
            recipient_id = delivery.get("recipient_id")
            if recipient_id is not None:
                recipient = self.clients.get(recipient_id)
                clients = [] if recipient is None else [(recipient_id, recipient)]
            elif data.get("channel") is None:
                clients = self.clients.snapshot()
            else:
                clients = self.clients.channel_snapshot(data["channel"])
            await self._send_to_clients(
                clients, json.dumps(data, separators=(",", ":"))
            )

    async def _send_to_clients(
        self,
        clients: Iterable[tuple[str, WebSocketServerProtocol]],
        encoded_message: str,
    ) -> None:
        clients = list(clients)
        results = await asyncio.gather(
            *(client.send(encoded_message) for _, client in clients),
            return_exceptions=True,
        )
        for (client_id, _), result in zip(clients, results):
            if isinstance(result, Exception):
                self.clients.remove(client_id)

    async def _send_direct(
        self,
        sender_id: str,
        sender: WebSocketServerProtocol,
        payload: dict[str, Any],
        channel: str | None = None,
    ) -> None:
        recipient_id = payload.get("client_id")
        if not isinstance(recipient_id, str):
            await sender.send(
                message(
                    "system",
                    {"event": "error", "detail": "direct payload requires client_id"},
                )
            )
            return
        if await self.redis.hget(REDIS_CLIENTS_KEY, recipient_id) is None:
            await sender.send(
                message("system", {"event": "error", "detail": "client not found"})
            )
            return
        if channel is not None and not await self.redis.sismember(
            self._channel_key(channel), recipient_id
        ):
            await sender.send(
                message(
                    "system",
                    {"event": "error", "detail": "client is not subscribed to channel"},
                    channel,
                )
            )
            return
        forwarded_payload = {key: value for key, value in payload.items() if key != "client_id"}
        await self._publish_message(
            "direct",
            {"sender_id": sender_id, **forwarded_payload},
            channel,
            recipient_id,
        )

    async def handle_http_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            method, target, headers = await self._read_http_request(reader)
            if method == "GET":
                status, content_type, body = await self._rest_response(target)
            else:
                status, body = await self._soap_response(reader, method, target, headers)
                content_type = "text/xml; charset=utf-8"
        except (ValueError, asyncio.IncompleteReadError) as exc:
            status = HTTPStatus.BAD_REQUEST
            content_type = "text/xml; charset=utf-8"
            body = self._soap_fault("Client", str(exc))
        except Exception:
            status = HTTPStatus.INTERNAL_SERVER_ERROR
            content_type = "text/xml; charset=utf-8"
            body = self._soap_fault("Server", "Internal server error")

        encoded_body = body.encode("utf-8")
        writer.write(
            f"HTTP/1.1 {status.value} {status.phrase}\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(encoded_body)}\r\n"
            "Connection: close\r\n\r\n".encode("ascii")
            + encoded_body
        )
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    @staticmethod
    async def _read_http_request(
        reader: asyncio.StreamReader,
    ) -> tuple[str, str, dict[str, str]]:
        request_line = (await reader.readline()).decode("ascii").strip()
        parts = request_line.split()
        if len(parts) != 3:
            raise ValueError("malformed HTTP request line")

        headers: dict[str, str] = {}
        while True:
            line = await reader.readline()
            if line in (b"\r\n", b"\n"):
                break
            name, separator, value = line.decode("ascii").partition(":")
            if not separator:
                raise ValueError("malformed HTTP header")
            headers[name.lower().strip()] = value.strip()
        return parts[0], parts[1], headers

    async def _soap_response(
        self,
        reader: asyncio.StreamReader,
        method: str,
        target: str,
        headers: dict[str, str],
    ) -> tuple[HTTPStatus, str]:
        if method != "POST" or urlsplit(target).path != "/soap":
            raise ValueError("SOAP requests must use POST /soap")

        try:
            content_length = int(headers["content-length"])
        except (KeyError, ValueError) as exc:
            raise ValueError("valid Content-Length header is required") from exc
        if content_length < 0 or content_length > MAX_SOAP_REQUEST_SIZE:
            raise ValueError("SOAP request body is too large")
        body = await reader.readexactly(content_length)
        try:
            envelope = ElementTree.fromstring(body)
        except ElementTree.ParseError as exc:
            raise ValueError("malformed SOAP XML") from exc

        soap_body = envelope.find(f"{{{SOAP_ENV}}}Body")
        operation = next(iter(soap_body), None) if soap_body is not None else None
        if operation is None or operation.tag != f"{{{SERVICE_NS}}}GetHealth":
            raise ValueError("unsupported SOAP operation")

        response = (
            f'<soap:Envelope xmlns:soap="{SOAP_ENV}" xmlns:ns="{SERVICE_NS}">'
            "<soap:Body><ns:GetHealthResponse>"
            f"<ns:connectedClientCount>{self.clients.count}</ns:connectedClientCount>"
            "</ns:GetHealthResponse></soap:Body></soap:Envelope>"
        )
        return HTTPStatus.OK, response

    async def _rest_response(self, target: str) -> tuple[HTTPStatus, str, str]:
        parsed = urlsplit(target)
        path = parsed.path
        if path == "/channels":
            names = sorted(await self.redis.hkeys(REDIS_CHANNELS_KEY))
            body: dict[str, Any] = {"channels": [
                {
                    "name": name,
                    "subscriber_count": await self.redis.scard(self._channel_key(name)),
                }
                for name in names
            ]}
            status = HTTPStatus.OK
        elif path == "/messages":
            query = parse_qs(parsed.query)
            try:
                limit = int(query.get("limit", ["50"])[0])
                offset = int(query.get("offset", ["0"])[0])
            except ValueError:
                return self._json_error(HTTPStatus.BAD_REQUEST, "limit and offset must be integers")
            if limit < 0 or offset < 0:
                return self._json_error(HTTPStatus.BAD_REQUEST, "limit and offset must be non-negative")
            body = {"messages": await self.messages.list(limit, offset)}
            status = HTTPStatus.OK
        elif path.startswith("/channels/") and path.endswith("/subscribers"):
            encoded_name = path[len("/channels/") : -len("/subscribers")].rstrip("/")
            name = unquote(encoded_name)
            if not name or "/" in name:
                return self._json_error(HTTPStatus.NOT_FOUND, "endpoint not found")
            subscribers = await self.redis.smembers(self._channel_key(name))
            body = {"channel": name, "subscribers": sorted(subscribers)}
            status = HTTPStatus.OK
        else:
            return self._json_error(HTTPStatus.NOT_FOUND, "endpoint not found")
        return status, "application/json; charset=utf-8", json.dumps(body, separators=(",", ":"))

    @staticmethod
    def _json_error(status: HTTPStatus, detail: str) -> tuple[HTTPStatus, str, str]:
        return (
            status,
            "application/json; charset=utf-8",
            json.dumps({"error": detail}, separators=(",", ":")),
        )

    @staticmethod
    def _soap_fault(code: str, detail: str) -> str:
        return (
            f'<soap:Envelope xmlns:soap="{SOAP_ENV}"><soap:Body><soap:Fault>'
            f"<faultcode>soap:{code}</faultcode><faultstring>{escape(detail)}</faultstring>"
            "</soap:Fault></soap:Body></soap:Envelope>"
        )


async def run_server(host: str, websocket_port: int, soap_port: int) -> None:
    server = NotificationServer(host, websocket_port, soap_port)
    await server.start()
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signum, stop_event.set)
    print(
        f"WebSocket listening on ws://{host}:{server.bound_websocket_port}; "
        f"SOAP listening on http://{host}:{server.bound_soap_port}/soap"
    )
    try:
        await stop_event.wait()
    finally:
        await server.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--websocket-port", type=int, default=8765)
    parser.add_argument("--soap-port", type=int, default=8080)
    args = parser.parse_args()
    asyncio.run(run_server(args.host, args.websocket_port, args.soap_port))


if __name__ == "__main__":
    main()
