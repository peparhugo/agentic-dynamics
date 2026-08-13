# Implementation Summary: Rate Limiting, Message History & Expiry

## Rate Limiting
- **File**: `rate_limiter.py`
- **Per-client limit**: 100 messages per minute (configurable via `RATE_LIMIT` env var)
- **Storage**: Redis counters with automatic expiration
- **Behavior**: Returns system message with rate_limit_exceeded error
- **Tests**: 3 tests for RateLimiter class

## Persistent Message History
- **Endpoint**: `GET /history?channel=X&since=ISO_TIMESTAMP&limit=50`
- **Required params**: `channel` (string)
- **Optional params**: 
  - `since` (ISO 8601 timestamp) - filter messages after this time
  - `limit` (int, default 50, max 1000) - number of messages to return
  - `offset` (int, default 0) - pagination offset
- **Response fields**:
  - `messages` (array) - messages in chronological order (oldest first)
  - `has_more` (boolean) - indicates if more results exist
  - `count` (int) - number of messages in current response
  - `total` (int) - total count of matching messages
  - `channel`, `limit`, `offset`, `since` - echoed request params
- **Tests**: 9 tests for history endpoint

## Message Expiry/Cleanup
- **Background task**: Runs on server startup and periodically every hour
- **Initial cleanup**: Runs once on startup
- **Cleanup interval**: 1 hour (3600 seconds)
- **TTL**: 7 days (configurable via `MESSAGE_TTL_DAYS` env var)
- **Implementation**: `cleanup_old_messages()` in MessagePersistence
- **Tests**: 4 tests for cleanup functionality

## New Database Methods (message_persistence.py)
- `get_messages_since(channel, since, limit, offset)` - messages after timestamp in ASC order
- `get_messages_count_since(channel, since)` - count of messages after timestamp
- `get_messages_chronological(channel, limit, offset)` - messages in ASC order (for history endpoint)
- `cleanup_old_messages(ttl_days)` - delete old messages, return count deleted
- **Tests**: 3 tests for time range queries

## Integration Points
- Rate limiter connected in NotificationServer.run()
- Rate check applied in _handle_message() before routing
- /history route added in _setup_rest_routes()
- Message cleanup task started in run() and cancelled in shutdown
- No changes to transport layer or pub/sub functionality

## Configuration
- `RATE_LIMIT`: Messages per minute per client (default: 100)
- `MESSAGE_TTL_DAYS`: Days before message cleanup (default: 7)
- `REDIS_URL`: Redis connection URL (default: redis://localhost:6379)

## Test Coverage
- **Total tests**: 73 (all passing)
- **New test classes**: 5 (RateLimiter, HistoryEndpoint, MessageCleanup, MessagePersistenceTimeRange)
- **New tests**: 19
