import asyncio
import json
import threading

import pytest
from websockets.asyncio.client import connect

from server import NotificationServer, ClientRegistry


async def async_http_get(host, port, path):
    reader, writer = await asyncio.open_connection(host, port)
    request = f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
    writer.write(request.encode())
    await writer.drain()

    raw = b""
    while True:
        chunk = await asyncio.wait_for(reader.read(4096), timeout=5)
        if not chunk:
            break
        raw += chunk

    writer.close()
    await writer.wait_closed()

    parts = raw.split(b"\r\n\r\n", 1)
    body = parts[1] if len(parts) > 1 else b""
    return json.loads(body.decode())


@pytest.fixture
async def notification_server():
    server = NotificationServer(host="localhost", port=0)
    async with server.run() as ws_server:
        server.port = ws_server.sockets[0].getsockname()[1]
        yield server


class TestClientRegistry:
    def test_add_and_count(self):
        reg = ClientRegistry()
        assert reg.count() == 0
        reg.add("id1", object())
        assert reg.count() == 1
        reg.add("id2", object())
        assert reg.count() == 2

    def test_remove(self):
        reg = ClientRegistry()
        dummy = object()
        reg.add("id1", dummy)
        assert reg.count() == 1
        reg.remove("id1")
        assert reg.count() == 0
        reg.remove("nonexistent")

    def test_get_all_returns_copy(self):
        reg = ClientRegistry()
        dummy = object()
        reg.add("id1", dummy)
        clients = reg.get_all()
        clients["extra"] = "bad"
        assert "extra" not in reg.get_all()

    def test_clear(self):
        reg = ClientRegistry()
        reg.add("a", object())
        reg.add("b", object())
        reg.clear()
        assert reg.count() == 0

    def test_thread_safety(self):
        reg = ClientRegistry()
        errors = []

        def adder(start):
            try:
                for i in range(start, start + 500):
                    reg.add(str(i), object())
            except Exception as e:
                errors.append(e)

        def remover(start):
            try:
                for i in range(start, start + 500):
                    reg.remove(str(i))
            except Exception as e:
                errors.append(e)

        threads = []
        for j in range(5):
            t1 = threading.Thread(target=adder, args=(j * 1000,))
            t2 = threading.Thread(target=remover, args=(j * 1000,))
            threads.extend([t1, t2])

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        reg.clear()


@pytest.mark.asyncio
async def test_client_connects_and_receives_welcome(notification_server):
    uri = f"ws://localhost:{notification_server.port}"
    async with connect(uri) as ws:
        msg = await asyncio.wait_for(ws.recv(), timeout=5)
        data = json.loads(msg)
        assert data["type"] == "system"
        assert "client_id" in data["payload"]
        assert len(data["payload"]["client_id"]) > 0


@pytest.mark.asyncio
async def test_each_client_gets_unique_id(notification_server):
    uri = f"ws://localhost:{notification_server.port}"
    async with connect(uri) as ws1, connect(uri) as ws2:
        data1 = json.loads(await asyncio.wait_for(ws1.recv(), timeout=5))
        data2 = json.loads(await asyncio.wait_for(ws2.recv(), timeout=5))
        assert data1["payload"]["client_id"] != data2["payload"]["client_id"]


@pytest.mark.asyncio
async def test_health_returns_client_count(notification_server):
    port = notification_server.port

    data = await async_http_get("localhost", port, "/health")
    assert data["clients"] == 0

    uri = f"ws://localhost:{port}"
    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        await asyncio.sleep(0.05)
        data = await async_http_get("localhost", port, "/health")
        assert data["clients"] == 1


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients(notification_server):
    uri = f"ws://localhost:{notification_server.port}"

    async with connect(uri) as client1, connect(uri) as client2:
        await asyncio.wait_for(client1.recv(), timeout=5)
        await asyncio.wait_for(client2.recv(), timeout=5)

        await client1.send(json.dumps({
            "type": "broadcast",
            "payload": {"message": "hello"}
        }))

        msg1 = await asyncio.wait_for(client1.recv(), timeout=5)
        msg2 = await asyncio.wait_for(client2.recv(), timeout=5)

        d1 = json.loads(msg1)
        d2 = json.loads(msg2)

        assert d1["type"] == "broadcast"
        assert d1["payload"]["message"] == "hello"
        assert d2["type"] == "broadcast"
        assert d2["payload"]["message"] == "hello"


@pytest.mark.asyncio
async def test_direct_message(notification_server):
    uri = f"ws://localhost:{notification_server.port}"

    async with connect(uri) as client1:
        welcome1 = await asyncio.wait_for(client1.recv(), timeout=5)
        client1_id = json.loads(welcome1)["payload"]["client_id"]

        async with connect(uri) as client2:
            welcome2 = await asyncio.wait_for(client2.recv(), timeout=5)
            client2_id = json.loads(welcome2)["payload"]["client_id"]

            await client1.send(json.dumps({
                "type": "direct",
                "target": client2_id,
                "payload": {"message": "private"}
            }))

            direct_msg = await asyncio.wait_for(client2.recv(), timeout=5)
            data = json.loads(direct_msg)
            assert data["type"] == "direct"
            assert data["payload"]["message"] == "private"
            assert data["sender"] == client1_id


@pytest.mark.asyncio
async def test_direct_message_to_nonexistent(notification_server):
    uri = f"ws://localhost:{notification_server.port}"
    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        await ws.send(json.dumps({
            "type": "direct",
            "target": "nonexistent-id",
            "payload": {"message": "nobody"}
        }))


@pytest.mark.asyncio
async def test_client_disconnect_removed_from_registry(notification_server):
    port = notification_server.port
    uri = f"ws://localhost:{port}"

    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        data = await async_http_get("localhost", port, "/health")
        assert data["clients"] == 1

    await asyncio.sleep(0.1)
    data = await async_http_get("localhost", port, "/health")
    assert data["clients"] == 0


@pytest.mark.asyncio
async def test_broadcast_skips_disconnected_clients(notification_server):
    uri = f"ws://localhost:{notification_server.port}"

    async with connect(uri) as client1:
        await asyncio.wait_for(client1.recv(), timeout=5)

        async with connect(uri) as client2:
            await asyncio.wait_for(client2.recv(), timeout=5)
            await client2.close()

            await asyncio.sleep(0.05)

            await client1.send(json.dumps({
                "type": "broadcast",
                "payload": {"message": "still alive"}
            }))

            msg = await asyncio.wait_for(client1.recv(), timeout=5)
            data = json.loads(msg)
            assert data["payload"]["message"] == "still alive"


@pytest.mark.asyncio
async def test_ignore_invalid_json(notification_server):
    uri = f"ws://localhost:{notification_server.port}"
    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        await ws.send("not valid json{{{{")
        await ws.send(json.dumps({
            "type": "broadcast",
            "payload": {"message": "after bad json"}
        }))
        msg = await asyncio.wait_for(ws.recv(), timeout=5)
        data = json.loads(msg)
        assert data["payload"]["message"] == "after bad json"


@pytest.mark.asyncio
async def test_message_format_fields(notification_server):
    uri = f"ws://localhost:{notification_server.port}"

    async with connect(uri) as ws:
        welcome = await asyncio.wait_for(ws.recv(), timeout=5)
        welcome_data = json.loads(welcome)

        assert "type" in welcome_data
        assert "payload" in welcome_data
        assert "timestamp" in welcome_data
        assert welcome_data["type"] == "system"

        await ws.send(json.dumps({
            "type": "broadcast",
            "payload": {"k": "v"}
        }))

        msg = await asyncio.wait_for(ws.recv(), timeout=5)
        data = json.loads(msg)
        assert data["type"] == "broadcast"
        assert data["payload"] == {"k": "v"}
        assert "timestamp" in data


@pytest.mark.asyncio
async def test_multiple_clients_connect_and_disconnect(notification_server):
    port = notification_server.port
    uri = f"ws://localhost:{port}"

    async with connect(uri) as ws1, connect(uri) as ws2, connect(uri) as ws3:
        await asyncio.wait_for(ws1.recv(), timeout=5)
        await asyncio.wait_for(ws2.recv(), timeout=5)
        await asyncio.wait_for(ws3.recv(), timeout=5)

        await asyncio.sleep(0.05)
        data = await async_http_get("localhost", port, "/health")
        assert data["clients"] == 3

    await asyncio.sleep(0.15)
    data = await async_http_get("localhost", port, "/health")
    assert data["clients"] == 0
