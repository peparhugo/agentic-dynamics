import asyncio
import json

import pytest
import pytest_asyncio
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from server import registry, start

WS_HOST = "127.0.0.1"
HTTP_HOST = "127.0.0.1"


@pytest_asyncio.fixture
async def server():
    ws_server, http_server = await start(WS_HOST, 0, HTTP_HOST, 0)
    ws_port = ws_server.sockets[0].getsockname()[1]
    http_port = http_server.sockets[0].getsockname()[1]
    yield ws_port, http_port
    ws_server.close()
    await ws_server.wait_closed()
    http_server.close()
    await http_server.wait_closed()
    registry.clear()


@pytest.mark.asyncio
async def test_connect_and_welcome(server):
    ws_port, _ = server
    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws:
        raw = await asyncio.wait_for(ws.recv(), timeout=2)
        msg = json.loads(raw)
        assert msg["type"] == "system"
        assert "client_id" in msg["payload"]
        assert "timestamp" in msg


@pytest.mark.asyncio
async def test_health_no_clients(server):
    _, http_port = server
    reader, writer = await asyncio.open_connection(HTTP_HOST, http_port)
    request = f"GET /health HTTP/1.1\r\nHost: {HTTP_HOST}:{http_port}\r\n\r\n"
    writer.write(request.encode())
    await writer.drain()
    raw = await asyncio.wait_for(reader.read(), timeout=2)
    writer.close()
    await writer.wait_closed()

    body = raw.split(b"\r\n\r\n", 1)[1]
    data = json.loads(body.decode())
    assert data["clients_connected"] == 0


@pytest.mark.asyncio
async def test_health_with_clients(server):
    ws_port, http_port = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws1:
        await ws1.recv()
        async with connect(f"ws://{WS_HOST}:{ws_port}") as ws2:
            await ws2.recv()

            reader, writer = await asyncio.open_connection(HTTP_HOST, http_port)
            request = f"GET /health HTTP/1.1\r\nHost: {HTTP_HOST}:{http_port}\r\n\r\n"
            writer.write(request.encode())
            await writer.drain()
            raw = await asyncio.wait_for(reader.read(), timeout=2)
            writer.close()
            await writer.wait_closed()

            body = raw.split(b"\r\n\r\n", 1)[1]
            data = json.loads(body.decode())
            assert data["clients_connected"] == 2


@pytest.mark.asyncio
async def test_broadcast(server):
    ws_port, _ = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws1, \
            connect(f"ws://{WS_HOST}:{ws_port}") as ws2:

        welcome1 = json.loads(await ws1.recv())
        welcome2 = json.loads(await ws2.recv())
        assert welcome1["type"] == "system"
        assert welcome2["type"] == "system"

        payload = {"message": "hello everyone"}
        await ws1.send(json.dumps({"type": "broadcast", "payload": payload}))

        msg1 = json.loads(await asyncio.wait_for(ws1.recv(), timeout=2))
        msg2 = json.loads(await asyncio.wait_for(ws2.recv(), timeout=2))

        assert msg1["type"] == "broadcast"
        assert msg1["payload"] == payload
        assert "timestamp" in msg1

        assert msg2["type"] == "broadcast"
        assert msg2["payload"] == payload
        assert "timestamp" in msg2


@pytest.mark.asyncio
async def test_direct_message(server):
    ws_port, _ = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws1, \
            connect(f"ws://{WS_HOST}:{ws_port}") as ws2:

        welcome1 = json.loads(await ws1.recv())
        welcome2 = json.loads(await ws2.recv())
        client2_id = welcome2["payload"]["client_id"]

        payload = {"target": client2_id, "message": "secret"}
        await ws1.send(json.dumps({"type": "direct", "payload": payload}))

        msg = json.loads(await asyncio.wait_for(ws2.recv(), timeout=2))
        assert msg["type"] == "direct"
        assert msg["payload"]["message"] == "secret"
        assert msg["payload"]["target"] == client2_id

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws1.recv(), timeout=0.3)


@pytest.mark.asyncio
async def test_direct_to_nonexistent(server):
    ws_port, _ = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws:
        welcome = json.loads(await ws.recv())

        payload = {"target": "nonexistent-id", "message": "ghost"}
        await ws.send(json.dumps({"type": "direct", "payload": payload}))

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws.recv(), timeout=0.3)


@pytest.mark.asyncio
async def test_disconnect_removes_client(server):
    ws_port, http_port = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws1:
        await ws1.recv()
        async with connect(f"ws://{WS_HOST}:{ws_port}") as ws2:
            await ws2.recv()
            async with connect(f"ws://{WS_HOST}:{ws_port}") as ws3:
                await ws3.recv()

            await asyncio.sleep(0.1)

            reader, writer = await asyncio.open_connection(HTTP_HOST, http_port)
            request = f"GET /health HTTP/1.1\r\nHost: {HTTP_HOST}:{http_port}\r\n\r\n"
            writer.write(request.encode())
            await writer.drain()
            raw = await asyncio.wait_for(reader.read(), timeout=2)
            writer.close()
            await writer.wait_closed()

            body = raw.split(b"\r\n\r\n", 1)[1]
            data = json.loads(body.decode())
            assert data["clients_connected"] == 2


@pytest.mark.asyncio
async def test_disconnected_client_not_broadcasted(server):
    ws_port, _ = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws1, \
            connect(f"ws://{WS_HOST}:{ws_port}") as ws2, \
            connect(f"ws://{WS_HOST}:{ws_port}") as ws3:

        await ws1.recv()
        await ws2.recv()
        await ws3.recv()

        await ws2.close()

        await ws1.send(json.dumps({"type": "broadcast", "payload": {"test": 1}}))
        await asyncio.wait_for(ws1.recv(), timeout=2)
        await asyncio.wait_for(ws3.recv(), timeout=2)

        with pytest.raises(ConnectionClosed):
            await asyncio.wait_for(ws2.recv(), timeout=0.3)


@pytest.mark.asyncio
async def test_invalid_json_ignored(server):
    ws_port, _ = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws1, \
            connect(f"ws://{WS_HOST}:{ws_port}") as ws2:

        await ws1.recv()
        await ws2.recv()

        await ws1.send("not json at all")
        await ws1.send(json.dumps({"type": "broadcast", "payload": {"msg": "after bad"}}))

        msg1 = json.loads(await asyncio.wait_for(ws1.recv(), timeout=2))
        assert msg1["payload"] == {"msg": "after bad"}

        msg2 = json.loads(await asyncio.wait_for(ws2.recv(), timeout=2))
        assert msg2["payload"] == {"msg": "after bad"}


@pytest.mark.asyncio
async def test_unknown_message_type_ignored(server):
    ws_port, _ = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "unknown_type", "payload": {}}))

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws.recv(), timeout=0.3)


@pytest.mark.asyncio
async def test_multiple_broadcasts(server):
    ws_port, _ = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws1, \
            connect(f"ws://{WS_HOST}:{ws_port}") as ws2:

        await ws1.recv()
        await ws2.recv()

        for i in range(3):
            await ws1.send(json.dumps({"type": "broadcast", "payload": {"seq": i}}))
            m1 = json.loads(await asyncio.wait_for(ws1.recv(), timeout=2))
            m2 = json.loads(await asyncio.wait_for(ws2.recv(), timeout=2))
            assert m1["payload"]["seq"] == i
            assert m2["payload"]["seq"] == i


@pytest.mark.asyncio
async def test_broadcast_with_empty_payload(server):
    ws_port, _ = server

    async with connect(f"ws://{WS_HOST}:{ws_port}") as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "broadcast", "payload": {}}))
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
        assert msg["type"] == "broadcast"
        assert msg["payload"] == {}
