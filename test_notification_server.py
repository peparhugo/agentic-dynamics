import asyncio
import json
import urllib.error
import urllib.request
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
import websockets

from notification_server import NotificationServer, make_message


@asynccontextmanager
async def running_server():
    server = NotificationServer()
    async with websockets.serve(
        server.handler,
        "127.0.0.1",
        0,
        process_request=server.process_request,
    ) as ws_server:
        port = ws_server.sockets[0].getsockname()[1]
        yield f"127.0.0.1:{port}", server


@pytest_asyncio.fixture
async def server():
    async with running_server() as (addr, srv):
        yield addr, srv


async def http_get(addr: str, path: str) -> tuple[int, dict]:
    def _get():
        with urllib.request.urlopen(f"http://{addr}{path}", timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    return await asyncio.get_running_loop().run_in_executor(None, _get)


async def connect_client(addr: str):
    ws = await websockets.connect(f"ws://{addr}")
    welcome = json.loads(await ws.recv())
    client_id = welcome["payload"]["client_id"]
    return ws, client_id, welcome


async def wait_count(registry, expected: int, timeout: float = 2.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if registry.count() == expected:
            return
        await asyncio.sleep(0.02)
    raise AssertionError(
        f"registry count never reached {expected}, still {registry.count()}"
    )


async def test_connect_assigns_unique_ids(server):
    addr, srv = server
    ws1, id1, welcome1 = await connect_client(addr)
    ws2, id2, welcome2 = await connect_client(addr)
    assert id1 != id2
    assert welcome1["type"] == "system"
    assert welcome2["type"] == "system"
    assert srv.registry.count() == 2
    await ws1.close()
    await ws2.close()


async def test_health_returns_connected_count(server):
    addr, srv = server
    status, body = await http_get(addr, "/health")
    assert status == 200
    assert body == {"status": "ok", "connected_clients": 0}

    ws1, _, _ = await connect_client(addr)
    ws2, _, _ = await connect_client(addr)

    status, body = await http_get(addr, "/health")
    assert status == 200
    assert body["connected_clients"] == 2

    await ws1.close()
    await ws2.close()
    await wait_count(srv.registry, 0)

    status, body = await http_get(addr, "/health")
    assert status == 200
    assert body["connected_clients"] == 0


async def test_unknown_http_path_returns_404(server):
    addr, _ = server
    def _get():
        with urllib.request.urlopen(f"http://{addr}/nope", timeout=5) as resp:
            return resp.status
    with pytest.raises(urllib.error.HTTPError) as exc:
        await asyncio.get_running_loop().run_in_executor(None, _get)
    assert exc.value.code == 404


async def test_message_format(server):
    addr, _ = server
    ws, _, welcome = await connect_client(addr)
    assert set(welcome) == {"type", "payload", "timestamp"}
    assert welcome["type"] == "system"
    assert isinstance(welcome["payload"], dict)
    assert isinstance(welcome["timestamp"], str)
    assert welcome["payload"]["client_id"]
    await ws.close()


async def test_broadcast_reaches_all_clients(server):
    addr, _ = server
    ws1, _, _ = await connect_client(addr)
    ws2, _, _ = await connect_client(addr)

    payload = {"text": "hello everyone"}
    await ws1.send(json.dumps(make_message("broadcast", payload)))

    got1 = json.loads(await ws1.recv())
    got2 = json.loads(await ws2.recv())

    assert got1["type"] == "broadcast"
    assert got2["type"] == "broadcast"
    assert got1["payload"] == payload
    assert got2["payload"] == payload
    assert got1["timestamp"] == got2["timestamp"]

    await ws1.close()
    await ws2.close()


async def test_direct_message_reaches_target_only(server):
    addr, _ = server
    ws1, id1, _ = await connect_client(addr)
    ws2, id2, _ = await connect_client(addr)

    payload = {"to": id2, "text": "secret"}
    await ws1.send(json.dumps(make_message("direct", payload)))

    got = json.loads(await ws2.recv())
    assert got["type"] == "direct"
    assert got["payload"] == payload

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(ws1.recv(), 0.2)

    await ws1.close()
    await ws2.close()


async def test_direct_to_unknown_target_errors(server):
    addr, _ = server
    ws, _, _ = await connect_client(addr)

    payload = {"to": "does-not-exist", "text": "hi"}
    await ws.send(json.dumps(make_message("direct", payload)))

    got = json.loads(await ws.recv())
    assert got["type"] == "system"
    assert got["payload"]["message"] == "error"

    await ws.close()


async def test_disconnect_removes_client(server):
    addr, srv = server
    ws1, id1, _ = await connect_client(addr)
    ws2, id2, _ = await connect_client(addr)
    assert srv.registry.count() == 2

    await ws1.close()
    await wait_count(srv.registry, 1)

    assert srv.registry.get(id1) is None
    assert srv.registry.get(id2) is not None

    payload = {"text": "after disconnect"}
    await ws2.send(json.dumps(make_message("broadcast", payload)))
    got = json.loads(await ws2.recv())
    assert got["payload"] == payload

    await ws2.close()
    await wait_count(srv.registry, 0)


async def test_system_ack_roundtrip(server):
    addr, _ = server
    ws, _, _ = await connect_client(addr)

    payload = {"note": "ping"}
    await ws.send(json.dumps(make_message("system", payload)))

    got = json.loads(await ws.recv())
    assert got["type"] == "system"
    assert got["payload"]["message"] == "ack"
    assert got["payload"]["echo"] == payload

    await ws.close()


async def test_invalid_json_returns_error(server):
    addr, _ = server
    ws, _, _ = await connect_client(addr)

    await ws.send("not-json")
    got = json.loads(await ws.recv())
    assert got["type"] == "system"
    assert got["payload"]["message"] == "error"

    await ws.close()
