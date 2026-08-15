import asyncio
import json

import pytest
import websockets

from server import NotificationServer, make_message


async def start_server():
    server = NotificationServer(host="127.0.0.1", port=0, health_port=0)
    await server.start()
    return server


async def connect_client(server):
    websocket = await websockets.connect(f"ws://{server.host}:{server.port}")
    first = json.loads(await asyncio.wait_for(websocket.recv(), timeout=2))
    return websocket, first["payload"]["client_id"]


async def http_get(host, port, path="/health"):
    reader, writer = await asyncio.open_connection(host, port)
    request = f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
    writer.write(request.encode("latin-1"))
    await writer.drain()
    response = await asyncio.wait_for(reader.read(), timeout=2)
    writer.close()
    await writer.wait_closed()
    header, _, body = response.partition(b"\r\n\r\n")
    status_line = header.split(b"\r\n", 1)[0].decode("latin-1")
    return status_line, json.loads(body.decode("utf-8"))


async def wait_until(predicate, timeout=2.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.01)
    return predicate()


async def test_assigns_unique_ids():
    server = await start_server()
    try:
        ws_a, id_a = await connect_client(server)
        ws_b, id_b = await connect_client(server)
        assert id_a != id_b
        assert server.registry.count() == 2
        await ws_a.close()
        await ws_b.close()
    finally:
        await server.stop()


async def test_broadcast_delivers_to_all():
    server = await start_server()
    try:
        ws_a, id_a = await connect_client(server)
        ws_b, id_b = await connect_client(server)

        sent = await server.broadcast("broadcast", {"message": "hello"})
        assert sent == 2

        msg_a = json.loads(await asyncio.wait_for(ws_a.recv(), timeout=2))
        msg_b = json.loads(await asyncio.wait_for(ws_b.recv(), timeout=2))

        assert msg_a["type"] == "broadcast"
        assert msg_a["payload"] == {"message": "hello"}
        assert msg_a["timestamp"]
        assert msg_b == msg_a or (
            msg_b["type"] == "broadcast" and msg_b["payload"] == {"message": "hello"}
        )
        await ws_a.close()
        await ws_b.close()
    finally:
        await server.stop()


async def test_direct_delivers_to_target_only():
    server = await start_server()
    try:
        ws_a, id_a = await connect_client(server)
        ws_b, id_b = await connect_client(server)

        delivered = await server.send_to(id_a, "direct", {"message": "secret"})
        assert delivered is True

        msg_a = json.loads(await asyncio.wait_for(ws_a.recv(), timeout=2))
        assert msg_a["type"] == "direct"
        assert msg_a["payload"] == {"message": "secret"}

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws_b.recv(), timeout=0.3)

        await ws_a.close()
        await ws_b.close()
    finally:
        await server.stop()


async def test_disconnect_removes_client():
    server = await start_server()
    try:
        ws, client_id = await connect_client(server)
        assert server.registry.count() == 1
        await ws.close()
        assert await wait_until(lambda: server.registry.count() == 0)
    finally:
        await server.stop()


async def test_health_returns_connected_count():
    server = await start_server()
    try:
        ws_a, id_a = await connect_client(server)
        ws_b, id_b = await connect_client(server)

        status_line, body = await http_get(server.host, server.health_port)
        assert "200 OK" in status_line
        assert body["connected"] == 2

        await ws_a.close()
        assert await wait_until(lambda: server.registry.count() == 1)
        status_line, body = await http_get(server.host, server.health_port)
        assert body["connected"] == 1

        await ws_b.close()
    finally:
        await server.stop()


async def test_health_returns_zero_when_empty():
    server = await start_server()
    try:
        status_line, body = await http_get(server.host, server.health_port)
        assert "200 OK" in status_line
        assert body["connected"] == 0
    finally:
        await server.stop()


async def test_incoming_broadcast_is_relayed():
    server = await start_server()
    try:
        ws_a, id_a = await connect_client(server)
        ws_b, id_b = await connect_client(server)

        await ws_a.send(json.dumps({"type": "broadcast", "payload": {"msg": "ping"}}))

        msg_a = json.loads(await asyncio.wait_for(ws_a.recv(), timeout=2))
        msg_b = json.loads(await asyncio.wait_for(ws_b.recv(), timeout=2))
        assert msg_a["type"] == "broadcast"
        assert msg_a["payload"] == {"msg": "ping"}
        assert msg_b["type"] == "broadcast"
        assert msg_b["payload"] == {"msg": "ping"}

        await ws_a.close()
        await ws_b.close()
    finally:
        await server.stop()


async def test_message_format():
    message = make_message("system", {"client_id": "abc"})
    assert set(message.keys()) == {"type", "payload", "timestamp"}
    assert message["type"] == "system"
    assert message["payload"] == {"client_id": "abc"}
    assert isinstance(message["timestamp"], str)
