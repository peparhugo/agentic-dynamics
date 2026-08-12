"""Application entry point for the notification server."""

from notification_server import (
    BaseTransport,
    ClientRegistry,
    NotificationServer,
    WebSocketTransport,
    main,
    make_message,
)

__all__ = [
    "BaseTransport",
    "ClientRegistry",
    "NotificationServer",
    "WebSocketTransport",
    "make_message",
    "main",
]


if __name__ == "__main__":
    main()
