"""Async WebSocket notification server with a SOAP health service."""

from __future__ import annotations

import argparse
import asyncio
import json
import signal
import threading
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any
from xml.etree import ElementTree
from xml.sax.saxutils import escape

import websockets
from websockets.exceptions import ConnectionClosed
from websockets.legacy.server import WebSocketServer, WebSocketServerProtocol


SOAP_ENV = "http://schemas.xmlsoap.org/soap/envelope/"
SERVICE_NS = "urn:notification-server"
SUPPORTED_TYPES = {"broadcast", "direct", "system"}
MAX_SOAP_REQUEST_SIZE = 64 * 1024


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def message(message_type: str, payload: dict[str, Any]) -> str:
    return json.dumps(
        {"type": message_type, "payload": payload, "timestamp": utc_timestamp()},
        separators=(",", ":"),
    )


class ClientRegistry:
    """A registry safe to inspect or mutate from any thread."""

    def __init__(self) -> None:
        self._clients: dict[str, WebSocketServerProtocol] = {}
        self._lock = threading.RLock()

    def add(self, client: WebSocketServerProtocol) -> str:
        client_id = str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = client
        return client_id

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)

    def get(self, client_id: str) -> WebSocketServerProtocol | None:
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> list[tuple[str, WebSocketServerProtocol]]:
        with self._lock:
            return list(self._clients.items())

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
                self.handle_soap_connection, self.host, self.soap_port
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
        if message_type == "system":
            await websocket.send(
                message(
                    "system",
                    {"event": "error", "detail": "system messages are server-only"},
                )
            )
        elif message_type == "broadcast":
            await self.broadcast(
                message("broadcast", {"sender_id": client_id, **payload})
            )
        else:
            await self._send_direct(client_id, websocket, payload)

    @staticmethod
    def _validate_message(incoming: Any) -> None:
        if not isinstance(incoming, dict):
            raise ValueError("message must be a JSON object")
        if set(incoming) != {"type", "payload", "timestamp"}:
            raise ValueError("message must contain only type, payload, and timestamp")
        if incoming["type"] not in SUPPORTED_TYPES:
            raise ValueError("unsupported message type")
        if not isinstance(incoming["payload"], dict):
            raise ValueError("payload must be an object")
        if not isinstance(incoming["timestamp"], str):
            raise ValueError("timestamp must be a string")

    async def broadcast(self, encoded_message: str) -> None:
        clients = self.clients.snapshot()
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
        forwarded_payload = {key: value for key, value in payload.items() if key != "client_id"}
        try:
            await recipient.send(
                message("direct", {"sender_id": sender_id, **forwarded_payload})
            )
        except ConnectionClosed:
            self.clients.remove(recipient_id)
            await sender.send(
                message("system", {"event": "error", "detail": "client disconnected"})
            )

    async def handle_soap_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            status, body = await self._soap_response(reader)
        except (ValueError, asyncio.IncompleteReadError) as exc:
            status = HTTPStatus.BAD_REQUEST
            body = self._soap_fault("Client", str(exc))
        except Exception:
            status = HTTPStatus.INTERNAL_SERVER_ERROR
            body = self._soap_fault("Server", "Internal server error")

        encoded_body = body.encode("utf-8")
        writer.write(
            f"HTTP/1.1 {status.value} {status.phrase}\r\n"
            "Content-Type: text/xml; charset=utf-8\r\n"
            f"Content-Length: {len(encoded_body)}\r\n"
            "Connection: close\r\n\r\n".encode("ascii")
            + encoded_body
        )
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def _soap_response(
        self, reader: asyncio.StreamReader
    ) -> tuple[HTTPStatus, str]:
        request_line = (await reader.readline()).decode("ascii").strip()
        parts = request_line.split()
        if len(parts) != 3 or parts[0] != "POST" or parts[1] != "/soap":
            raise ValueError("SOAP requests must use POST /soap")

        headers: dict[str, str] = {}
        while True:
            line = await reader.readline()
            if line in (b"\r\n", b"\n"):
                break
            name, separator, value = line.decode("ascii").partition(":")
            if not separator:
                raise ValueError("malformed HTTP header")
            headers[name.lower().strip()] = value.strip()

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
