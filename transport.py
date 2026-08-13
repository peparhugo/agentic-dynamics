"""Abstract base transport layer for notification server."""

from abc import ABC, abstractmethod
from message_handler import Message


class BaseTransport(ABC):
    """Abstract base class for transport mechanisms."""

    @abstractmethod
    async def on_connect(self, client_id: str) -> None:
        """Called when a client connects."""
        pass

    @abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        """Called when a client disconnects."""
        pass

    @abstractmethod
    async def send_message(self, client_id: str, message: Message) -> None:
        """Send a message to a specific client."""
        pass

    @abstractmethod
    async def broadcast(self, message: Message, channel: str = None) -> None:
        """Broadcast a message to all clients or channel subscribers."""
        pass

    @abstractmethod
    async def run(self) -> None:
        """Start the transport server."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the transport server."""
        pass
