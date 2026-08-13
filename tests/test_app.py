import asyncio
import json
import threading

import pytest
from websockets.asyncio.client import connect

from app import NotificationServer, app, clients, clients_lock


@pytest.fixture
def server():
    instance = NotificationServer(port=0)
    instance.start()
    yield instance
    instance.stop()
    with clients_lock:
        clients.clear()


def url(server):
    return f"ws://127.0.0.1:{server.port}"


async def receive_json(websocket):
    return json.loads(await asyncio.wait_for(websocket.recv(), timeout=2))


async def connect_client(server):
    websocket = await connect(url(server))
    welcome = await receive_json(websocket)
    assert welcome["type"] == "system"
    assert welcome["payload"]["event"] == "connected"
    assert isinstance(welcome["timestamp"], str)
    return websocket, welcome["payload"]["client_id"]


@pytest.mark.asyncio
async def test_assigns_unique_ids_and_cleans_up_disconnects(server):
    first, first_id = await connect_client(server)
    second, second_id = await connect_client(server)
    assert first_id != second_id
    assert len(clients) == 2

    await first.close()
    await second.close()
    for _ in range(50):
        if not clients:
            break
        await asyncio.sleep(0.01)
    assert clients == {}


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients(server):
    first, _ = await connect_client(server)
    second, _ = await connect_client(server)
    message = {
        "type": "broadcast",
        "payload": {"text": "deployment complete"},
        "timestamp": "2026-08-13T12:00:00+00:00",
    }
    await first.send(json.dumps(message))

    assert await receive_json(first) == message
    assert await receive_json(second) == message
    await first.close()
    await second.close()


@pytest.mark.asyncio
async def test_direct_message_only_reaches_recipient(server):
    sender, _ = await connect_client(server)
    recipient, recipient_id = await connect_client(server)
    message = {
        "type": "direct",
        "payload": {"client_id": recipient_id, "text": "private"},
        "timestamp": "2026-08-13T12:00:00+00:00",
    }
    await sender.send(json.dumps(message))

    assert await receive_json(recipient) == message
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(sender.recv(), timeout=0.05)
    await sender.close()
    await recipient.close()


@pytest.mark.asyncio
async def test_invalid_messages_return_system_error(server):
    websocket, _ = await connect_client(server)
    await websocket.send("not json")
    response = await receive_json(websocket)
    assert response["type"] == "system"
    assert response["payload"] == {"error": "invalid JSON"}
    assert set(response) == {"type", "payload", "timestamp"}
    await websocket.close()


@pytest.mark.asyncio
async def test_health_reports_connected_count(server):
    websocket, _ = await connect_client(server)
    response = app.test_client().get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"connected_clients": 1}
    await websocket.close()


def test_websocket_loop_uses_daemon_thread(server):
    assert server._thread is not threading.main_thread()
    assert server._thread.daemon is True
    assert server._thread.is_alive()
