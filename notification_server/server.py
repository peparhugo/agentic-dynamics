"""Entry point wiring the WebSocket notification server and SOAP health API together."""
from __future__ import annotations

import asyncio
import logging
import os
import uuid

from aiohttp import web

from .broker import RedisBroker
from .redis_registry import RedisPresence
from .registry import ClientRegistry
from .soap import create_soap_app
from .store import MessageStore
from .transport import BaseTransport
from .ws_server import NotificationServer
from .ws_transport import WebSocketTransport

logger = logging.getLogger(__name__)

TRANSPORTS: dict[str, type[BaseTransport]] = {
    "websocket": WebSocketTransport,
}


def _db_path(database_url: str) -> str:
    if database_url.startswith("sqlite:///"):
        return database_url[len("sqlite:///"):]
    return database_url


def _build_transport(name: str | None = None) -> BaseTransport:
    """Build the configured Transport; selected by the `TRANSPORT` env var.

    Defaults to `websocket`. Adding a new mechanism (SSE, polling, raw TCP,
    ...) means writing a `BaseTransport` subclass and registering it in
    `TRANSPORTS` here — the core `NotificationServer` needs no changes.
    """
    name = (name if name is not None else os.environ.get("TRANSPORT", "websocket")).lower()
    try:
        transport_cls = TRANSPORTS[name]
    except KeyError:
        raise ValueError(
            f"unknown transport {name!r}; expected one of {sorted(TRANSPORTS)}"
        ) from None
    return transport_cls()


async def run(
    ws_host: str = "localhost",
    ws_port: int = 8765,
    soap_host: str = "localhost",
    soap_port: int = 8080,
    redis_url: str | None = None,
    database_url: str | None = None,
    transport: BaseTransport | None = None,
) -> None:
    redis_url = redis_url if redis_url is not None else os.environ.get("REDIS_URL")
    database_url = database_url or os.environ.get("DATABASE_URL", "notifications.db")
    transport = transport or _build_transport()

    registry = ClientRegistry()
    store = MessageStore(_db_path(database_url))

    broker = None
    presence = None
    redis_client = None
    if redis_url:
        import redis.asyncio as redis_asyncio

        redis_client = redis_asyncio.from_url(redis_url)
        broker = RedisBroker(redis_client)
        presence = RedisPresence(redis_client, server_id=str(uuid.uuid4()))
        logger.info("Redis pub/sub backbone enabled via %s", redis_url)

    notification_server = NotificationServer(
        registry, transport=transport, broker=broker, presence=presence, store=store
    )

    soap_app = create_soap_app(registry, store=store)
    runner = web.AppRunner(soap_app)
    await runner.setup()
    site = web.TCPSite(runner, soap_host, soap_port)
    await site.start()
    logger.info("SOAP health API listening on http://%s:%s/health", soap_host, soap_port)

    await notification_server.start()
    try:
        async with notification_server.serve(ws_host, ws_port):
            logger.info("WebSocket server listening on ws://%s:%s", ws_host, ws_port)
            await asyncio.Future()  # run forever
    finally:
        await notification_server.stop()
        if redis_client is not None:
            await redis_client.aclose()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
