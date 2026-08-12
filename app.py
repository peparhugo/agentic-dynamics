"""Command-line entry point for the notification server."""

from notification_server import NotificationServer, create_server

__all__ = ["NotificationServer", "create_server"]


if __name__ == "__main__":
    create_server().run()
