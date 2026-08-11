import asyncio
import json
import pytest
import websockets
from websockets.exceptions import ConnectionClosed

import server
from server import main, ClientRegistry


def _reset_registry():
    server.registry = ClientRegistry()


@pytest.fixture(autouse=True)
def clean_registry():
    _reset_registry()
    yield
    _reset_registry()


@pytest.fixture
def server_args():
    return {"host": "localhost", "port": 8767}


async def _run_server(host, port):
    task = asyncio.ensure_future(main(host, port))
    await asyncio.sleep(0.1)
    return task


async def _stop_server(task):
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_connect_receives_client_id(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
        assert msg["type"] == "system"
        assert msg["payload"]["message"] == "connected"
        assert "client_id" in msg["payload"]
        assert "timestamp" in msg
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_broadcast_message_to_all(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws1:
            await ws1.recv()
            async with websockets.connect(url) as ws2:
                await ws2.recv()
                # ws1 receives join notification about ws2
                await asyncio.wait_for(ws1.recv(), timeout=5)

                test_payload = {"message": "hello"}
                await ws1.send(json.dumps({
                    "type": "broadcast",
                    "payload": test_payload,
                }))

                raw1 = await asyncio.wait_for(ws1.recv(), timeout=5)
                msg1 = json.loads(raw1)

                raw2 = await asyncio.wait_for(ws2.recv(), timeout=5)
                msg2 = json.loads(raw2)

        assert msg1["type"] == "broadcast"
        assert msg1["payload"] == test_payload
        assert msg2["type"] == "broadcast"
        assert msg2["payload"] == test_payload
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_disconnect_sends_leave_message(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws1:
            await ws1.recv()
            async with websockets.connect(url) as ws2:
                await ws2.recv()
                # ws1 receives join notification about ws2
                await asyncio.wait_for(ws1.recv(), timeout=5)

                await ws1.close()

                # ws2 receives ws1's leave
                raw = await asyncio.wait_for(ws2.recv(), timeout=5)
                msg = json.loads(raw)

        assert msg["type"] == "system"
        assert msg["payload"]["message"] == "left"
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_disconnect_removes_client_from_registry(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()
            assert await server.registry.get_count() == 1
        await asyncio.sleep(0.1)
        assert await server.registry.get_count() == 0
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_health_endpoint_returns_count(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"

        reader, writer = await asyncio.open_connection(host, port)
        request = f"GET /health HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
        writer.write(request.encode())
        await writer.drain()
        response = (await reader.read()).decode()
        writer.close()
        await writer.wait_closed()

        assert "200" in response
        body = response.split("\r\n\r\n", 1)[1]
        data = json.loads(body)
        assert data["connected_clients"] == 0

        async with websockets.connect(url) as ws:
            await ws.recv()
            assert await server.registry.get_count() == 1

            reader, writer = await asyncio.open_connection(host, port)
            request = f"GET /health HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
            writer.write(request.encode())
            await writer.drain()
            response = (await reader.read()).decode()
            writer.close()
            await writer.wait_closed()

            assert "200" in response
            body = response.split("\r\n\r\n", 1)[1]
            data = json.loads(body)
            assert data["connected_clients"] == 1
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_unassigned_type_defaults_to_broadcast(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()
            await ws.send(json.dumps({"payload": {"text": "no type"}}))
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
        assert msg["type"] == "broadcast"
        assert msg["payload"] == {"text": "no type"}
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_message_has_required_fields(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()
            await ws.send(json.dumps({
                "type": "direct",
                "payload": {"target": "user1", "text": "hello"},
            }))
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
        assert "type" in msg
        assert "payload" in msg
        assert "timestamp" in msg
        assert isinstance(msg["type"], str)
        assert isinstance(msg["payload"], dict)
        assert isinstance(msg["timestamp"], str)
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_invalid_json_is_ignored(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()
            await ws.send("not valid json at all {{{")
            await ws.send(json.dumps({"type": "broadcast", "payload": {"ok": True}}))
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
        assert msg["payload"] == {"ok": True}
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_multiple_clients_receive_join_and_leave(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws1:
            msg1 = json.loads(await ws1.recv())
            cid1 = msg1["payload"]["client_id"]

            async with websockets.connect(url) as ws2:
                msg2 = json.loads(await ws2.recv())
                cid2 = msg2["payload"]["client_id"]

                # ws1 receives ws2's join
                join_msg = await asyncio.wait_for(ws1.recv(), timeout=5)
                join_data = json.loads(join_msg)
                assert join_data["type"] == "system"
                assert join_data["payload"]["message"] == "joined"
                assert join_data["payload"]["client_id"] == cid2

            # ws1 receives ws2's leave
            leave_msg = await asyncio.wait_for(ws1.recv(), timeout=5)
            leave_data = json.loads(leave_msg)
            assert leave_data["type"] == "system"
            assert leave_data["payload"]["message"] == "left"
            assert leave_data["payload"]["client_id"] == cid2
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_client_ids_are_unique(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws1, websockets.connect(url) as ws2:
            msg1 = json.loads(await ws1.recv())
            msg2 = json.loads(await ws2.recv())
        assert msg1["payload"]["client_id"] != msg2["payload"]["client_id"]
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_subscribe_to_channel(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()
            await ws.send(json.dumps({
                "type": "subscribe",
                "channel": "alerts",
            }))
            await asyncio.sleep(0.1)
            channels = await server.registry.get_channels()
            assert "alerts" in channels
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_unsubscribe_from_channel(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()
            await ws.send(json.dumps({
                "type": "subscribe",
                "channel": "alerts",
            }))
            await asyncio.sleep(0.05)
            await ws.send(json.dumps({
                "type": "unsubscribe",
                "channel": "alerts",
            }))
            await asyncio.sleep(0.05)
            channels = await server.registry.get_channels()
        assert "alerts" not in channels
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_channel_message_routes_only_to_subscribers(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws1:
            await ws1.recv()
            async with websockets.connect(url) as ws2:
                await ws2.recv()
                await asyncio.wait_for(ws1.recv(), timeout=5)

                await ws1.send(json.dumps({
                    "type": "subscribe",
                    "channel": "alerts",
                }))

                await ws1.send(json.dumps({
                    "type": "chat",
                    "channel": "alerts",
                    "payload": {"text": "channel message"},
                }))

                raw = await asyncio.wait_for(ws1.recv(), timeout=5)
                msg = json.loads(raw)
                assert msg["type"] == "chat"
                assert msg["payload"] == {"text": "channel message"}

                try:
                    await asyncio.wait_for(ws2.recv(), timeout=0.3)
                    assert False, "ws2 should not have received channel message"
                except asyncio.TimeoutError:
                    pass
                except ConnectionClosed:
                    pass
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_no_channel_message_broadcasts_to_all(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws1:
            await ws1.recv()
            async with websockets.connect(url) as ws2:
                await ws2.recv()
                await asyncio.wait_for(ws1.recv(), timeout=5)

                await ws1.send(json.dumps({
                    "type": "broadcast",
                    "payload": {"text": "to everyone"},
                }))

                msg1 = json.loads(await asyncio.wait_for(ws1.recv(), timeout=5))
                msg2 = json.loads(await asyncio.wait_for(ws2.recv(), timeout=5))

        assert msg1["payload"] == {"text": "to everyone"}
        assert msg2["payload"] == {"text": "to everyone"}
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_multiple_channel_subscriptions(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()
            await ws.send(json.dumps({
                "type": "subscribe",
                "channel": "alerts",
            }))
            await ws.send(json.dumps({
                "type": "subscribe",
                "channel": "chat",
            }))
            await asyncio.sleep(0.05)

            channels = await server.registry.get_channels()
            assert "alerts" in channels
            assert "chat" in channels
            assert channels["alerts"] == 1
            assert channels["chat"] == 1
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_disconnect_cleans_up_subscriptions(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()
            await ws.send(json.dumps({
                "type": "subscribe",
                "channel": "alerts",
            }))
            await asyncio.sleep(0.05)
            channels = await server.registry.get_channels()
            assert channels["alerts"] == 1

        await asyncio.sleep(0.1)
        channels = await server.registry.get_channels()
        assert channels == {}
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_channels_endpoint(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            await ws.recv()
            await ws.send(json.dumps({
                "type": "subscribe",
                "channel": "alerts",
            }))
            await asyncio.sleep(0.05)

            reader, writer = await asyncio.open_connection(host, port)
            request = f"GET /channels HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
            writer.write(request.encode())
            await writer.drain()
            response = (await reader.read()).decode()
            writer.close()
            await writer.wait_closed()

            assert "200" in response
            body = response.split("\r\n\r\n", 1)[1]
            data = json.loads(body)
            assert "alerts" in data
            assert data["alerts"] == 1
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_channel_subscribers_endpoint(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws:
            welcome = json.loads(await ws.recv())
            client_id = welcome["payload"]["client_id"]

            await ws.send(json.dumps({
                "type": "subscribe",
                "channel": "alerts",
            }))
            await asyncio.sleep(0.05)

            reader, writer = await asyncio.open_connection(host, port)
            request = f"GET /channels/alerts/subscribers HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
            writer.write(request.encode())
            await writer.drain()
            response = (await reader.read()).decode()
            writer.close()
            await writer.wait_closed()

            assert "200" in response
            body = response.split("\r\n\r\n", 1)[1]
            data = json.loads(body)
            assert client_id in data
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_channel_message_only_delivered_to_channel_subscribers(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws1:
            await ws1.recv()
            async with websockets.connect(url) as ws2:
                await ws2.recv()
                await asyncio.wait_for(ws1.recv(), timeout=5)

                ws1_cid = await server.registry.get_client_id(ws1)
                ws2_cid = await server.registry.get_client_id(ws2)

                await ws1.send(json.dumps({
                    "type": "subscribe",
                    "channel": "alerts",
                }))

                await ws1.send(json.dumps({
                    "type": "notify",
                    "channel": "alerts",
                    "payload": {"alert": "disk full"},
                }))

                msg = json.loads(await asyncio.wait_for(ws1.recv(), timeout=5))
                assert msg["payload"] == {"alert": "disk full"}

                try:
                    await asyncio.wait_for(ws2.recv(), timeout=0.3)
                    assert False, "ws2 should not receive channel-only message"
                except asyncio.TimeoutError:
                    pass
                except ConnectionClosed:
                    pass
    finally:
        await _stop_server(task)


@pytest.mark.asyncio
async def test_subscribe_after_channel_message_not_received(server_args):
    host, port = server_args["host"], server_args["port"]
    task = await _run_server(host, port)
    try:
        url = f"ws://{host}:{port}"
        async with websockets.connect(url) as ws1:
            await ws1.recv()
            async with websockets.connect(url) as ws2:
                await ws2.recv()
                await asyncio.wait_for(ws1.recv(), timeout=5)

                await ws1.send(json.dumps({
                    "type": "subscribe",
                    "channel": "alerts",
                }))

                await ws1.send(json.dumps({
                    "type": "notify",
                    "channel": "alerts",
                    "payload": {"alert": "first"},
                }))

                await asyncio.wait_for(ws1.recv(), timeout=5)

                await ws2.send(json.dumps({
                    "type": "subscribe",
                    "channel": "alerts",
                }))

                await ws1.send(json.dumps({
                    "type": "notify",
                    "channel": "alerts",
                    "payload": {"alert": "second"},
                }))

                msg1 = json.loads(await asyncio.wait_for(ws1.recv(), timeout=5))
                msg2 = json.loads(await asyncio.wait_for(ws2.recv(), timeout=5))

                assert msg1["payload"] == {"alert": "second"}
                assert msg2["payload"] == {"alert": "second"}
    finally:
        await _stop_server(task)
