import json

import pytest

from app import NotificationServer, app


class FakeWebSocket:
    def __init__(self):
        self.sent = []

    async def send_text(self, message):
        self.sent.append(json.loads(message))


@pytest.mark.asyncio
async def test_broadcast_sends_to_every_registered_client():
    server = NotificationServer()
    first = FakeWebSocket()
    second = FakeWebSocket()
    server.register(first)
    server.register(second)

    await server.broadcast({"message": "hello"})

    assert first.sent[0]["type"] == "broadcast"
    assert first.sent[0]["payload"] == {"message": "hello"}
    assert second.sent[0]["payload"] == {"message": "hello"}
    assert "timestamp" in first.sent[0]


@pytest.mark.asyncio
async def test_direct_message_targets_one_client():
    server = NotificationServer()
    target = FakeWebSocket()
    other = FakeWebSocket()
    target_id = server.register(target)
    server.register(other)

    assert await server.send_direct(target_id, {"message": "private"})
    assert target.sent[0]["payload"] == {"message": "private"}
    assert other.sent == []


def test_health_reports_connected_client_count():
    client = app.test_client()
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"connected_clients": 0}
