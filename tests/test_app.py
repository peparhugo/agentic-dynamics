import asyncio
import json
import urllib.request

import pytest
from websockets.asyncio.client import connect

from app import NotificationServer


@pytest.fixture
async def running_server(tmp_path):
    notification_server = NotificationServer(tmp_path)
    async with notification_server.run(port=0) as websocket_server:
        port = websocket_server.sockets[0].getsockname()[1]
        yield notification_server, port, tmp_path


async def receive_json(websocket):
    return json.loads(await asyncio.wait_for(websocket.recv(), timeout=1))


async def test_connect_assigns_unique_ids_and_persists_state(running_server):
    server, port, data_dir = running_server
    async with connect(f"ws://127.0.0.1:{port}") as first, connect(
        f"ws://127.0.0.1:{port}"
    ) as second:
        first_message = await receive_json(first)
        second_message = await receive_json(second)

        assert first_message["type"] == "system"
        assert first_message["payload"]["event"] == "connected"
        assert first_message["payload"]["client_id"] != second_message["payload"]["client_id"]
        assert await server.connected_count() == 2
        persisted = json.loads((data_dir / "clients.json").read_text())
        assert sorted(persisted["clients"]) == sorted(
            [first_message["payload"]["client_id"], second_message["payload"]["client_id"]]
        )


async def test_broadcast_reaches_every_connected_client(running_server):
    _, port, data_dir = running_server
    async with connect(f"ws://127.0.0.1:{port}") as first, connect(
        f"ws://127.0.0.1:{port}"
    ) as second:
        await receive_json(first)
        await receive_json(second)
        await first.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))

        first_received = await receive_json(first)
        second_received = await receive_json(second)
        assert first_received == second_received
        assert first_received["type"] == "broadcast"
        assert first_received["payload"] == {"text": "hello"}
        assert isinstance(first_received["timestamp"], str)

    history = [json.loads(line) for line in (data_dir / "messages.jsonl").read_text().splitlines()]
    assert any(message["type"] == "broadcast" for message in history)


async def test_direct_message_only_reaches_target(running_server):
    _, port, _ = running_server
    async with connect(f"ws://127.0.0.1:{port}") as sender, connect(
        f"ws://127.0.0.1:{port}"
    ) as recipient:
        await receive_json(sender)
        recipient_id = (await receive_json(recipient))["payload"]["client_id"]
        await sender.send(
            json.dumps(
                {"type": "direct", "payload": {"client_id": recipient_id, "text": "private"}}
            )
        )

        message = await receive_json(recipient)
        assert message["type"] == "direct"
        assert message["payload"]["text"] == "private"
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sender.recv(), timeout=0.05)


async def test_invalid_messages_return_system_errors(running_server):
    _, port, _ = running_server
    async with connect(f"ws://127.0.0.1:{port}") as websocket:
        await receive_json(websocket)
        await websocket.send("not-json")
        response = await receive_json(websocket)
        assert response["type"] == "system"
        assert response["payload"] == {"error": "invalid JSON"}


async def test_disconnect_removes_and_persists_client(running_server):
    server, port, data_dir = running_server
    websocket = await connect(f"ws://127.0.0.1:{port}")
    await receive_json(websocket)
    await websocket.close()

    for _ in range(20):
        if await server.connected_count() == 0:
            break
        await asyncio.sleep(0.01)
    assert await server.connected_count() == 0
    assert json.loads((data_dir / "clients.json").read_text()) == {"clients": []}


async def test_health_reports_connected_count(running_server):
    _, port, _ = running_server
    async with connect(f"ws://127.0.0.1:{port}") as websocket:
        await receive_json(websocket)

        def request_health():
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health") as response:
                return response.status, json.load(response)

        status, body = await asyncio.to_thread(request_health)
        assert status == 200
        assert body == {"connected_clients": 1}
