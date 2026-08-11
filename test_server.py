import asyncio
import json
import pytest

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from server import handler, process_request, registry, make_message

PORT = 18765


async def http_get(host, port, path):
    reader, writer = await asyncio.open_connection(host, port)
    request = f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
    writer.write(request.encode())
    await writer.drain()
    raw = await asyncio.wait_for(reader.read(-1), timeout=5)
    writer.close()
    await writer.wait_closed()

    parts = raw.split(b"\r\n\r\n", 1)
    if len(parts) > 1:
        return json.loads(parts[1].decode())
    return None


@pytest.mark.asyncio
async def test_connect_assigns_unique_id():
    async with serve(handler, "localhost", PORT, process_request=process_request):
        async with connect(f"ws://localhost:{PORT}") as ws:
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
            assert msg["type"] == "system"
            assert "client_id" in msg["payload"]
            assert len(msg["payload"]["client_id"]) > 0
            assert msg["payload"]["message"].startswith("Connected as")


@pytest.mark.asyncio
async def test_two_clients_get_different_ids():
    async with serve(handler, "localhost", PORT, process_request=process_request):
        async with connect(f"ws://localhost:{PORT}") as ws1:
            raw1 = await asyncio.wait_for(ws1.recv(), timeout=5)
            msg1 = json.loads(raw1)

            async with connect(f"ws://localhost:{PORT}") as ws2:
                raw2 = await asyncio.wait_for(ws2.recv(), timeout=5)
                msg2 = json.loads(raw2)

                assert msg1["payload"]["client_id"] != msg2["payload"]["client_id"]


@pytest.mark.asyncio
async def test_broadcast_to_all_clients():
    async with serve(handler, "localhost", PORT, process_request=process_request):
        async with connect(f"ws://localhost:{PORT}") as ws1:
            await asyncio.wait_for(ws1.recv(), timeout=5)
            async with connect(f"ws://localhost:{PORT}") as ws2:
                await asyncio.wait_for(ws2.recv(), timeout=5)

                test_payload = {"message": "hello everyone"}
                await ws1.send(json.dumps({
                    "type": "broadcast",
                    "payload": test_payload,
                    "timestamp": ""
                }))

                msg1 = json.loads(await asyncio.wait_for(ws1.recv(), timeout=5))
                msg2 = json.loads(await asyncio.wait_for(ws2.recv(), timeout=5))

                assert msg1["type"] == "broadcast"
                assert msg1["payload"] == test_payload
                assert msg2["type"] == "broadcast"
                assert msg2["payload"] == test_payload


@pytest.mark.asyncio
async def test_disconnect_cleanup():
    async with serve(handler, "localhost", PORT, process_request=process_request):
        client_id = None
        async with connect(f"ws://localhost:{PORT}") as ws:
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
            client_id = msg["payload"]["client_id"]
            assert registry.count() == 1

        await asyncio.sleep(0.2)

        assert registry.count() == 0
        assert registry.get(client_id) is None


@pytest.mark.asyncio
async def test_health_endpoint():
    async with serve(handler, "localhost", PORT, process_request=process_request):
        resp = await http_get("localhost", PORT, "/health")
        assert resp["clients"] == 0
        assert resp["status"] == "ok"

        async with connect(f"ws://localhost:{PORT}") as ws:
            await asyncio.wait_for(ws.recv(), timeout=5)
            resp = await http_get("localhost", PORT, "/health")
            assert resp["clients"] == 1

        await asyncio.sleep(0.2)

        resp = await http_get("localhost", PORT, "/health")
        assert resp["clients"] == 0


@pytest.mark.asyncio
async def test_direct_message():
    async with serve(handler, "localhost", PORT, process_request=process_request):
        async with connect(f"ws://localhost:{PORT}") as ws1:
            raw1 = await asyncio.wait_for(ws1.recv(), timeout=5)
            msg1 = json.loads(raw1)
            client1_id = msg1["payload"]["client_id"]

            async with connect(f"ws://localhost:{PORT}") as ws2:
                raw2 = await asyncio.wait_for(ws2.recv(), timeout=5)
                msg2 = json.loads(raw2)
                client2_id = msg2["payload"]["client_id"]

                await ws1.send(json.dumps({
                    "type": "direct",
                    "payload": {"recipient": client2_id, "message": "hello client2"},
                    "timestamp": ""
                }))

                echo = json.loads(await asyncio.wait_for(ws1.recv(), timeout=5))
                assert echo["type"] == "direct"
                assert echo["payload"]["from"] == client1_id
                assert echo["payload"]["message"] == "hello client2"

                received = json.loads(await asyncio.wait_for(ws2.recv(), timeout=5))
                assert received["type"] == "direct"
                assert received["payload"]["from"] == client1_id
                assert received["payload"]["message"] == "hello client2"


@pytest.mark.asyncio
async def test_message_format():
    async with serve(handler, "localhost", PORT, process_request=process_request):
        async with connect(f"ws://localhost:{PORT}") as ws:
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
            assert set(msg.keys()) == {"type", "payload", "timestamp"}
            assert isinstance(msg["type"], str)
            assert isinstance(msg["payload"], dict)
            assert isinstance(msg["timestamp"], str)
            assert len(msg["timestamp"]) > 0


@pytest.mark.asyncio
async def test_thread_safe_registry():
    import concurrent.futures

    async with serve(handler, "localhost", PORT, process_request=process_request):
        async with connect(f"ws://localhost:{PORT}") as ws:
            await asyncio.wait_for(ws.recv(), timeout=5)

            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(registry.count) for _ in range(10)]
                results = [f.result() for f in futures]
                assert all(r == 1 for r in results)


@pytest.mark.asyncio
async def test_system_message_on_disconnect():
    async with serve(handler, "localhost", PORT, process_request=process_request):
        async with connect(f"ws://localhost:{PORT}") as ws1, \
                   connect(f"ws://localhost:{PORT}") as ws2:
            raw1 = await asyncio.wait_for(ws1.recv(), timeout=5)
            msg1 = json.loads(raw1)
            client1_id = msg1["payload"]["client_id"]

            raw2 = await asyncio.wait_for(ws2.recv(), timeout=5)
            msg2 = json.loads(raw2)

            await ws1.close()
            await asyncio.sleep(0.1)

            raw_sys = await asyncio.wait_for(ws2.recv(), timeout=5)
            sys_msg = json.loads(raw_sys)
            assert sys_msg["type"] == "system"
            assert "disconnected" in sys_msg["payload"]["message"]
            assert sys_msg["payload"]["client_id"] == client1_id
