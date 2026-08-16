"""WebSocket notification server — CLI entry point."""

import argparse
import asyncio
import logging

from notifications import NotificationServer

logging.basicConfig(level=logging.INFO)


async def main(host: str, ws_port: int, rest_port: int) -> None:
    server = NotificationServer(host=host, ws_port=ws_port, rest_port=rest_port)
    await server.start()
    try:
        await asyncio.Future()  # run forever
    finally:
        await server.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WebSocket notification server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--ws-port", type=int, default=8765)
    parser.add_argument("--rest-port", type=int, default=8080)
    args = parser.parse_args()
    try:
        asyncio.run(main(args.host, args.ws_port, args.rest_port))
    except KeyboardInterrupt:
        pass
