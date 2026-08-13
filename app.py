"""
Application entry point for the WebSocket-based notification server.

Run with:
    python app.py
"""

import asyncio

from notification_server import main

if __name__ == "__main__":
    asyncio.run(main())
