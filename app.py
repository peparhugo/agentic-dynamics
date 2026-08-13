"""Async WebSocket notification service with a SOAP health operation."""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any
from xml.etree import ElementTree as ET

from websockets.server import WebSocketServerProtocol, serve


SUPPORTED_MESSAGE_TYPES = frozenset({"broadcast", "direct", "system", "subscribe", "unsubscribe"})
SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
SERVICE_NS = "urn:notification-service"


class NotificationServer:
    """Coordinates connected clients and validates notification messages."""

    def __init__(self) -> None:
        self.clients: dict[str, WebSocketServerProtocol] = {}
        self.channels: dict[str, set[str]] = {}
        self._clients_lock = asyncio.Lock()

    async def register(self, websocket: WebSocketServerProtocol) -> str:
        client_id = str(uuid.uuid4())
        async with self._clients_lock:
            self.clients[client_id] = websocket
        await self.send(client_id, "system", {"event": "connected", "client_id": client_id})
        return client_id

    async def unregister(self, client_id: str) -> None:
        async with self._clients_lock:
            self.clients.pop(client_id, None)
            for channel in tuple(self.channels):
                self.channels[channel].discard(client_id)
                if not self.channels[channel]:
                    del self.channels[channel]

    async def client_count(self) -> int:
        async with self._clients_lock:
            return len(self.clients)

    @staticmethod
    def message(message_type: str, payload: dict[str, Any], channel: str | None = None) -> str:
        message = {
            "type": message_type,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if channel is not None:
            message["channel"] = channel
        return json.dumps(message)

    async def send(
        self, client_id: str, message_type: str, payload: dict[str, Any], channel: str | None = None
    ) -> bool:
        async with self._clients_lock:
            websocket = self.clients.get(client_id)
        if websocket is None:
            return False
        try:
            await websocket.send(self.message(message_type, payload, channel))
        except Exception:
            await self.unregister(client_id)
            return False
        return True

    async def broadcast(self, message_type: str, payload: dict[str, Any], channel: str | None = None) -> None:
        async with self._clients_lock:
            client_ids = tuple(self.channels.get(channel, ())) if channel is not None else tuple(self.clients)
        await asyncio.gather(*(self.send(client_id, message_type, payload, channel) for client_id in client_ids))

    async def subscribe(self, client_id: str, channel: str) -> None:
        async with self._clients_lock:
            if client_id in self.clients:
                self.channels.setdefault(channel, set()).add(client_id)

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        async with self._clients_lock:
            subscribers = self.channels.get(channel)
            if subscribers is not None:
                subscribers.discard(client_id)
                if not subscribers:
                    del self.channels[channel]

    async def channel_counts(self) -> dict[str, int]:
        async with self._clients_lock:
            return {channel: len(subscribers) for channel, subscribers in self.channels.items()}

    async def channel_subscribers(self, channel: str) -> list[str]:
        async with self._clients_lock:
            return sorted(self.channels.get(channel, ()))

    async def websocket_handler(self, websocket: WebSocketServerProtocol) -> None:
        client_id = await self.register(websocket)
        try:
            async for raw_message in websocket:
                await self.handle_message(client_id, raw_message)
        finally:
            await self.unregister(client_id)

    async def handle_message(self, sender_id: str, raw_message: str) -> None:
        try:
            message = json.loads(raw_message)
            message_type = message["type"]
            payload = message["payload"]
            if message_type not in SUPPORTED_MESSAGE_TYPES or not isinstance(payload, dict):
                raise ValueError
            channel = message.get("channel")
            if channel is not None and (not isinstance(channel, str) or not channel):
                raise ValueError
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            await self.send(sender_id, "system", {"event": "error", "message": "invalid message"})
            return

        if message_type == "subscribe":
            if channel is None:
                await self.send(sender_id, "system", {"event": "error", "message": "invalid channel"})
                return
            await self.subscribe(sender_id, channel)
        elif message_type == "unsubscribe":
            if channel is None:
                await self.send(sender_id, "system", {"event": "error", "message": "invalid channel"})
                return
            await self.unsubscribe(sender_id, channel)
        elif message_type == "broadcast":
            await self.broadcast("broadcast", payload, channel)
        elif message_type == "direct":
            recipient_id = payload.get("client_id")
            content = payload.get("message")
            if not isinstance(recipient_id, str) or not isinstance(content, dict):
                await self.send(sender_id, "system", {"event": "error", "message": "invalid direct message"})
                return
            await self.send(recipient_id, "direct", content)
        else:
            await self.broadcast("system", payload, channel)

    async def soap_handler(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request = await reader.readuntil(b"\r\n\r\n")
            headers = request.decode("iso-8859-1")
            method, path, _ = headers.split("\r\n", 1)[0].split(" ", 2)
            if method == "GET" and path == "/channels":
                response = self.http_response("200 OK", json.dumps(await self.channel_counts()).encode(), "application/json")
            elif method == "GET" and path.startswith("/channels/") and path.endswith("/subscribers"):
                channel = path[len("/channels/") : -len("/subscribers")]
                if not channel or "/" in channel:
                    response = self.http_response("404 Not Found", b'{"error":"not found"}', "application/json")
                else:
                    subscribers = await self.channel_subscribers(channel)
                    response = self.http_response("200 OK", json.dumps(subscribers).encode(), "application/json")
            elif method != "POST":
                response = self.http_response("404 Not Found", b'{"error":"not found"}', "application/json")
            else:
                response = await self.soap_response(headers, reader)
        except (ValueError, ET.ParseError, asyncio.IncompleteReadError, UnicodeDecodeError):
            response = self.http_response("400 Bad Request", self.soap_fault("Invalid SOAP request"))
        writer.write(response)
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def soap_response(self, headers: str, reader: asyncio.StreamReader) -> bytes:
        content_length = next(
            int(line.split(":", 1)[1].strip())
            for line in headers.split("\r\n")
            if line.lower().startswith("content-length:")
        )
        body = await reader.readexactly(content_length)
        root = ET.fromstring(body)
        operation = next(iter(root)).find(".//{*}Health")
        if operation is None:
            raise ValueError("unsupported SOAP operation")
        return self.http_response("200 OK", self.soap_health_response(await self.client_count()))

    @staticmethod
    def soap_health_response(client_count: int) -> bytes:
        return (
            f'<?xml version="1.0" encoding="utf-8"?><soap:Envelope xmlns:soap="{SOAP_NS}" '
            f'xmlns:ns="{SERVICE_NS}"><soap:Body><ns:HealthResponse><ns:connectedClientCount>'
            f"{client_count}</ns:connectedClientCount></ns:HealthResponse></soap:Body></soap:Envelope>"
        ).encode()

    @staticmethod
    def soap_fault(message: str) -> bytes:
        return (
            f'<?xml version="1.0" encoding="utf-8"?><soap:Envelope xmlns:soap="{SOAP_NS}"><soap:Body>'
            f"<soap:Fault><faultcode>soap:Client</faultcode><faultstring>{message}</faultstring>"
            f"</soap:Fault></soap:Body></soap:Envelope>"
        ).encode()

    @staticmethod
    def http_response(status: str, body: bytes, content_type: str = "text/xml; charset=utf-8") -> bytes:
        return (
            f"HTTP/1.1 {status}\r\nContent-Type: {content_type}\r\n"
            f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n"
        ).encode() + body


async def main() -> None:
    server = NotificationServer()
    async with serve(server.websocket_handler, "localhost", 8765), await asyncio.start_server(
        server.soap_handler, "localhost", 8766
    ):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
