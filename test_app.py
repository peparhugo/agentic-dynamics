import asyncio
import json
import urllib.request

import pytest
import websockets

from app import NotificationServer


async def health(port: int) -> dict:
    response = await asyncio.to_thread(urllib.request.urlopen, f"http://127.0.0.1:{port}/health")
    return json.loads(response.read())


@pytest.mark.asyncio
async def test_health_reports_connected_clients():
    async with NotificationServer(port=0) as server:
        assert (await health(server.port))["connected_clients"] == 0
        async with websockets.connect(f"ws://127.0.0.1:{server.port}"):
            assert (await health(server.port))["connected_clients"] == 1


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients():
    async with NotificationServer(port=0) as server:
        async with (
            websockets.connect(f"ws://127.0.0.1:{server.port}") as first,
            websockets.connect(f"ws://127.0.0.1:{server.port}") as second,
        ):
            await first.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))
            for client in (first, second):
                message = json.loads(await client.recv())
                assert message["type"] == "broadcast"
                assert message["payload"] == {"text": "hello"}
                assert isinstance(message["timestamp"], str)


@pytest.mark.asyncio
async def test_direct_message_reaches_only_target():
    async with NotificationServer(port=0) as server:
        async with (
            websockets.connect(f"ws://127.0.0.1:{server.port}") as sender,
            websockets.connect(f"ws://127.0.0.1:{server.port}") as target,
        ):
            sender_id, target_id = list(server.clients)
            await sender.send(json.dumps({"type": "direct", "payload": {"client_id": target_id, "text": "private"}}))
            message = json.loads(await target.recv())
            assert message["payload"]["text"] == "private"
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(sender.recv(), timeout=0.05)
            assert sender_id != target_id


@pytest.mark.asyncio
async def test_disconnect_removes_client():
    async with NotificationServer(port=0) as server:
        client = await websockets.connect(f"ws://127.0.0.1:{server.port}")
        assert server.client_count == 1
        await client.close()
        for _ in range(20):
            if server.client_count == 0:
                break
            await asyncio.sleep(0.01)
        assert server.client_count == 0
