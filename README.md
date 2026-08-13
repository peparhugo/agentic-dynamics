# WebSocket Notification Server

Install dependencies and start the server:

```bash
python3 -m pip install -r requirements.txt
REDIS_URL=redis://127.0.0.1:6379/0 DATABASE_URL=sqlite:///messages.db \
  python3 app.py --host 127.0.0.1 --port 8765
```

Connect WebSocket clients to `ws://127.0.0.1:8765`. On connection, each client
receives a `system` message containing its unique `client_id`. Send a
`broadcast` message to reach every client, or a `direct` message with a
`target_id` in its payload to reach one client. Clients can dynamically join or
leave channels with `subscribe` and `unsubscribe` messages:

```json
{"type":"subscribe","channel":"alerts"}
{"type":"unsubscribe","channel":"alerts"}
```

Add a top-level `channel` to a `broadcast`, `system`, or `direct` message to
restrict its delivery to subscribers of that channel. Messages without a
channel retain their original delivery behavior. A direct message with a
channel is delivered only when its target is subscribed.

`GET /health` returns the current connected client count. `GET /channels`
returns active channels and subscriber counts, and
`GET /channels/{name}/subscribers` returns the channel's subscriber IDs.
`GET /messages?limit=50&offset=0` returns persisted messages, newest first.
`GET /history?channel=alerts&since=2026-08-13T12:00:00Z&limit=50` returns
channel messages in chronological order with a `has_more` pagination flag.

When `REDIS_URL` is set, each server publishes messages to Redis and runs a
subscription worker that delivers them to its local WebSocket clients. This
allows any number of server instances to share message delivery and connection
metadata. `DATABASE_URL` selects the SQLite history database and defaults to an
in-memory database; use an absolute URL such as `sqlite:////var/lib/app/messages.db`
or a relative URL such as `sqlite:///messages.db` for durable history.
Each client may send 100 messages per minute by default. Redis counters enforce
the limit across server instances, and over-limit clients receive a `system`
error response. Set `RATE_LIMIT` to change the limit. Message history older
than seven days is removed by a startup background task; set `MESSAGE_TTL_DAYS`
to change the retention period.

Every outgoing message has this shape:

```json
{"type":"broadcast","payload":{"text":"hello"},"timestamp":"2026-08-13T12:00:00Z"}
```
