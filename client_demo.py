"""
Simple WebSocket client demo for testing the notification server.

Usage:
    python3 client_demo.py
"""

import asyncio
import json
import websockets
from datetime import datetime, timezone


async def demo_client():
    """Connect to the server and test basic functionality."""
    uri = "ws://127.0.0.1:8765"

    async with websockets.connect(uri) as websocket:
        # Receive connection confirmation
        msg = await websocket.recv()
        data = json.loads(msg)
        client_id = data["payload"]["client_id"]
        print(f"Connected! Client ID: {client_id}")
        print(f"Server message: {data}\n")

        # Send a broadcast message
        print("Sending broadcast message...")
        broadcast = {
            "type": "broadcast",
            "payload": {"message": "Hello from demo client!"},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await websocket.send(json.dumps(broadcast))

        # Receive the broadcast echo
        response = await websocket.recv()
        data = json.loads(response)
        print(f"Received broadcast: {data}\n")

        # Send a system message
        print("Sending system message...")
        system_msg = {
            "type": "system",
            "payload": {"action": "alert", "message": "System notification"},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await websocket.send(json.dumps(system_msg))

        # Receive the system message echo
        response = await websocket.recv()
        data = json.loads(response)
        print(f"Received system message: {data}\n")

        print("Demo complete!")


async def demo_multiple_clients():
    """Demo with multiple clients connecting simultaneously."""
    async def client(client_num):
        uri = "ws://127.0.0.1:8765"
        async with websockets.connect(uri) as ws:
            # Get connection confirmation
            msg = await ws.recv()
            data = json.loads(msg)
            client_id = data["payload"]["client_id"]
            print(f"[Client {client_num}] Connected with ID: {client_id}")

            # Send a broadcast
            broadcast = {
                "type": "broadcast",
                "payload": {"from": f"client_{client_num}", "message": f"Hello from client {client_num}"},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await ws.send(json.dumps(broadcast))

            # Listen for any broadcasts (including own)
            msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
            data = json.loads(msg)
            print(f"[Client {client_num}] Received: {data['payload']}")

    # Connect 3 clients
    await asyncio.gather(
        client(1),
        client(2),
        client(3),
    )


if __name__ == "__main__":
    print("=== WebSocket Notification Server Demo ===\n")
    print("Make sure the server is running:")
    print("  python3 notification_server.py\n")

    try:
        asyncio.run(demo_client())
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure the server is running on ws://127.0.0.1:8765")
