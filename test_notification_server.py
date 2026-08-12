import json

import pytest

from app import NotificationServer, app, notification_server


class FakeWebSocket:
    def __init__(self):
        self.sent = []

    async def send_text(self, message):
        self.sent.append(json.loads(message))


class IncomingWebSocket(FakeWebSocket):
    def __init__(self, messages):
        super().__init__()
        self.messages = iter(messages)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.messages)
        except StopIteration:
            raise StopAsyncIteration


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


@pytest.mark.asyncio
async def test_channel_broadcast_only_reaches_subscribers():
    server = NotificationServer()
    alerts = FakeWebSocket()
    system = FakeWebSocket()
    alerts_id = server.register(alerts)
    server.register(system)
    server.subscribe(alerts_id, "alerts")

    await server.broadcast({"channel": "alerts", "message": "warning"})

    assert [message["payload"]["message"] for message in alerts.sent] == ["warning"]
    assert system.sent == []


@pytest.mark.asyncio
async def test_websocket_subscribe_and_unsubscribe_are_dynamic():
    server = NotificationServer()
    websocket = IncomingWebSocket([
        json.dumps({"type": "subscribe", "payload": {"channel": "chat"}}),
        json.dumps({"type": "unsubscribe", "channel": "chat"}),
    ])

    await server.websocket_handler(websocket)

    assert server.channel_counts() == {}


def test_channel_rest_endpoints_report_active_subscribers():
    server = notification_server
    client = app.test_client()
    websocket = FakeWebSocket()
    client_id = server.register(websocket)
    server.subscribe(client_id, "alerts")
    try:
        response = client.get("/channels")
        assert response.status_code == 200
        assert response.get_json() == {"channels": {"alerts": 1}}

        response = client.get("/channels/alerts/subscribers")
        assert response.status_code == 200
        assert response.get_json() == {
            "channel": "alerts",
            "subscribers": [client_id],
        }
    finally:
        server.unregister(client_id)


def test_health_reports_connected_client_count():
    client = app.test_client()
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"connected_clients": 0}
