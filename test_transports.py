from collections.abc import Iterable
from typing import Any

import pytest

from app import BaseTransport, NotificationServer, WebSocketTransport
from transports import TRANSPORTS


class RecordingTransport(BaseTransport):
    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        super().__init__(host, port)
        self.sent: list[tuple[str, dict[str, Any]]] = []
        self.broadcasts: list[tuple[dict[str, Any], list[str] | None]] = []

    async def on_connect(self, connection: Any) -> str:
        del connection
        assert self.application is not None
        await self.application.transport_connected("custom-client")
        return "custom-client"

    async def on_disconnect(self, client_id: str) -> None:
        assert self.application is not None
        await self.application.transport_disconnected(client_id)

    async def send_message(self, client_id: str, notification: dict[str, Any]) -> None:
        self.sent.append((client_id, notification))

    async def broadcast(
        self,
        notification: dict[str, Any],
        client_ids: Iterable[str] | None = None,
    ) -> None:
        self.broadcasts.append(
            (notification, None if client_ids is None else list(client_ids))
        )


@pytest.mark.asyncio
async def test_notification_core_delivers_through_custom_transport():
    transport = RecordingTransport()
    notification = {
        "type": "broadcast",
        "payload": {"text": "transport independent"},
        "timestamp": "2026-08-16T12:00:00Z",
    }

    async with NotificationServer(transport=transport) as server:
        await transport.on_connect(object())
        await server.broadcast(notification)

        assert server.connected_count == 1
        assert transport.broadcasts == [(notification, ["custom-client"])]


def test_websocket_transport_is_selected_from_config(monkeypatch):
    monkeypatch.setenv("TRANSPORT", "websocket")
    server = NotificationServer()
    try:
        assert isinstance(server.transport, WebSocketTransport)
    finally:
        server.messages.close()


def test_registered_transport_can_be_selected_from_config(monkeypatch):
    monkeypatch.setitem(TRANSPORTS, "recording", RecordingTransport)
    monkeypatch.setenv("TRANSPORT", "recording")
    server = NotificationServer(host="localhost", port=1234)
    try:
        assert isinstance(server.transport, RecordingTransport)
        assert server.transport.host == "localhost"
        assert server.transport.port == 1234
    finally:
        server.messages.close()
