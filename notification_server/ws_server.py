"""Async notification server core: routing logic over a pluggable Transport."""
from __future__ import annotations

import logging
import uuid

from .broker import RedisBroker
from .messages import InvalidMessage, error_message, make_message, parse_message
from .redis_registry import RedisPresence
from .registry import ClientRegistry
from .store import MessageStore
from .transport import BaseTransport
from .ws_transport import WebSocketTransport

logger = logging.getLogger(__name__)


class NotificationServer:
    def __init__(
        self,
        registry: ClientRegistry | None = None,
        *,
        transport: BaseTransport | None = None,
        broker: RedisBroker | None = None,
        presence: RedisPresence | None = None,
        store: MessageStore | None = None,
    ) -> None:
        self.registry = registry or ClientRegistry()
        self.transport = transport or WebSocketTransport()
        self.broker = broker
        self.presence = presence
        self.store = store

    async def start(self) -> None:
        """Start the Redis subscriber worker, if a broker is configured.

        No-op when `broker` wasn't passed in, so plain in-process usage
        (the default) needs no lifecycle management at all.
        """
        if self.broker is not None:
            await self.broker.start(self._deliver_envelope)

    async def stop(self) -> None:
        """Stop the Redis subscriber worker, if a broker is configured."""
        if self.broker is not None:
            await self.broker.stop()

    async def handler(self, connection) -> None:
        client_id = str(uuid.uuid4())
        self.registry.add(client_id, connection)
        await self.transport.on_connect(connection)
        if self.presence is not None:
            await self.presence.add_client(client_id)
        try:
            await self._send(
                connection, make_message("system", {"event": "connected", "client_id": client_id})
            )
            async for raw in self.transport.receive(connection):
                await self._handle_raw(client_id, raw)
        finally:
            self.registry.remove(client_id)
            await self.transport.on_disconnect(connection)
            if self.presence is not None:
                await self.presence.remove_client(client_id)

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
        await self._persist(outgoing)
        if self.broker is not None:
            await self.broker.publish(dict(outgoing, _route="broadcast"))
            return
        await self._deliver_broadcast(outgoing, channel)

    async def _deliver_broadcast(self, outgoing: dict, channel: str | None) -> None:
        targets = (
            self.registry.connections_for_channel(channel)
            if channel
            else self.registry.connections()
        )
        await self.transport.broadcast(targets, outgoing)

    async def _subscribe(self, sender_id: str, message: dict) -> None:
        channel = message.get("channel")
        sender = self.registry.get(sender_id)
        if not channel:
            if sender is not None:
                await self._send(sender, error_message("subscribe requires a 'channel' field"))
            return
        self.registry.subscribe(sender_id, channel)
        if self.presence is not None:
            await self.presence.subscribe(sender_id, channel)
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
        if self.presence is not None:
            await self.presence.unsubscribe(sender_id, channel)
        if sender is not None:
            await self._send(
                sender, make_message("system", {"event": "unsubscribed", "channel": channel})
            )

    async def _direct(self, sender_id: str, message: dict) -> None:
        target_id = message["payload"].get("target_id")
        outgoing = dict(message, sender_id=sender_id)

        if self.broker is not None and self.presence is not None:
            connected = target_id is not None and (
                target_id in self.registry or await self.presence.is_connected(target_id)
            )
            if not connected:
                sender = self.registry.get(sender_id)
                if sender is not None:
                    await self._send(
                        sender, error_message(f"target_id {target_id!r} is not connected")
                    )
                return
            await self._persist(outgoing)
            await self.broker.publish(dict(outgoing, _route="direct", _target_id=target_id))
            return

        target = self.registry.get(target_id) if target_id else None
        if target is None:
            sender = self.registry.get(sender_id)
            if sender is not None:
                await self._send(
                    sender, error_message(f"target_id {target_id!r} is not connected")
                )
            return
        await self._persist(outgoing)
        await self._send(target, outgoing)

    async def _deliver_envelope(self, envelope: dict) -> None:
        """Handle an envelope received from the Redis broker's subscriber.

        Runs on every server instance (including the publisher) and matches
        the envelope against this instance's own local registry only.
        """
        route = envelope.pop("_route", None)
        if route == "broadcast":
            await self._deliver_broadcast(envelope, envelope.get("channel"))
        elif route == "direct":
            target_id = envelope.pop("_target_id", None)
            target = self.registry.get(target_id) if target_id else None
            if target is not None:
                await self._send(target, envelope)

    async def _persist(self, outgoing: dict) -> None:
        if self.store is None:
            return
        await self.store.arecord(
            outgoing["type"], outgoing["payload"], outgoing["timestamp"], outgoing.get("channel")
        )

    async def _send(self, connection, message: dict) -> None:
        await self.transport.send_message(connection, message)

    def serve(self, host: str = "localhost", port: int = 8765):
        return self.transport.serve(self.handler, host, port)
