# WebSocket Notification Server

Install dependencies and start the server:

```bash
python3 -m pip install -r requirements.txt
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

Every outgoing message has this shape:

```json
{"type":"broadcast","payload":{"text":"hello"},"timestamp":"2026-08-13T12:00:00Z"}
```
