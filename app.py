"""Application entry point for the notification server."""

from notification_server import ClientRegistry, NotificationServer, main, make_message

__all__ = ["ClientRegistry", "NotificationServer", "make_message", "main"]


if __name__ == "__main__":
    main()
