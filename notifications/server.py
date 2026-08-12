"""WebSocket-based notification server.

Accepts WebSocket connections, assigns each client a unique ID, relays
messages between clients, and exposes a ``GET /health`` REST endpoint that
reports the number of connected clients.
"""

import json
import logging
from http import HTTPStatus

from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response

from .messages import make_message, parse_message
from .registry import ClientRegistry

logger = logging.getLogger(__name__)


class NotificationServer:
    """A WebSocket notification hub.

    Message envelopes follow the shape ``{"type": str, "payload": dict,
    "timestamp": str}`` and may carry an optional ``"channel"`` field. Supported
    types:

    * ``broadcast`` — delivered to every connected client, or only to the
      subscribers of the named channel when a ``"channel"`` field is present.
    * ``direct`` — routed to the client named in ``payload["target"]``.
    * ``system`` — server-originated messages (e.g. connection events).
    * ``subscribe`` — subscribes the sender to the named channel.
    * ``unsubscribe`` — removes the sender from the named channel.

    Clients may subscribe to any number of named channels (``"alerts"``,
    ``"system"``, ``"chat"``, ...) and channel messages only reach the clients
    subscribed to that channel.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        path: str = "/ws",
    ) -> None:
        self.host = host
        self.port = port
        self.path = path
        self.registry = ClientRegistry()
        self._server = None

    # -- lifecycle ----------------------------------------------------------

    async def start(self) -> None:
        """Bind the WebSocket server and begin accepting connections."""
        self._server = await serve(
            self._handler,
            self.host,
            self.port,
            process_request=self._process_request,
        )
        logger.info("notification server listening on %s:%s", self.host, self.port)

    async def close(self) -> None:
        """Stop the server and release the bound port."""
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    @property
    def bound_port(self) -> int:
        """Return the actual bound port (useful when port=0)."""
        sock = self._server.sockets[0]
        return sock.getsockname()[1]

    # -- HTTP handling ------------------------------------------------------

    @staticmethod
    def _json_response(body: dict, status: HTTPStatus = HTTPStatus.OK) -> Response:
        """Build a JSON REST response."""
        encoded = json.dumps(body).encode("utf-8")
        return Response(
            status_code=status,
            reason_phrase=status.phrase,
            headers=Headers(
                [
                    ("Content-Type", "application/json"),
                    ("Content-Length", str(len(encoded))),
                ]
            ),
            body=encoded,
        )

    async def _process_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        if request.path == "/health":
            return self._json_response({"clients": len(self.registry)})
        if request.path == "/channels":
            return self._json_response(self.registry.channels())
        if request.path.startswith("/channels/") and request.path.endswith(
            "/subscribers"
        ):
            name = request.path[len("/channels/") : -len("/subscribers")]
            return self._json_response(
                {
                    "channel": name,
                    "subscribers": sorted(self.registry.channel_members(name)),
                }
            )
        if request.path != self.path:
            return Response(
                status_code=HTTPStatus.NOT_FOUND,
                reason_phrase=HTTPStatus.NOT_FOUND.phrase,
                headers=Headers(
                    [
                        ("Content-Type", "text/plain; charset=utf-8"),
                        ("Content-Length", "9"),
                    ]
                ),
                body=b"Not Found",
            )
        return None

    # -- WebSocket connection handler ---------------------------------------

    async def _handler(self, connection: ServerConnection) -> None:
        client_id = self.registry.register(connection)
        try:
            await connection.send(
                make_message(
                    "system", {"event": "connected", "client_id": client_id}
                )
            )
            async for raw in connection:
                await self._route(client_id, raw)
        except ConnectionClosed:
            pass
        finally:
            self.registry.unregister(client_id)
            logger.info(
                "client %s disconnected (%d connected)",
                client_id,
                len(self.registry),
            )

    async def _route(self, sender_id: str, raw: str) -> None:
        """Process a message received from ``sender_id``."""
        try:
            message = parse_message(raw)
        except ValueError as exc:
            await self.send_system(sender_id, {"error": str(exc)})
            return

        msg_type = message["type"]
        payload = message["payload"]
        timestamp = message["timestamp"]
        channel = message.get("channel") or payload.get("channel")
        if channel is not None and not isinstance(channel, str):
            channel = None

        if msg_type == "broadcast":
            forwarded = dict(payload)
            forwarded.pop("channel", None)
            forwarded["from"] = sender_id
            if channel:
                await self.send_to_channel(
                    channel, forwarded, timestamp=timestamp
                )
            else:
                await self.broadcast(forwarded, timestamp=timestamp)

        elif msg_type == "direct":
            target = payload.get("target")
            if not isinstance(target, str) or not target:
                await self.send_system(
                    sender_id,
                    {"error": "direct message requires a string payload.target"},
                )
                return
            forwarded = {k: v for k, v in payload.items() if k != "target"}
            forwarded["from"] = sender_id
            if not await self.send_direct(target, forwarded, timestamp=timestamp):
                await self.send_system(
                    sender_id, {"error": f"no such client: {target}"}
                )

        elif msg_type == "subscribe":
            if not channel:
                await self.send_system(
                    sender_id,
                    {"error": "subscribe requires a channel"},
                )
                return
            self.registry.subscribe(sender_id, channel)
            logger.info(
                "client %s subscribed to channel %r", sender_id, channel
            )

        elif msg_type == "unsubscribe":
            if not channel:
                await self.send_system(
                    sender_id,
                    {"error": "unsubscribe requires a channel"},
                )
                return
            self.registry.unsubscribe(sender_id, channel)
            logger.info(
                "client %s unsubscribed from channel %r", sender_id, channel
            )

        else:  # "system"
            await self.send_system(sender_id, dict(payload), timestamp=timestamp)

    # -- public messaging API ------------------------------------------------

    async def broadcast(self, payload: dict, timestamp: str | None = None) -> int:
        """Send a broadcast message to every connected client.

        Returns the number of clients the message was delivered to.
        """
        raw = make_message("broadcast", payload, timestamp=timestamp)
        return await self._send_all(raw)

    async def send_to_channel(
        self, channel: str, payload: dict, timestamp: str | None = None
    ) -> int:
        """Send a broadcast message to the subscribers of a named channel.

        Returns the number of clients the message was delivered to.
        """
        raw = make_message(
            "broadcast", payload, timestamp=timestamp, channel=channel
        )
        delivered = 0
        for client_id in self.registry.channel_members(channel):
            connection = self.registry.get(client_id)
            if connection is None:
                continue
            try:
                await connection.send(raw)
                delivered += 1
            except ConnectionClosed:
                continue
        return delivered

    async def send_direct(
        self, client_id: str, payload: dict, timestamp: str | None = None
    ) -> bool:
        """Send a direct message to one client. Returns False if unknown."""
        connection = self.registry.get(client_id)
        if connection is None:
            return False
        await connection.send(make_message("direct", payload, timestamp=timestamp))
        return True

    async def send_system(
        self, client_id: str, payload: dict, timestamp: str | None = None
    ) -> bool:
        """Send a system message to one client. Returns False if unknown."""
        connection = self.registry.get(client_id)
        if connection is None:
            return False
        await connection.send(make_message("system", payload, timestamp=timestamp))
        return True

    async def system(self, payload: dict, timestamp: str | None = None) -> int:
        """Send a system message to every connected client."""
        raw = make_message("system", payload, timestamp=timestamp)
        return await self._send_all(raw)

    async def _send_all(self, raw: str) -> int:
        """Deliver ``raw`` to all clients, skipping ones that have dropped."""
        delivered = 0
        for _, connection in list(self.registry):
            try:
                await connection.send(raw)
                delivered += 1
            except ConnectionClosed:
                continue
        return delivered
