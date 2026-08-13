"""Transport-agnostic notification server.

Clients connect, are assigned a unique ID, and can broadcast JSON messages
to every other connected client, to a channel's subscribers, or send one
directly to a specific client ID. How clients actually connect and receive
bytes is delegated entirely to a pluggable `Transport` (see `transport.py`);
this module contains only the core notification logic: parsing, routing,
persistence, and fan-out across server instances via Redis.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Any, Iterable

import websockets

from .messages import InvalidMessage, build_message, parse_message
from .redis_bus import RedisBus
from .registry import ClientRegistry
from .store import MessageStore
from .transport import BaseTransport
from .websocket_transport import WebSocketTransport

logger = logging.getLogger("notification_server")

# Message types that represent actual notification content, as opposed to
# connection control-plane chatter (system/subscribe/unsubscribe). These are
# the ones persisted to SQLite and distributed over the Redis bus.
CONTENT_TYPES = {"broadcast", "direct"}


class NotificationServer:
    """Ties together a pluggable transport, the client registry, the Redis
    pub/sub bus, and SQLite history.

    `redis_client` and `db_path` are both optional so existing single-instance,
    in-memory behavior keeps working with no configuration at all: pass neither
    and every message stays local, exactly like before Redis was introduced.
    Pass a redis(.asyncio)-compatible client to fan messages out to other
    server instances sharing the same broker, and/or a db_path to persist
    message history to SQLite.

    `transport` selects the wire protocol: a `TRANSPORTS` key (also readable
    from the `TRANSPORT` env var), or a `BaseTransport` subclass/instance
    directly. Defaults to `WebSocketTransport`.
    """

    #: Registry of transports selectable by name via the `transport` kwarg
    #: or the `TRANSPORT` env var. Adding a new transport means adding an
    #: entry here, not modifying any of the dispatch/routing logic below.
    TRANSPORTS: dict[str, type[BaseTransport]] = {
        "websocket": WebSocketTransport,
    }

    def __init__(
        self,
        redis_client: Any = None,
        db_path: str | None = None,
        server_id: str | None = None,
        transport: "str | type[BaseTransport] | BaseTransport | None" = None,
    ) -> None:
        self.server_id = server_id or uuid.uuid4().hex
        self.registry = ClientRegistry(redis_client=redis_client, server_id=self.server_id)
        self.bus = RedisBus(redis_client) if redis_client is not None else None
        self.store = MessageStore(db_path or os.environ.get("DATABASE_URL", "notification_server.db"))
        self._started = False

        self.transport = self._make_transport(transport)
        # `handler`/`process_request` are the entry points a transport's own
        # server loop (e.g. `websockets.serve`) is wired up to; not every
        # transport has both (e.g. a raw-TCP transport has no HTTP upgrade
        # step), so `process_request` is only set when the transport exposes it.
        self.handler = self.transport.on_connect
        self.process_request = getattr(self.transport, "process_request", None)

    def _make_transport(
        self, transport: "str | type[BaseTransport] | BaseTransport | None"
    ) -> BaseTransport:
        if isinstance(transport, BaseTransport):
            return transport
        if transport is None:
            transport = os.environ.get("TRANSPORT", "websocket")
        if isinstance(transport, str):
            try:
                transport_cls = self.TRANSPORTS[transport]
            except KeyError:
                raise ValueError(f"unknown transport: {transport!r}") from None
        else:
            transport_cls = transport
        return transport_cls(self)

    async def start(self) -> None:
        """Idempotently subscribe to the Redis bus, if one is configured."""
        if self.bus is not None and not self._started:
            await self.bus.start(self._on_bus_message)
            self._started = True

    async def close(self) -> None:
        if self.bus is not None:
            await self.bus.stop()
        self.store.close()

    async def _client_connected(self, client_id: str) -> None:
        logger.info("client %s connected", client_id)
        await self.transport.send_message(client_id, build_message("system", {
            "event": "connected",
            "client_id": client_id,
        }))
        await self._distribute(
            build_message("system", {
                "event": "client_joined",
                "client_id": client_id,
                "connected_clients": await self.registry.global_count(),
            }),
            exclude=(client_id,),
        )

    async def _client_disconnected(self, client_id: str) -> None:
        logger.info("client %s disconnected", client_id)
        await self._distribute(
            build_message("system", {
                "event": "client_left",
                "client_id": client_id,
                "connected_clients": await self.registry.global_count(),
            })
        )

    async def _dispatch(self, client_id: str, raw: str) -> None:
        try:
            message = parse_message(raw)
        except InvalidMessage as exc:
            await self.transport.send_message(client_id, build_message("system", {
                "event": "error",
                "detail": str(exc),
            }))
            return

        msg_type = message["type"]
        payload = message["payload"]

        if msg_type == "broadcast":
            channel = payload.get("channel")
            out_message = build_message("broadcast", {**payload, "from": client_id})
            await self._persist(out_message, channel)
            await self._distribute(out_message, channel=channel)
        elif msg_type == "direct":
            await self._handle_direct(client_id, payload)
        elif msg_type == "subscribe":
            await self._handle_subscribe(client_id, payload)
        elif msg_type == "unsubscribe":
            await self._handle_unsubscribe(client_id, payload)
        else:  # "system" — reserved for server-originated messages
            await self.transport.send_message(client_id, build_message("system", {
                "event": "error",
                "detail": "clients may not send system messages",
            }))

    async def _handle_subscribe(self, client_id: str, payload: dict) -> None:
        channel = payload.get("channel")
        if not isinstance(channel, str) or not channel:
            await self.transport.send_message(client_id, build_message("system", {
                "event": "error",
                "detail": "subscribe requires a non-empty 'channel' string",
            }))
            return
        await self.registry.subscribe(client_id, channel)
        await self.transport.send_message(client_id, build_message("system", {
            "event": "subscribed",
            "channel": channel,
            "client_id": client_id,
        }))

    async def _handle_unsubscribe(self, client_id: str, payload: dict) -> None:
        channel = payload.get("channel")
        if not isinstance(channel, str) or not channel:
            await self.transport.send_message(client_id, build_message("system", {
                "event": "error",
                "detail": "unsubscribe requires a non-empty 'channel' string",
            }))
            return
        await self.registry.unsubscribe(client_id, channel)
        await self.transport.send_message(client_id, build_message("system", {
            "event": "unsubscribed",
            "channel": channel,
            "client_id": client_id,
        }))

    async def _handle_direct(self, sender_id: str, payload: dict) -> None:
        target_id = payload.get("target")
        # `exists` (not just "connected to this instance") is what lets a
        # direct message find its target when the two clients are on
        # different server instances sharing the same Redis backbone.
        target_exists = await self.registry.exists(target_id) if target_id else False
        if not target_exists:
            await self.transport.send_message(sender_id, build_message("system", {
                "event": "error",
                "detail": f"unknown target: {target_id!r}",
            }))
            return
        message = build_message("direct", {**payload, "from": sender_id})
        await self._persist(message, channel=None)
        await self._distribute(message, target=target_id)

    async def _distribute(
        self,
        message: dict,
        *,
        channel: str | None = None,
        target: str | None = None,
        exclude: Iterable[str] = (),
    ) -> None:
        """Route `message` to its recipients, via the Redis bus if one is configured.

        With a bus, this instance only ever publishes; delivery to local
        clients happens in `_deliver_locally`, invoked for every instance
        (this one included) when the envelope comes back off the
        subscription. Without a bus, delivery happens immediately, in place.
        """
        envelope = {"message": message, "channel": channel, "target": target, "exclude": list(exclude)}
        if self.bus is not None:
            await self.bus.publish(envelope)
        else:
            await self._deliver_locally(envelope)

    async def _on_bus_message(self, envelope: dict) -> None:
        await self._deliver_locally(envelope)

    async def _deliver_locally(self, envelope: dict) -> None:
        message = envelope["message"]
        channel = envelope.get("channel")
        target = envelope.get("target")
        exclude = envelope.get("exclude") or ()

        if target:
            await self.transport.send_message(target, message)
            return

        await self.transport.broadcast(message, channel=channel, exclude=exclude)

    async def _persist(self, message: dict, channel: str | None) -> None:
        if message["type"] not in CONTENT_TYPES:
            return
        await asyncio.to_thread(
            self.store.save_message,
            message["type"],
            message["payload"],
            message["timestamp"],
            channel,
        )


def create_app() -> NotificationServer:
    redis_client = None
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        import redis.asyncio as redis_asyncio
        redis_client = redis_asyncio.from_url(redis_url)
    db_path = os.environ.get("DATABASE_URL", "notification_server.db")
    return NotificationServer(redis_client=redis_client, db_path=db_path)


async def run_server(host: str = "localhost", port: int = 8765) -> None:
    app = create_app()
    await app.start()
    try:
        async with websockets.serve(app.handler, host, port, process_request=app.process_request):
            logger.info("notification server listening on %s:%s", host, port)
            await asyncio.Future()
    finally:
        await app.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
