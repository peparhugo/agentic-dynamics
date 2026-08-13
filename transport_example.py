"""
Example transport implementations to demonstrate the pluggable design.

This shows how new transport mechanisms can be added without modifying
the core NotificationServer logic.
"""

from transport import BaseTransport


class SSETransport(BaseTransport):
    """Server-Sent Events transport (example implementation)."""

    async def send_message(self, client_id: str, message: dict) -> None:
        """Send a message to a specific client via SSE."""
        # In a real implementation, this would use the SSE connection
        # to push the message to the client
        pass

    async def broadcast(
        self, message: dict, exclude: str | None = None, channel: str | None = None
    ) -> None:
        """Broadcast a message to all clients or to a specific channel via SSE."""
        # In a real implementation, this would iterate over all SSE connections
        # and send the message to each one (excluding if specified)
        pass


class PollingTransport(BaseTransport):
    """Long-polling transport (example implementation)."""

    async def send_message(self, client_id: str, message: dict) -> None:
        """Store a message for the next polling request from the client."""
        # In a real implementation, this would store messages in a queue
        # that the client retrieves on its next poll
        pass

    async def broadcast(
        self, message: dict, exclude: str | None = None, channel: str | None = None
    ) -> None:
        """Queue a message for all polling clients."""
        # In a real implementation, this would queue messages for all
        # active polling clients (excluding if specified)
        pass
