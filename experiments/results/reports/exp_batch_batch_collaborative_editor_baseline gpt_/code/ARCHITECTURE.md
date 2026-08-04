# Relay collaborative editor architecture

## Data flow

The browser owns one `Y.Doc` per open document. Tiptap/ProseMirror renders the shared `XmlFragment`; Yjs merges concurrent updates deterministically without a central operation order. `WebsocketProvider` broadcasts binary updates and awareness messages, while `IndexeddbPersistence` stores the same update log locally. After reconnect, state vectors ensure that only missing updates move in either direction.

Awareness is deliberately ephemeral. Names, colors, selections, and cursors are not written into document history. The collaboration cursor extension maps selections through document changes and expires disconnected peers.

## Undo and comments

Tiptap's local history is disabled. The collaboration extension uses a Yjs `UndoManager`, scoped to the local client origin, so undo reverses the current user's last edit without reverting a collaborator's interleaved changes. Undo itself is another CRDT operation and is therefore synchronized.

Comments live in a shared `Y.Array`. Their range endpoints are encoded `Y.RelativePosition` values rather than character offsets, so anchors survive concurrent insertions and deletions. Resolution is a synchronized map update. Production deployments can move comment bodies to a service while retaining these relative anchors in Yjs if audit or access-control policy requires it.

## Persistence and versions

IndexedDB is the offline write-ahead store, not the system of record. The websocket service persists Yjs updates and periodically compacts them into snapshots. The version REST API lists immutable, server-created checkpoints and restores one by applying its snapshot as a new update; history is never destructively rewritten.

Suggested backend boundaries:

- Collaboration gateway: authenticates document access, relays Yjs updates, rate limits awareness, and fans out over a pub/sub layer.
- Update store: append-only update stream plus compacted snapshots, partitioned by document ID.
- Version service: immutable named/automatic snapshots and restore authorization.
- Document API: metadata, sharing policy, export, and search indexing.

## Scaling and failure handling

Gateways remain stateless after subscription and can scale horizontally. Document channels are distributed by consistent hashing or Redis/NATS pub/sub. Snapshot compaction occurs asynchronously. Clients reject no local keystrokes while offline; websocket exponential reconnect is handled by `y-websocket`, and Yjs state-vector exchange deduplicates replayed updates.

Access tokens should be supplied in the websocket provider parameters, refreshed outside the CRDT layer, and rechecked on reconnect. Server-side limits should cover update size, document size, awareness frequency, and inactive sessions. Version and comment mutations require the same document ACL as realtime connections.

## Frontend module boundaries

- `collaboration/session.ts`: lifecycle for CRDT, transport, awareness, and offline storage.
- `collaboration/comments.ts`: relative anchors and synchronized comment transactions.
- `hooks/useCollaborativeEditor.ts`: editor schema/extensions and CRDT bindings.
- `hooks/useSessionState.ts`: React projection of provider and shared-type events.
- `api/versions.ts`: replaceable HTTP boundary for immutable snapshots.
- `components/*`: presentation and user actions; no transport ownership.
