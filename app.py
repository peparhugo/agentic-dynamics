"""Async WebSocket notification server with a SOAP health service."""

from __future__ import annotations

import argparse
import asyncio
import json
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any
from xml.etree import ElementTree

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed


SOAP_ENV = "http://schemas.xmlsoap.org/soap/envelope/"
SERVICE_NS = "urn:notification-server"
SUPPORTED_TYPES = {"broadcast", "direct", "system"}


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def message(message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"type": message_type, "payload": payload, "timestamp": utc_timestamp()}


class ClientRegistry:
    """A registry safe to inspect or mutate from multiple threads."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._lock = threading.RLock()

    def add(self, client: ServerConnection) -> str:
        client_id = str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = client
        return client_id

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)

    def get(self, client_id: str) -> ServerConnection | None:
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> list[tuple[str, ServerConnection]]:
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
        self._websocket_server: Server | None = None
        self._soap_server: asyncio.Server | None = None

    async def start(self) -> None:
        self._websocket_server = await serve(
            self.handle_websocket, self.host, self.websocket_port
        )
        try:
            self._soap_server = await asyncio.start_server(
                self.handle_soap_connection, self.host, self.soap_port
            )
        except BaseException:
            self._websocket_server.close()
            await self._websocket_server.wait_closed()
            self._websocket_server = None
            raise

        websocket_socket = self._websocket_server.sockets[0]
        soap_socket = self._soap_server.sockets[0]
        self.websocket_port = websocket_socket.getsockname()[1]
        self.soap_port = soap_socket.getsockname()[1]

    async def stop(self) -> None:
        if self._websocket_server is not None:
            self._websocket_server.close()
            await self._websocket_server.wait_closed()
            self._websocket_server = None
        if self._soap_server is not None:
            self._soap_server.close()
            await self._soap_server.wait_closed()
            self._soap_server = None

    async def serve_forever(self) -> None:
        await self.start()
        assert self._websocket_server is not None
        assert self._soap_server is not None
        async with self._websocket_server, self._soap_server:
            await asyncio.gather(
                self._websocket_server.serve_forever(),
                self._soap_server.serve_forever(),
            )

    async def handle_websocket(self, websocket: ServerConnection) -> None:
        client_id = self.clients.add(websocket)
        try:
            await self._send(
                websocket,
                message("system", {"event": "connected", "client_id": client_id}),
            )
            async for raw_message in websocket:
                await self._handle_message(client_id, websocket, raw_message)
        except ConnectionClosed:
            pass
        finally:
            self.clients.remove(client_id)

    async def _handle_message(
        self, client_id: str, websocket: ServerConnection, raw_message: str | bytes
    ) -> None:
        try:
            incoming = json.loads(raw_message)
        except (json.JSONDecodeError, UnicodeDecodeError):
            await self._error(websocket, "message must be valid JSON")
            return

        if not isinstance(incoming, dict):
            await self._error(websocket, "message must be a JSON object")
            return
        message_type = incoming.get("type")
        payload = incoming.get("payload")
        if message_type not in SUPPORTED_TYPES or not isinstance(payload, dict):
            await self._error(websocket, "type and payload are invalid")
            return
        if message_type == "system":
            await self._error(websocket, "system messages are server-only")
            return

        outgoing_payload = dict(payload)
        outgoing_payload["sender_id"] = client_id
        outgoing = message(message_type, outgoing_payload)
        if message_type == "broadcast":
            await self.broadcast(outgoing)
            return

        target_id = payload.get("client_id")
        if not isinstance(target_id, str):
            await self._error(websocket, "direct payload requires client_id")
            return
        target = self.clients.get(target_id)
        if target is None:
            await self._error(websocket, "direct message target is not connected")
            return
        await self._send(target, outgoing)

    async def broadcast(self, outgoing: dict[str, Any]) -> None:
        clients = self.clients.snapshot()
        if not clients:
            return
        results = await asyncio.gather(
            *(self._send(client, outgoing) for _, client in clients),
            return_exceptions=True,
        )
        for (client_id, _), result in zip(clients, results):
            if isinstance(result, ConnectionClosed):
                self.clients.remove(client_id)

    async def _error(self, websocket: ServerConnection, detail: str) -> None:
        await self._send(websocket, message("system", {"event": "error", "detail": detail}))

    @staticmethod
    async def _send(websocket: ServerConnection, outgoing: dict[str, Any]) -> None:
        await websocket.send(json.dumps(outgoing, separators=(",", ":")))

    async def handle_soap_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            request_line = await asyncio.wait_for(reader.readline(), timeout=5)
            if not request_line:
                return
            parts = request_line.decode("ascii", errors="replace").strip().split()
            if len(parts) != 3:
                await self._write_http(writer, HTTPStatus.BAD_REQUEST, b"Bad request")
                return
            method, path, _ = parts
            headers: dict[str, str] = {}
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=5)
                if line in (b"\r\n", b"\n", b""):
                    break
                name, separator, value = line.decode("latin-1").partition(":")
                if not separator:
                    await self._write_http(writer, HTTPStatus.BAD_REQUEST, b"Bad request")
                    return
                headers[name.strip().lower()] = value.strip()

            if method != "POST" or path != "/health":
                await self._write_http(writer, HTTPStatus.NOT_FOUND, b"Not found")
                return
            try:
                content_length = int(headers.get("content-length", "0"))
            except ValueError:
                await self._write_http(writer, HTTPStatus.BAD_REQUEST, b"Bad request")
                return
            if content_length <= 0 or content_length > 1_000_000:
                await self._write_http(writer, HTTPStatus.BAD_REQUEST, b"Bad request")
                return
            body = await asyncio.wait_for(reader.readexactly(content_length), timeout=5)
            response = self._soap_health_response(body)
            await self._write_http(writer, HTTPStatus.OK, response, "text/xml; charset=utf-8")
        except (asyncio.IncompleteReadError, asyncio.TimeoutError):
            if not writer.is_closing():
                await self._write_http(writer, HTTPStatus.BAD_REQUEST, b"Bad request")
        finally:
            writer.close()
            await writer.wait_closed()

    def _soap_health_response(self, body: bytes) -> bytes:
        try:
            root = ElementTree.fromstring(body)
            soap_body = root.find(f"{{{SOAP_ENV}}}Body")
            operation = next(iter(soap_body)) if soap_body is not None else None
            operation_name = operation.tag.rsplit("}", 1)[-1] if operation is not None else ""
            if operation_name != "Health":
                raise ValueError("unsupported SOAP operation")
        except (ElementTree.ParseError, ValueError):
            return self._soap_fault("Client", "Expected a SOAP Health operation")

        envelope = ElementTree.Element(f"{{{SOAP_ENV}}}Envelope")
        response_body = ElementTree.SubElement(envelope, f"{{{SOAP_ENV}}}Body")
        health = ElementTree.SubElement(response_body, f"{{{SERVICE_NS}}}HealthResponse")
        count = ElementTree.SubElement(health, f"{{{SERVICE_NS}}}connectedClientCount")
        count.text = str(self.clients.count)
        return ElementTree.tostring(envelope, encoding="utf-8", xml_declaration=True)

    @staticmethod
    def _soap_fault(code: str, text: str) -> bytes:
        envelope = ElementTree.Element(f"{{{SOAP_ENV}}}Envelope")
        body = ElementTree.SubElement(envelope, f"{{{SOAP_ENV}}}Body")
        fault = ElementTree.SubElement(body, f"{{{SOAP_ENV}}}Fault")
        ElementTree.SubElement(fault, "faultcode").text = code
        ElementTree.SubElement(fault, "faultstring").text = text
        return ElementTree.tostring(envelope, encoding="utf-8", xml_declaration=True)

    @staticmethod
    async def _write_http(
        writer: asyncio.StreamWriter,
        status: HTTPStatus,
        body: bytes,
        content_type: str = "text/plain; charset=utf-8",
    ) -> None:
        headers = (
            f"HTTP/1.1 {status.value} {status.phrase}\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii")
        writer.write(headers + body)
        await writer.drain()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--websocket-port", type=int, default=8765)
    parser.add_argument("--soap-port", type=int, default=8080)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = NotificationServer(args.host, args.websocket_port, args.soap_port)
    asyncio.run(server.serve_forever())


if __name__ == "__main__":
    main()
