"""
Example WebSocket client demonstrating the notification server.
"""

import asyncio
import json
import websockets


async def broadcast_example():
    """Example of sending a broadcast message."""
    async with websockets.connect("ws://localhost:8765") as websocket:
        greeting = await websocket.recv()
        data = json.loads(greeting)
        client_id = data["payload"]["client_id"]
        print(f"Connected with client ID: {client_id}")
        print(f"Greeting: {data}")

        await websocket.send(json.dumps({
            "type": "broadcast",
            "payload": {
                "text": "Hello to all connected clients!",
                "sender": client_id
            }
        }))
        print("Broadcast message sent")

        await asyncio.sleep(1)


async def listen_example():
    """Example of listening for broadcast messages."""
    async with websockets.connect("ws://localhost:8765") as websocket:
        greeting = await websocket.recv()
        data = json.loads(greeting)
        client_id = data["payload"]["client_id"]
        print(f"Connected with client ID: {client_id}")

        print("Listening for messages (press Ctrl+C to exit)...")
        async for message in websocket:
            data = json.loads(message)
            print(f"Received {data['type']}: {data['payload']}")


async def direct_message_example():
    """Example of sending direct messages between clients."""
    async with websockets.connect("ws://localhost:8765") as websocket:
        greeting = await websocket.recv()
        data = json.loads(greeting)
        client_id = data["payload"]["client_id"]
        print(f"Connected with client ID: {client_id}")

        target_id = input("Enter target client ID: ")

        await websocket.send(json.dumps({
            "type": "direct",
            "payload": {
                "target_id": target_id,
                "text": "This is a direct message!"
            }
        }))
        print("Direct message sent")


async def health_check_example():
    """Example of checking server health."""
    import aiohttp

    async with aiohttp.ClientSession() as session:
        async with session.get("http://localhost:9765/health") as response:
            data = await response.json()
            print(f"Health check: {data}")
            print(f"Connected clients: {data['connected_clients']}")


async def main():
    """Run examples based on user choice."""
    print("WebSocket Notification Server - Examples")
    print("1. Send broadcast message")
    print("2. Listen for messages")
    print("3. Send direct message")
    print("4. Check server health")

    choice = input("Choose an example (1-4): ")

    if choice == "1":
        await broadcast_example()
    elif choice == "2":
        await listen_example()
    elif choice == "3":
        await direct_message_example()
    elif choice == "4":
        await health_check_example()
    else:
        print("Invalid choice")


if __name__ == "__main__":
    asyncio.run(main())
