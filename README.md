# WebSocket Notification Server

An asyncio notification server using `websockets`, with Redis pub/sub as its
cross-instance message backbone and SQLite message history. Connected clients
and channel subscriptions are tracked in Redis.

WebSocket is the default pluggable transport and can be selected explicitly
with `TRANSPORT=websocket`.

```bash
python -m pip install -r requirements.txt
REDIS_URL=redis://127.0.0.1:6379/0 DATABASE_URL=sqlite:///data/messages.db \
  python app.py --host 127.0.0.1 --port 8765 --data-dir data
```

Connect to `ws://127.0.0.1:8765`. Messages use this shape:

```json
{"type":"broadcast","payload":{"text":"hello"},"timestamp":"ignored for input"}
```

The server generates authoritative UTC timestamps. `broadcast` and `system`
messages go to every client. A `direct` payload must include the target client's
`client_id`:

```json
{"type":"direct","payload":{"client_id":"...","text":"private"}}
```

Clients can dynamically subscribe to multiple named channels. Subscription
control messages are silent:

```json
{"type":"subscribe","channel":"alerts"}
{"type":"unsubscribe","channel":"alerts"}
```

Adding a top-level `channel` to a `broadcast` or `system` message delivers it
only to subscribers. A channeled `direct` message is delivered only when its
target subscribes to that channel. Messages without a channel retain their
original broadcast or direct behavior.

`GET /health` reports the connected client count. `GET /channels` lists active
channels and subscriber counts, while `GET /channels/{name}/subscribers` lists
the subscriber IDs for a channel. `GET /messages?limit=50&offset=0` returns
persisted messages in insertion order.

`GET /history?channel=alerts&since=2026-01-01T00:00:00Z&limit=50` returns
channel messages in chronological order and includes a `has_more` pagination
flag. Client input is limited to 100 messages per minute with Redis counters.
Set `RATE_LIMIT` to change that limit. Messages older than seven days are
removed by a background cleanup task; set `MESSAGE_TTL_DAYS` to change the
retention period.
