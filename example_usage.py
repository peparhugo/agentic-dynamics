"""Example usage of the WebSocket Notification Server."""

import asyncio
import json
import websockets
import aiohttp

async def example_client():
    """Example WebSocket client that connects and sends messages."""
    print("Connecting to WebSocket server...")
    async with websockets.connect('ws://localhost:8765') as ws:
        # Receive client ID from server
        response = await ws.recv()
        msg = json.loads(response)
        client_id = msg['payload']['client_id']
        print(f"Connected with client ID: {client_id}")

        # Send a broadcast message
        broadcast = json.dumps({
            'type': 'broadcast',
            'payload': {'text': 'Hello everyone!'},
            'timestamp': '2024-01-01T00:00:00'
        })
        print(f"Sending broadcast: {broadcast}")
        await ws.send(broadcast)

        # Wait for responses
        try:
            while True:
                msg_data = await asyncio.wait_for(ws.recv(), timeout=5)
                msg = json.loads(msg_data)
                print(f"Received: {msg}")
        except asyncio.TimeoutError:
            print("No more messages")


async def check_health():
    """Check server health status."""
    print("Checking server health...")
    async with aiohttp.ClientSession() as session:
        async with session.get('http://localhost:8080/health') as resp:
            data = await resp.json()
            print(f"Server health: {data}")


async def main():
    """Run example scenarios."""
    # Check server is running
    try:
        await check_health()
    except aiohttp.ClientConnectorError:
        print("ERROR: Server is not running. Start it with: python3 notification_server.py")
        return

    # Run example client
    try:
        await example_client()
    except Exception as e:
        print(f"Error: {e}")


if __name__ == '__main__':
    asyncio.run(main())
