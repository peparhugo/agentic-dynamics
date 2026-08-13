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


async def get_message_history():
    """Retrieve message history from persistent storage."""
    print("Retrieving message history...")
    async with aiohttp.ClientSession() as session:
        async with session.get('http://localhost:8080/messages?limit=10') as resp:
            data = await resp.json()
            print(f"Message history (total: {data['total']}):")
            for msg in data['messages']:
                print(f"  - [{msg['timestamp']}] {msg['channel']}: {msg['payload']}")


async def get_channel_messages(channel: str):
    """Retrieve messages for a specific channel."""
    print(f"Retrieving messages for channel '{channel}'...")
    async with aiohttp.ClientSession() as session:
        async with session.get(f'http://localhost:8080/messages?channel={channel}') as resp:
            data = await resp.json()
            print(f"Messages in '{channel}' channel (total: {data['total']}):")
            for msg in data['messages']:
                print(f"  - {msg['payload']}")


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
        print("\n--- WebSocket Client Example ---")
        # Create a task for the client to run briefly
        client_task = asyncio.create_task(example_client())
        try:
            await asyncio.wait_for(client_task, timeout=3)
        except asyncio.TimeoutError:
            client_task.cancel()

        # Show message history features
        print("\n--- Message History Example ---")
        await get_message_history()

        print("\n--- Channel Messages Example ---")
        await get_channel_messages('broadcast')

    except Exception as e:
        print(f"Error: {e}")


if __name__ == '__main__':
    asyncio.run(main())
