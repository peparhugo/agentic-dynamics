import asyncio
import json
import urllib.request

import pytest
import pytest_asyncio
import websockets

from notification_server.server import NotificationServer


@pytest_asyncio.fixture
async def server():
    srv = NotificationServer(host="localhost", port=0)
    await srv.start()
    yield srv
    srv.stop()
    await srv.wait_closed()


def ws_uri(srv: NotificationServer) -> str:
    return f"ws://localhost:{srv.bound_port}"


def health_url(srv: NotificationServer) -> str:
    return f"http://localhost:{srv.bound_port}/health"


async def get_health(srv: NotificationServer) -> dict:
    def _fetch():
        with urllib.request.urlopen(health_url(srv)) as resp:
            return resp.status, json.loads(resp.read())

    return await asyncio.to_thread(_fetch)


async def recv_json(websocket) -> dict:
    return json.loads(await websocket.recv())


async def wait_until(predicate, timeout: float = 2.0, interval: float = 0.02) -> None:
    async def _loop():
        while not predicate():
            await asyncio.sleep(interval)

    await asyncio.wait_for(_loop(), timeout=timeout)


# -- connection lifecycle -------------------------------------------------


@pytest.mark.asyncio
async def test_client_receives_unique_id_on_connect(server):
    async with websockets.connect(ws_uri(server)) as ws1, websockets.connect(ws_uri(server)) as ws2:
        welcome1 = await recv_json(ws1)
        welcome2 = await recv_json(ws2)

        assert welcome1["type"] == "system"
        assert welcome2["type"] == "system"
        id1 = welcome1["payload"]["client_id"]
        id2 = welcome2["payload"]["client_id"]

        assert id1 != id2
        assert server.registry.count() == 2


@pytest.mark.asyncio
async def test_disconnect_removes_client_from_registry(server):
    async with websockets.connect(ws_uri(server)) as ws:
        await recv_json(ws)
        assert server.registry.count() == 1

    await wait_until(lambda: server.registry.count() == 0)


# -- health endpoint --------------------------------------------------------


@pytest.mark.asyncio
async def test_health_endpoint_with_no_clients(server):
    status, body = await get_health(server)
    assert status == 200
    assert body == {"connected_clients": 0}


@pytest.mark.asyncio
async def test_health_endpoint_reflects_connected_clients(server):
    async with websockets.connect(ws_uri(server)) as ws1:
        await recv_json(ws1)
        async with websockets.connect(ws_uri(server)) as ws2:
            await recv_json(ws2)
            status, body = await get_health(server)
            assert status == 200
            assert body == {"connected_clients": 2}

    await wait_until(lambda: server.registry.count() == 0)
    status, body = await get_health(server)
    assert body == {"connected_clients": 0}


# -- broadcast ----------------------------------------------------------


@pytest.mark.asyncio
async def test_broadcast_reaches_all_connected_clients(server):
    async with websockets.connect(ws_uri(server)) as ws1, websockets.connect(ws_uri(server)) as ws2, \
            websockets.connect(ws_uri(server)) as ws3:
        for ws in (ws1, ws2, ws3):
            await recv_json(ws)

        await ws1.send(json.dumps({
            "type": "broadcast",
            "payload": {"text": "hello everyone"},
            "timestamp": "2024-01-01T00:00:00Z",
        }))

        for ws in (ws1, ws2, ws3):
            message = await recv_json(ws)
            assert message["type"] == "broadcast"
            assert message["payload"] == {"text": "hello everyone"}


# -- direct messages ------------------------------------------------------


@pytest.mark.asyncio
async def test_direct_message_delivered_only_to_target(server):
    async with websockets.connect(ws_uri(server)) as ws1, websockets.connect(ws_uri(server)) as ws2, \
            websockets.connect(ws_uri(server)) as ws3:
        welcome1 = await recv_json(ws1)
        welcome2 = await recv_json(ws2)
        await recv_json(ws3)

        target_id = welcome2["payload"]["client_id"]

        await ws1.send(json.dumps({
            "type": "direct",
            "payload": {"target_id": target_id, "text": "hi there"},
            "timestamp": "2024-01-01T00:00:00Z",
        }))

        message = await recv_json(ws2)
        assert message["type"] == "direct"
        assert message["payload"]["text"] == "hi there"
        assert message["sender_id"] == welcome1["payload"]["client_id"]

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws3.recv(), timeout=0.2)


@pytest.mark.asyncio
async def test_direct_message_to_unknown_target_returns_error(server):
    async with websockets.connect(ws_uri(server)) as ws:
        await recv_json(ws)
        await ws.send(json.dumps({
            "type": "direct",
            "payload": {"target_id": "does-not-exist", "text": "hi"},
            "timestamp": "2024-01-01T00:00:00Z",
        }))
        message = await recv_json(ws)
        assert message["type"] == "system"
        assert "error" in message["payload"]


# -- message validation -----------------------------------------------------


@pytest.mark.asyncio
async def test_system_message_from_client_is_rejected(server):
    async with websockets.connect(ws_uri(server)) as ws:
        await recv_json(ws)
        await ws.send(json.dumps({
            "type": "system",
            "payload": {"anything": "here"},
            "timestamp": "2024-01-01T00:00:00Z",
        }))
        message = await recv_json(ws)
        assert message["type"] == "system"
        assert "error" in message["payload"]


@pytest.mark.asyncio
async def test_unknown_message_type_returns_error(server):
    async with websockets.connect(ws_uri(server)) as ws:
        await recv_json(ws)
        await ws.send(json.dumps({
            "type": "bogus",
            "payload": {},
            "timestamp": "2024-01-01T00:00:00Z",
        }))
        message = await recv_json(ws)
        assert message["type"] == "system"
        assert "error" in message["payload"]


@pytest.mark.asyncio
async def test_invalid_json_returns_error(server):
    async with websockets.connect(ws_uri(server)) as ws:
        await recv_json(ws)
        await ws.send("not valid json")
        message = await recv_json(ws)
        assert message["type"] == "system"
        assert "error" in message["payload"]


@pytest.mark.asyncio
async def test_message_missing_required_fields_returns_error(server):
    async with websockets.connect(ws_uri(server)) as ws:
        await recv_json(ws)
        await ws.send(json.dumps({"type": "broadcast"}))
        message = await recv_json(ws)
        assert message["type"] == "system"
        assert "error" in message["payload"]


# -- message envelope ---------------------------------------------------------


@pytest.mark.asyncio
async def test_all_messages_have_required_envelope_fields(server):
    async with websockets.connect(ws_uri(server)) as ws:
        welcome = await recv_json(ws)
        assert set(["type", "payload", "timestamp"]).issubset(welcome.keys())
        assert welcome["type"] in {"broadcast", "direct", "system"}
