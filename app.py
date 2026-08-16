"""Entry point for the WebSocket notification server."""

import asyncio
import os

from notification_server import NotificationServer


async def main() -> None:
    server = NotificationServer(
        host=os.environ.get("HOST", "0.0.0.0"),
        ws_port=int(os.environ.get("WS_PORT", "8765")),
        http_port=int(os.environ.get("HTTP_PORT", "8000")),
    )
    await server.start()
    print(f"WebSocket server listening on {server.ws_url}")
    print(f"REST health endpoint on {server.http_url}")
    try:
        await asyncio.Future()  # run until interrupted
    finally:
        await server.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
