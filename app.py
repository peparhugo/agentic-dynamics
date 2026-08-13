"""Async WebSocket notification server with a SOAP health service."""

from __future__ import annotations

import argparse
import asyncio
import json
import signal
import threading
import uuid
from collections.abc import Iterable
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree
from xml.sax.saxutils import escape

import websockets
from websockets.exceptions import ConnectionClosed
from websockets.legacy.server import WebSocketServer, WebSocketServerProtocol


SOAP_ENV = "http://schemas.xmlsoap.org/soap/envelope/"
SERVICE_NS = "urn:notification-server"
SUPPORTED_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}
MAX_SOAP_REQUEST_SIZE = 64 * 1024


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


class NotificationServer:
    def __init__(
        self,
        host: str = "127.0.0.1",
        websocket_port: int = 8765,
        soap_port: int = 8080,
    ) -> None:
        self.host = host
        self.websocket_port = websocket_port
        self.soap_port = soap_port
        self.clients = ClientRegistry()
        self._websocket_server: WebSocketServer | None = None
        self._soap_server: asyncio.AbstractServer | None = None

    async def start(self) -> None:
        self._websocket_server = await websockets.serve(
            self.handle_websocket, self.host, self.websocket_port
        )
        try:
            self._soap_server = await asyncio.start_server(
                self.handle_http_connection, self.host, self.soap_port
            )
        except Exception:
            self._websocket_server.close()
            await self._websocket_server.wait_closed()
            self._websocket_server = None
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
        await websocket.send(
            message("system", {"event": "connected", "client_id": client_id})
        )
        try:
            async for raw_message in websocket:
                await self._process_message(client_id, websocket, raw_message)
        except ConnectionClosed:
            pass
        finally:
            self.clients.remove(client_id)

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
            await self.broadcast(
                message("broadcast", {"sender_id": client_id, **payload}, channel),
                channel,
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
                event = "subscribed"
            else:
                self.clients.unsubscribe(client_id, channel)
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
        clients = (
            self.clients.snapshot()
            if channel is None
            else self.clients.channel_snapshot(channel)
        )
        await self._send_to_clients(clients, encoded_message)

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
        recipient = self.clients.get(recipient_id)
        if recipient is None:
            await sender.send(
                message("system", {"event": "error", "detail": "client not found"})
            )
            return
        if channel is not None and recipient_id not in self.clients.subscribers(channel):
            await sender.send(
                message(
                    "system",
                    {"event": "error", "detail": "client is not subscribed to channel"},
                    channel,
                )
            )
            return
        forwarded_payload = {key: value for key, value in payload.items() if key != "client_id"}
        try:
            await recipient.send(
                message("direct", {"sender_id": sender_id, **forwarded_payload}, channel)
            )
        except ConnectionClosed:
            self.clients.remove(recipient_id)
            await sender.send(
                message("system", {"event": "error", "detail": "client disconnected"})
            )

    async def handle_http_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            method, target, headers = await self._read_http_request(reader)
            if method == "GET":
                status, content_type, body = self._rest_response(target)
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

    def _rest_response(self, target: str) -> tuple[HTTPStatus, str, str]:
        path = urlsplit(target).path
        if path == "/channels":
            body: dict[str, Any] = {"channels": self.clients.channels()}
            status = HTTPStatus.OK
        elif path.startswith("/channels/") and path.endswith("/subscribers"):
            encoded_name = path[len("/channels/") : -len("/subscribers")].rstrip("/")
            name = unquote(encoded_name)
            if not name or "/" in name:
                return self._json_error(HTTPStatus.NOT_FOUND, "endpoint not found")
            body = {"channel": name, "subscribers": self.clients.subscribers(name)}
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
