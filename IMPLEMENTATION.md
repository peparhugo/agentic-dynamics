# WebSocket Notification Server

A high-performance, async-based notification server built with Python, featuring WebSocket support and REST health endpoints.

## Architecture

### Core Components

1. **ClientRegistry** - Thread-safe client connection registry
   - Uses `threading.RLock()` for thread-safe operations
   - Tracks active WebSocket connections with unique UUIDs
   - Provides atomic operations: register, unregister, get, get_all, count

2. **NotificationServer** - Main application class
   - Dual-server setup: WebSocket (port 8765) + HTTP REST (port 8080)
   - Asynchronous message handling with asyncio
   - Support for three message types: `broadcast`, `direct`, `system`

### Key Features

#### Message Format
```json
{
  "type": "broadcast|direct|system",
  "payload": { "...": "..." },
  "timestamp": "2024-01-01T00:00:00+00:00"
}
```

#### WebSocket Operations

- **Connect**: Client receives welcome system message with assigned ID
- **Broadcast**: Sender's message relayed to all OTHER clients (excluded sender)
- **Direct**: Target-specific message from sender
- **System Messages**: Connection/disconnection events broadcast to all clients
- **Disconnect**: Clean removal with notification to remaining clients

#### HTTP REST Endpoints

- `GET /health` - Returns:
  ```json
  {
    "status": "healthy",
    "connected_clients": 5,
    "timestamp": "2024-01-01T00:00:00+00:00"
  }
  ```

### Thread Safety

- `ClientRegistry` uses `RLock` (reentrant lock) for all dict operations
- All async broadcast operations gather concurrently with `asyncio.gather()`
- Connection closed exceptions are gracefully handled

### Error Handling

- Invalid JSON in messages is silently ignored
- Closed WebSocket connections don't crash the server
- Non-existent direct message targets are silently ignored

## Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python3 app.py

# Run tests
pytest test_app.py -v
```

## Testing

- **18 comprehensive tests** covering:
  - Client registry operations and thread safety
  - Broadcast and direct messaging
  - System message generation
  - Health endpoint
  - Edge cases (closed connections, invalid JSON, non-existent clients)
  - Message format validation

All tests use pytest + pytest-asyncio with mock WebSocket objects for isolation.
