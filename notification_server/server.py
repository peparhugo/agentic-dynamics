"""Entry point wiring the WebSocket notification server and SOAP health API together."""
from __future__ import annotations

import asyncio
import logging

from aiohttp import web

from .registry import ClientRegistry
from .soap import create_soap_app
from .ws_server import NotificationServer

logger = logging.getLogger(__name__)


async def run(
    ws_host: str = "localhost",
    ws_port: int = 8765,
    soap_host: str = "localhost",
    soap_port: int = 8080,
) -> None:
    registry = ClientRegistry()
    notification_server = NotificationServer(registry)

    soap_app = create_soap_app(registry)
    runner = web.AppRunner(soap_app)
    await runner.setup()
    site = web.TCPSite(runner, soap_host, soap_port)
    await site.start()
    logger.info("SOAP health API listening on http://%s:%s/health", soap_host, soap_port)

    async with notification_server.serve(ws_host, ws_port):
        logger.info("WebSocket server listening on ws://%s:%s", ws_host, ws_port)
        await asyncio.Future()  # run forever


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
