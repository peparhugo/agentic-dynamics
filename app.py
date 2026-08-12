"""WebSocket-based notification server.

Run with::

    python app.py [--host 127.0.0.1] [--port 8765] [--path /ws]
"""

import argparse
import asyncio
import logging

from notifications.server import NotificationServer


async def run() -> None:
    parser = argparse.ArgumentParser(description="WebSocket notification server")
    parser.add_argument("--host", default="127.0.0.1", help="interface to bind")
    parser.add_argument("--port", type=int, default=8765, help="TCP port")
    parser.add_argument("--path", default="/ws", help="WebSocket endpoint path")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )

    server = NotificationServer(host=args.host, port=args.port, path=args.path)
    await server.start()
    try:
        await asyncio.Event().wait()
    finally:
        await server.close()


if __name__ == "__main__":
    asyncio.run(run())
