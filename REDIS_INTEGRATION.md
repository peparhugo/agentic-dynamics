# Redis Pub/Sub and SQLite Persistence Integration

## Overview
The notification server now includes:
- **Redis pub/sub** for distributed message delivery across multiple server instances
- **SQLite persistence** for message history
- **Client connection state** storage in Redis (survives server restart)
- **REST API** for message retrieval with pagination

## Architecture

### Message Flow
1. WebSocket client sends message
2. Server processes and validates message
3. **SQLite stores** message for history (timestamp, channel, type, payload)
4. **Redis publishes** to channel for other server instances
5. **WebSocket clients** receive message in real-time

### Distributed Deployment
```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ WebSocket
       ▼
┌─────────────────────────────────┐
│   Server Instance 1 (Port 8765) │
├─────────────────────────────────┤
│  WebSocket Handler              │
│  ↓                              │
│  Redis Publisher ───────┐       │
│  SQLite Store ──┐       │       │
└────────────────┼───────┼───────┘
                 │       │
                 ▼       ▼
              ┌──────────────┐
              │   Redis     │
              │  (Channels) │
              └──────────────┘
                 ▲
                 │
┌─────────────────────────────────┐
│   Server Instance 2 (Port 8766) │
├─────────────────────────────────┤
│  Redis Subscriber ──────────────┘
│  ↓
│  WebSocket Handler
└─────────────────────────────────┘
```

## Configuration

### Environment Variables
- `REDIS_URL`: Redis connection string (default: `redis://localhost:6379`)
- `DATABASE_URL`: SQLite database path (default: `messages.db`)

### Example
```bash
export REDIS_URL="redis://redis-server:6379"
export DATABASE_URL="/var/lib/messages.db"
python3 app.py
```

## REST Endpoints

### GET /messages
Retrieve stored messages with pagination.

**Parameters:**
- `limit` (optional): Number of messages to return (default: 50, max: 1000)
- `offset` (optional): Number of messages to skip (default: 0)
- `channel` (optional): Filter by channel name

**Examples:**
```bash
# Get 50 most recent messages
curl http://localhost:8080/messages

# Get messages from alerts channel
curl http://localhost:8080/messages?channel=alerts

# Pagination: get 25 messages, skip first 50
curl http://localhost:8080/messages?limit=25&offset=50

# Get direct messages for a client
curl http://localhost:8080/messages?channel=direct:client-id
```

**Response:**
```json
{
  "messages": [
    {
      "id": 1,
      "channel": "alerts",
      "type": "broadcast",
      "payload": {"content": "alert message"},
      "timestamp": "2024-01-01T00:00:00+00:00"
    }
  ],
  "limit": 50,
  "offset": 0,
  "total": 1,
  "count": 1,
  "timestamp": "2024-08-13T08:00:00+00:00"
}
```

## Database Schema

### messages table
```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT NOT NULL,
    type TEXT NOT NULL,
    payload TEXT NOT NULL,        -- JSON string
    timestamp TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_channel ON messages (channel);
CREATE INDEX idx_timestamp ON messages (timestamp);
```

### Redis Keys
- `client:{client_id}`: Client connection state (24-hour TTL)
  ```json
  {
    "connected_at": "2024-08-13T08:00:00+00:00",
    "status": "connected"
  }
  ```

## Features

### Message Persistence
- All broadcast messages stored with channel, type, payload, and timestamp
- Direct messages stored in `direct:{recipient_id}` channel
- System messages (connect/disconnect) stored
- Automatic cleanup with configurable retention (currently no cleanup)

### Redis Pub/Sub
- Real-time message distribution
- Channels: broadcast, system, direct:{client_id}, custom channels
- Multiple server instances share same Redis backbone
- Graceful degradation if Redis unavailable

### Client Connection State
- Stored in Redis with 24-hour TTL
- Survives server restart
- Includes connection timestamp and status
- Queryable for monitoring

## Testing

### Test Coverage
- 50 total tests, all passing
- 6 database tests
- 8 integration tests
- Backward compatibility verified

### Run Tests
```bash
python3 -m pytest test_app.py -v
```

## Backward Compatibility

All existing WebSocket functionality is preserved:
- Real-time messaging works without Redis/database
- Channel subscriptions work as before
- Direct messaging works as before
- HTTP health/channels endpoints unchanged

If Redis is unavailable, messages are still delivered locally (WebSocket only).

## Example Usage

### Broadcasting a message
```json
{
  "type": "broadcast",
  "channel": "alerts",
  "payload": {"severity": "high", "message": "Server alert"}
}
```

### Sending a direct message
```json
{
  "type": "direct",
  "payload": {
    "target_id": "client-id",
    "message": "Hello client"
  }
}
```

### Subscribing to a channel
```json
{
  "type": "subscribe",
  "payload": {"channel": "alerts"}
}
```

## Performance Considerations

1. **SQLite**: Good for single-server message history
2. **Redis**: Handles distribution across server instances
3. **WebSocket**: Real-time delivery with connection pooling
4. **Indexes**: Channel and timestamp indexes for faster queries
5. **Limits**: Max 1000 messages per API request

## Security Notes

- Use authentication for Redis in production
- Validate all message payloads
- Use TLS for WebSocket (wss://)
- Implement rate limiting for API endpoints
- Store sensitive data securely
