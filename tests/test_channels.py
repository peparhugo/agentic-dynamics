import asyncio

import httpx
import pytest
import pytest_asyncio
import websockets

from app import create_server, decode_message, encode_message


@pytest_asyncio.fixture
async def server():
    app, serve_coro = create_server("127.0.0.1", 0)
    srv = await serve_coro
    port = srv.sockets[0].getsockname()[1]
    yield app, port
    srv.close()
    await srv.wait_closed()


async def connect_client(port):
    ws = await websockets.connect(f"ws://127.0.0.1:{port}")
    hello = decode_message(await ws.recv())
    return ws, hello


async def get(port, path):
    async with httpx.AsyncClient() as client:
        return await client.get(f"http://127.0.0.1:{port}{path}")


async def test_channel_message_routes_only_to_subscribers(server):
    _, port = server
    ws1, _ = await connect_client(port)
    ws2, _ = await connect_client(port)
    ws3, _ = await connect_client(port)

    await ws1.send(encode_message({"type": "subscribe", "channel": "alerts"}))
    await ws3.send(encode_message({"type": "subscribe", "channel": "alerts"}))
    await asyncio.sleep(0.1)

    await ws1.send(
        encode_message({"type": "broadcast", "channel": "alerts", "payload": {"text": "hi"}})
    )

    r1 = decode_message(await asyncio.wait_for(ws1.recv(), timeout=5))
    r3 = decode_message(await asyncio.wait_for(ws3.recv(), timeout=5))
    assert r1["payload"]["text"] == "hi"
    assert r3["payload"]["text"] == "hi"

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(ws2.recv(), timeout=0.5)

    await ws1.close()
    await ws2.close()
    await ws3.close()


async def test_unsubscribe_stops_delivery(server):
    _, port = server
    ws1, _ = await connect_client(port)
    ws2, _ = await connect_client(port)

    await ws1.send(encode_message({"type": "subscribe", "channel": "chat"}))
    await ws2.send(encode_message({"type": "subscribe", "channel": "chat"}))
    await asyncio.sleep(0.1)
    await ws2.send(encode_message({"type": "unsubscribe", "channel": "chat"}))
    await asyncio.sleep(0.1)

    await ws1.send(
        encode_message({"type": "broadcast", "channel": "chat", "payload": {"text": "yo"}})
    )

    r1 = decode_message(await asyncio.wait_for(ws1.recv(), timeout=5))
    assert r1["payload"]["text"] == "yo"

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(ws2.recv(), timeout=0.5)

    await ws1.close()
    await ws2.close()


async def test_client_subscribes_to_multiple_channels(server):
    _, port = server
    ws1, _ = await connect_client(port)
    ws2, _ = await connect_client(port)

    await ws1.send(encode_message({"type": "subscribe", "channel": "alerts"}))
    await ws1.send(encode_message({"type": "subscribe", "channel": "system"}))
    await ws2.send(encode_message({"type": "subscribe", "channel": "alerts"}))
    await asyncio.sleep(0.1)

    await ws1.send(
        encode_message({"type": "broadcast", "channel": "system", "payload": {"text": "sys"}})
    )
    r1 = decode_message(await asyncio.wait_for(ws1.recv(), timeout=5))
    assert r1["payload"]["text"] == "sys"
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(ws2.recv(), timeout=0.5)

    await ws1.send(
        encode_message({"type": "broadcast", "channel": "alerts", "payload": {"text": "alert"}})
    )
    a1 = decode_message(await asyncio.wait_for(ws1.recv(), timeout=5))
    a2 = decode_message(await asyncio.wait_for(ws2.recv(), timeout=5))
    assert a1["payload"]["text"] == "alert"
    assert a2["payload"]["text"] == "alert"

    await ws1.close()
    await ws2.close()


async def test_channels_endpoint_lists_counts(server):
    _, port = server
    ws1, _ = await connect_client(port)
    ws2, _ = await connect_client(port)

    await ws1.send(encode_message({"type": "subscribe", "channel": "alerts"}))
    await ws2.send(encode_message({"type": "subscribe", "channel": "alerts"}))
    await ws2.send(encode_message({"type": "subscribe", "channel": "chat"}))
    await asyncio.sleep(0.1)

    resp = await get(port, "/channels")
    assert resp.status_code == 200
    assert resp.json() == {"channels": {"alerts": 2, "chat": 1}}

    await ws1.close()
    await ws2.close()


async def test_channel_subscribers_endpoint_lists_ids(server):
    _, port = server
    ws1, hello1 = await connect_client(port)
    ws2, hello2 = await connect_client(port)

    await ws1.send(encode_message({"type": "subscribe", "channel": "alerts"}))
    await ws2.send(encode_message({"type": "subscribe", "channel": "alerts"}))
    await asyncio.sleep(0.1)

    resp = await get(port, "/channels/alerts/subscribers")
    assert resp.status_code == 200
    assert resp.json() == {
        "subscribers": sorted([hello1["payload"]["id"], hello2["payload"]["id"]])
    }

    await ws1.close()
    await ws2.close()


async def test_disconnect_removes_subscriptions(server):
    _, port = server
    ws1, _ = await connect_client(port)
    ws2, hello2 = await connect_client(port)

    await ws1.send(encode_message({"type": "subscribe", "channel": "alerts"}))
    await ws2.send(encode_message({"type": "subscribe", "channel": "alerts"}))
    await asyncio.sleep(0.1)

    assert (await get(port, "/channels")).json() == {"channels": {"alerts": 2}}

    await ws1.close()
    await asyncio.wait_for(ws2.recv(), timeout=5)  # consume disconnect notification

    resp = await get(port, "/channels/alerts/subscribers")
    assert resp.json() == {"subscribers": [hello2["payload"]["id"]]}

    await ws2.close()
