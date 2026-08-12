import asyncio
import json
import urllib.request

import pytest
import websockets

from app import NotificationServer


def get_health(url: str) -> dict:
    with urllib.request.urlopen(url) as response:
        return json.load(response)


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients_and_disconnect_is_removed():
    server = NotificationServer("127.0.0.1", 0)
    await server.start()
    first = await websockets.connect(f"ws://127.0.0.1:{server.port}")
    second = await websockets.connect(f"ws://127.0.0.1:{server.port}")
    try:
        assert len(server.clients) == 2
        await server.broadcast({"type": "broadcast", "payload": {"message": "hello"}})
        received = await asyncio.gather(first.recv(), second.recv())
        assert [json.loads(message)["payload"] for message in received] == [
            {"message": "hello"},
            {"message": "hello"},
        ]
        await first.close()
        for _ in range(20):
            if len(server.clients) == 1:
                break
            await asyncio.sleep(0.01)
        assert len(server.clients) == 1
    finally:
        await second.close()
        await server.stop()


@pytest.mark.asyncio
async def test_health_returns_connected_client_count():
    server = NotificationServer("127.0.0.1", 0)
    await server.start()
    clients = [await websockets.connect(f"ws://127.0.0.1:{server.port}") for _ in range(2)]
    try:
        health = await asyncio.to_thread(get_health, f"http://127.0.0.1:{server.port}/health")
        assert health == {"connected_clients": 2}
    finally:
        await asyncio.gather(*(client.close() for client in clients))
        await server.stop()
