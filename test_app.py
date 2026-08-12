import asyncio
import json
import socket

import pytest
import pytest_asyncio
from websockets.asyncio.client import connect as ws_connect

from app import registry, start_server


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest_asyncio.fixture
async def server():
    ws_port = _find_free_port()
    http_port = _find_free_port()
    ws_server, http_server = await start_server(
        ws_host="127.0.0.1", ws_port=ws_port,
        http_host="127.0.0.1", http_port=http_port,
    )
    yield {"ws_port": ws_port, "http_port": http_port}
    ws_server.close()
    http_server.close()
    await ws_server.wait_closed()
    http_server.close()
    await http_server.wait_closed()


async def _ws_url(server, path: str = "") -> str:
    return f"ws://127.0.0.1:{server['ws_port']}{path}"


async def _http_get(server, path: str) -> dict:
    port = server["http_port"]
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        request = f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n"
        writer.write(request.encode())
        await writer.drain()
        raw = await asyncio.wait_for(reader.read(), timeout=5)
        parts = raw.decode().split("\r\n\r\n", 1)
        body = parts[1] if len(parts) > 1 else ""
        return json.loads(body)
    finally:
        writer.close()


async def _recv_json(ws) -> dict:
    raw = await asyncio.wait_for(ws.recv(), timeout=5)
    return json.loads(raw)


async def _drain_welcome_and_joins(wss: list) -> list[dict]:
    """Drain all welcome + join messages. Returns welcome messages in order."""
    n = len(wss)
    welcomes = []
    for i, ws in enumerate(wss):
        msgs_to_drain = n - i
        for j in range(msgs_to_drain):
            msg = await _recv_json(ws)
            if j == 0:
                welcomes.append(msg)
    return welcomes


@pytest.mark.asyncio
async def test_client_connects_and_receives_id(server):
    async with ws_connect(await _ws_url(server)) as ws:
        data = await _recv_json(ws)
        assert data["type"] == "system"
        assert "client_id" in data["payload"]
        assert data["payload"].get("connected") is True


@pytest.mark.asyncio
async def test_health_returns_zero_with_no_clients(server):
    result = await _http_get(server, "/health")
    assert result["connected_clients"] == 0


@pytest.mark.asyncio
async def test_health_returns_client_count(server):
    async with ws_connect(await _ws_url(server)):
        result = await _http_get(server, "/health")
        assert result["connected_clients"] == 1
    result = await _http_get(server, "/health")
    assert result["connected_clients"] == 0


@pytest.mark.asyncio
async def test_broadcast_to_all_clients(server):
    async with (
        ws_connect(await _ws_url(server)) as ws1,
        ws_connect(await _ws_url(server)) as ws2,
        ws_connect(await _ws_url(server)) as ws3,
    ):
        await _drain_welcome_and_joins([ws1, ws2, ws3])

        await ws1.send(json.dumps({"type": "broadcast", "payload": {"msg": "hello"}}))

        msg2 = await _recv_json(ws2)
        msg3 = await _recv_json(ws3)

        assert msg2["type"] == "broadcast"
        assert msg2["payload"] == {"msg": "hello"}
        assert "timestamp" in msg2

        assert msg3["type"] == "broadcast"
        assert msg3["payload"] == {"msg": "hello"}
        assert "timestamp" in msg3


@pytest.mark.asyncio
async def test_direct_message(server):
    async with (
        ws_connect(await _ws_url(server)) as ws1,
        ws_connect(await _ws_url(server)) as ws2,
        ws_connect(await _ws_url(server)) as ws3,
    ):
        welcomes = await _drain_welcome_and_joins([ws1, ws2, ws3])
        target = welcomes[0]["payload"]["client_id"]

        await ws2.send(json.dumps({
            "type": "direct",
            "target": target,
            "payload": {"private": True},
        }))

        msg = await _recv_json(ws1)
        assert msg["type"] == "direct"
        assert msg["payload"] == {"private": True}


@pytest.mark.asyncio
async def test_direct_message_to_nonexistent_client(server):
    async with ws_connect(await _ws_url(server)) as ws1:
        await _recv_json(ws1)
        await ws1.send(json.dumps({
            "type": "direct",
            "target": "nonexistent-id",
            "payload": {"hello": "world"},
        }))
        await asyncio.sleep(0.1)
        async with ws_connect(await _ws_url(server)) as ws2:
            await _recv_json(ws2)
            await ws2.send(json.dumps({"type": "broadcast", "payload": {"test": 1}}))
            await _recv_json(ws1)
            assert True


@pytest.mark.asyncio
async def test_disconnect_removes_client(server):
    async with ws_connect(await _ws_url(server)) as ws:
        await _recv_json(ws)
        count = (await _http_get(server, "/health"))["connected_clients"]
        assert count == 1
    count = (await _http_get(server, "/health"))["connected_clients"]
    assert count == 0


@pytest.mark.asyncio
async def test_multiple_disconnects_no_crash(server):
    ws1 = await ws_connect(await _ws_url(server))
    ws2 = await ws_connect(await _ws_url(server))
    await _recv_json(ws1)
    await _recv_json(ws2)
    await ws1.close()
    await ws2.close()
    count = (await _http_get(server, "/health"))["connected_clients"]
    assert count == 0


@pytest.mark.asyncio
async def test_system_message_type(server):
    async with (
        ws_connect(await _ws_url(server)) as ws1,
        ws_connect(await _ws_url(server)) as ws2,
    ):
        await _drain_welcome_and_joins([ws1, ws2])

        await ws1.send(json.dumps({"type": "system", "payload": {"action": "shutdown"}}))

        msg = await _recv_json(ws2)
        assert msg["type"] == "system"
        assert msg["payload"] == {"action": "shutdown"}
        assert "timestamp" in msg


@pytest.mark.asyncio
async def test_message_has_timestamp(server):
    async with (
        ws_connect(await _ws_url(server)) as ws1,
        ws_connect(await _ws_url(server)) as ws2,
    ):
        await _drain_welcome_and_joins([ws1, ws2])

        await ws1.send(json.dumps({"type": "broadcast", "payload": {"x": 1}}))
        msg = await _recv_json(ws2)

        assert "timestamp" in msg
        assert isinstance(msg["timestamp"], str)
        assert msg["type"] == "broadcast"
        assert msg["payload"] == {"x": 1}


@pytest.mark.asyncio
async def test_invalid_json_does_not_crash(server):
    async with (
        ws_connect(await _ws_url(server)) as ws1,
        ws_connect(await _ws_url(server)) as ws2,
    ):
        await _drain_welcome_and_joins([ws1, ws2])

        await ws1.send("not valid json {{{")
        await asyncio.sleep(0.1)

        await ws1.send(json.dumps({"type": "broadcast", "payload": {"ok": 1}}))
        msg = await _recv_json(ws2)
        assert msg["payload"] == {"ok": 1}


@pytest.mark.asyncio
async def test_broadcaster_does_not_receive_own_message(server):
    async with (
        ws_connect(await _ws_url(server)) as ws1,
        ws_connect(await _ws_url(server)) as ws2,
    ):
        await _drain_welcome_and_joins([ws1, ws2])

        await ws1.send(json.dumps({"type": "broadcast", "payload": {"n": 1}}))

        msg = await _recv_json(ws2)
        assert msg["payload"] == {"n": 1}

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws1.recv(), timeout=0.5)


@pytest.mark.asyncio
async def test_health_nonexistent_path_returns_404(server):
    port = server["http_port"]
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        request = f"GET /nonexistent HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n"
        writer.write(request.encode())
        await writer.drain()
        raw = await asyncio.wait_for(reader.read(), timeout=5)
        parts = raw.decode().split("\r\n\r\n", 1)
        body = parts[1] if len(parts) > 1 else ""
        data = json.loads(body)
        assert "error" in data
    finally:
        writer.close()


@pytest.mark.asyncio
async def test_unique_client_ids(server):
    async with (
        ws_connect(await _ws_url(server)) as ws1,
        ws_connect(await _ws_url(server)) as ws2,
    ):
        w1 = await _recv_json(ws1)
        w2 = await _recv_json(ws2)
        assert w1["payload"]["client_id"] != w2["payload"]["client_id"]


@pytest.mark.asyncio
async def test_empty_payload_defaults_to_empty_dict(server):
    async with (
        ws_connect(await _ws_url(server)) as ws1,
        ws_connect(await _ws_url(server)) as ws2,
    ):
        await _drain_welcome_and_joins([ws1, ws2])

        await ws1.send(json.dumps({"type": "broadcast"}))
        msg = await _recv_json(ws2)
        assert msg["payload"] == {}
        assert "timestamp" in msg


@pytest.mark.asyncio
async def test_connect_and_disconnect_notifications(server):
    async with ws_connect(await _ws_url(server)) as ws1:
        w1 = await _recv_json(ws1)

        async with ws_connect(await _ws_url(server)) as ws2:
            w2 = await _recv_json(ws2)

            join_notif = await _recv_json(ws1)
            assert join_notif["type"] == "system"
            assert join_notif["payload"].get("client_id") == w2["payload"]["client_id"]
            assert join_notif["payload"].get("event") == "connected"

        disconnect_notif = await _recv_json(ws1)
        assert disconnect_notif["type"] == "system"
        assert disconnect_notif["payload"].get("client_id") == w2["payload"]["client_id"]
        assert disconnect_notif["payload"].get("event") == "disconnected"


@pytest.mark.asyncio
async def test_disconnected_client_broadcast_clean(server):
    async with ws_connect(await _ws_url(server)) as ws1:
        await _recv_json(ws1)

        async with ws_connect(await _ws_url(server)) as ws2:
            await _recv_json(ws2)

        await asyncio.sleep(0.1)

        await ws1.send(json.dumps({"type": "broadcast", "payload": {"after": "disconnect"}}))


@pytest.mark.asyncio
async def test_concurrent_broadcasts(server):
    async with (
        ws_connect(await _ws_url(server)) as ws1,
        ws_connect(await _ws_url(server)) as ws2,
        ws_connect(await _ws_url(server)) as ws3,
    ):
        await _drain_welcome_and_joins([ws1, ws2, ws3])

        await asyncio.gather(
            ws1.send(json.dumps({"type": "broadcast", "payload": {"from": "ws1"}})),
            ws2.send(json.dumps({"type": "broadcast", "payload": {"from": "ws2"}})),
        )

        msgs = []
        for _ in range(2):
            msgs.append(await _recv_json(ws3))

        payloads = [m["payload"] for m in msgs]
        assert {"from": "ws1"} in payloads
        assert {"from": "ws2"} in payloads
        for m in msgs:
            assert "timestamp" in m
