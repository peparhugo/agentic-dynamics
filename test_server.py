import json
import asyncio
import threading

import pytest
import pytest_asyncio
from websockets.asyncio.client import connect

from server import ClientRegistry, make_message, registry, main


@pytest.fixture(autouse=True)
def reset_registry():
    for cid in list(registry.get_all()):
        registry.remove(cid[0])


@pytest_asyncio.fixture
async def server():
    task = asyncio.create_task(main())
    await asyncio.sleep(0.2)
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await asyncio.sleep(0.1)


def http_get(url):
    import urllib.request
    resp = urllib.request.urlopen(url)
    return json.loads(resp.read())


@pytest.mark.asyncio
async def test_client_gets_unique_id(server):
    async with connect("ws://127.0.0.1:8765") as ws:
        msg = json.loads(await ws.recv())
        assert msg["type"] == "system"
        assert msg["payload"]["message"] == "connected"
        assert "client_id" in msg["payload"]
        assert isinstance(msg["payload"]["client_id"], str)
        assert len(msg["payload"]["client_id"]) > 0
        assert "timestamp" in msg


@pytest.mark.asyncio
async def test_multiple_clients_get_unique_ids(server):
    async with (
        connect("ws://127.0.0.1:8765") as ws1,
        connect("ws://127.0.0.1:8765") as ws2,
    ):
        msg1 = json.loads(await ws1.recv())
        msg2 = json.loads(await ws2.recv())
        assert msg1["payload"]["client_id"] != msg2["payload"]["client_id"]


@pytest.mark.asyncio
async def test_broadcast_to_all_clients(server):
    async with (
        connect("ws://127.0.0.1:8765") as ws1,
        connect("ws://127.0.0.1:8765") as ws2,
        connect("ws://127.0.0.1:8765") as ws3,
    ):
        await ws1.recv()
        await ws2.recv()
        await ws3.recv()

        await ws1.send(json.dumps({
            "type": "broadcast",
            "payload": {"text": "hello all"},
        }))

        for ws in (ws2, ws3):
            msg = json.loads(await ws.recv())
            assert msg["type"] == "broadcast"
            assert msg["payload"]["text"] == "hello all"
            assert "timestamp" in msg


@pytest.mark.asyncio
async def test_direct_message_type(server):
    async with (
        connect("ws://127.0.0.1:8765") as ws1,
        connect("ws://127.0.0.1:8765") as ws2,
    ):
        await ws1.recv()
        await ws2.recv()

        await ws1.send(json.dumps({
            "type": "direct",
            "payload": {"target": "someone", "text": "private"},
        }))

        msg = json.loads(await ws2.recv())
        assert msg["type"] == "direct"
        assert msg["payload"]["text"] == "private"


@pytest.mark.asyncio
async def test_client_disconnect_removes_from_registry(server):
    for _ in range(3):
        async with connect("ws://127.0.0.1:8765") as ws:
            await ws.recv()
            assert registry.count() >= 1

    await asyncio.sleep(0.2)
    assert registry.count() == 0


@pytest.mark.asyncio
async def test_health_returns_client_count(server):
    async with (
        connect("ws://127.0.0.1:8765") as ws1,
        connect("ws://127.0.0.1:8765") as ws2,
    ):
        await ws1.recv()
        await ws2.recv()

        data = await asyncio.to_thread(http_get, "http://127.0.0.1:8766/health")
        assert data["clients"] == 2


@pytest.mark.asyncio
async def test_health_returns_zero_with_no_clients(server):
    data = await asyncio.to_thread(http_get, "http://127.0.0.1:8766/health")
    assert data["clients"] == 0


class TestClientRegistry:
    def test_add_client(self):
        reg = ClientRegistry()
        cid = reg.add("fake_ws_1")
        assert isinstance(cid, str)
        assert len(cid) > 0
        assert reg.count() == 1

    def test_remove_client(self):
        reg = ClientRegistry()
        cid = reg.add("fake_ws_1")
        assert reg.count() == 1
        reg.remove(cid)
        assert reg.count() == 0

    def test_remove_nonexistent(self):
        reg = ClientRegistry()
        reg.remove("nonexistent")
        assert reg.count() == 0

    def test_count(self):
        reg = ClientRegistry()
        assert reg.count() == 0
        reg.add("a")
        reg.add("b")
        assert reg.count() == 2

    def test_get_all(self):
        reg = ClientRegistry()
        cid1 = reg.add("ws1")
        cid2 = reg.add("ws2")
        all_clients = reg.get_all()
        assert len(all_clients) == 2
        ids = {c[0] for c in all_clients}
        assert cid1 in ids
        assert cid2 in ids

    def test_thread_safety(self):
        reg = ClientRegistry()
        errors = []

        def add_and_remove():
            try:
                for _ in range(100):
                    cid = reg.add(object())
                    reg.remove(cid)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_and_remove) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert reg.count() == 0


class TestMakeMessage:
    def test_format(self):
        msg = make_message("broadcast", {"text": "hello"})
        data = json.loads(msg)
        assert data["type"] == "broadcast"
        assert data["payload"] == {"text": "hello"}
        assert "timestamp" in data

    def test_system_type(self):
        msg = make_message("system", {"info": "test"})
        data = json.loads(msg)
        assert data["type"] == "system"

    def test_direct_type(self):
        msg = make_message("direct", {"to": "abc"})
        data = json.loads(msg)
        assert data["type"] == "direct"
