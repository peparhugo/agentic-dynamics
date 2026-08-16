"""Application entry point for the notification server."""

from notification_server import NotificationServer, main

__all__ = ["NotificationServer", "main"]


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
