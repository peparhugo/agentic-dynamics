---
status: accepted
---
# Workflow Cell Publishing & Rendering — Phase Badge Survey

**Scope:** map where a workflow cell's live status is published and rendered, and pin
the exact touchpoint for adding a live-phase badge (phase `name` + `index/total`).
**Read-only survey** — no code was modified. Line references are to the current tree.

---

## TL;DR

1. `run_workflow()` (`src/instrument/workflow_runner.py`) is the sole publisher of
   *phase* telemetry. It owns its own cell id `wf_<spec>_<model>` and already emits one
   `step_finish` event per phase — but the phase name is only embedded in the event's
   free-text (`"phase {name} {status}"`), with **no `index`/`total` anywhere**.
2. The phase badge has a **dual-identity wrinkle** (see §4): a Control Room–launched
   workflow produces *two* cells — `workflow_<uuid>` (launch envelope) and
   `wf_<spec>_<model>` (the engine cell where the phase events actually land).
3. No new Redis key is required: the existing `step_finish` event already flows through
   the per-cell event channel **and** the retained `events_log:<cell>` list. The badge
   needs (a) a `phase` object on that event, (b) that object surfaced in the `/api/matrix`
   telemetry samples, and (c) a `<span>` in the fleet card.

---

## 1. Where workflow cell status is published

### 1.1 The engine cell — `wf_<spec>_<model>`

| Touchpoint | file:line | What happens |
|---|---|---|
| cell id derivation | `src/instrument/workflow_runner.py:460-462` | `_cell_id(spec_name, model)` → slug `f"wf_{spec}_{model}"` (alnum, lower) |
| publisher construction | `src/instrument/workflow_runner.py:558-559` | `cell_id = _cell_id(...)`; `publisher = LivePublisher(cell_id) if publish else None` |
| run start | `src/instrument/workflow_runner.py:560-565` | `set_status("running")` + one `text` event `"workflow {spec.name} — {goal[:120]}"` |
| agent session reroute | `src/instrument/workflow_runner.py:618-619` | sets `os.environ["FINOPS_CELL_ID"] = cell_id` so the agent's *own* publisher streams into the same `wf_` cell (restored in `finally`, :688-692) |
| **per-phase event** | `src/instrument/workflow_runner.py:730-744` | `publish_event({"type":"step_finish","sessionID":cell_id,"part":{text:"phase {name} {status}", tokens:{…}, cost:…}})` — the **only** place phase identity is currently published |
| run end | `src/instrument/workflow_runner.py:751-752` | `set_status("done" if result.ok else "failed")` |

The `run_workflow` CLI (`scripts/run_workflow.py:87-100`) does not touch Redis itself; it
delegates to `run_workflow()`, whose `publish` defaults to `True`.

### 1.2 The launch envelope — `workflow_<uuid>` (Control Room–launched runs only)

When a workflow is launched from the portal (not from the CLI directly):

| Touchpoint | file:line | What happens |
|---|---|---|
| execution id | `admin/design_sessions.py:699` | `execution_id = f"workflow_{uuid.uuid4().hex[:12]}"` |
| enqueue marker | `admin/design_sessions.py:723-725` | `hset(STATUS_KEY, execution_id, "queued")` + publish `status` |
| spawn | `admin/design_sessions.py:726-732` | daemon thread → `_run_process(execution_id, [python, scripts/run_workflow.py, …])` |
| running marker | `admin/design_sessions.py:754-760` | `status("running")`; sets `FINOPS_CELL_ID = execution_id` in the subprocess env |
| stdout relay | `admin/design_sessions.py:775-776` | each CLI stdout line re-published as a `text` event to `events:<execution_id>` |
| done/failed | `admin/design_sessions.py:780-788` | parses the trailing JSON, then `status("done"/"failed")` |

---

## 2. Where it is rendered in the Control Room

| Touchpoint | file:line | What it does |
|---|---|---|
| fleet snapshot | `admin/server.py:745-783` (`GET /api/matrix`) | reads `story_status` hash → `cells` map; appends `telemetry` from `_retained_telemetry` |
| status stream | `admin/server.py:786-809` (`GET /api/status`) | SSE over the `status` channel |
| per-cell stream | `admin/server.py:824-864` (`GET /api/events/<cell_id>`) | replays `events_log:<cell_id>` then subscribes `events:<cell_id>` |
| step parser (server) | `admin/server.py:596-659` (`_step_sample`) | turns a raw `step_finish` payload into a telemetry sample (identity, cost, tokens) |
| retained aggregation | `admin/server.py:662-742` (`_retained_telemetry`) | reads every `events_log:<cell_id>` list, builds `telemetry.cells[cell_id] = {samples, reported_cost, input_tokens, output_tokens, latest_cost, …}` |
| fleet cards | `admin/static/app.js:292-364` (`renderFleet`) | renders one card per cell; **cell id `<span>` at `app.js:335`** — the natural badge slot |
| step parser (browser) | `admin/static/control-room-core.js:71-123` (`extractSample`) | same `step_finish` parsing for the live/burn-rate overlay |
| transcript rows | `admin/static/control-room-core.js:199-209` | renders the `step_finish` row (`STEP` label + token/cost text) |

`renderFleet` currently draws: status word + `SELECTED` label (`app.js:330-334`), the raw
cell id (`app.js:335`), latest reported cost (`app.js:339`), and a sparkline (`app.js:340`).
A phase badge would be appended to the card button between `:335` and `:339`, reading the
phase of the newest telemetry sample.

---

## 3. Exact Redis keys (transport inventory)

All keys live on the framework queue instance `FINOPS_REDIS_HOST:6380`, `FINOPS_REDIS_DB=1`
(`src/instrument/live.py:20-22`):

| Constant | Value | Kind | `file:line` |
|---|---|---|---|
| `STATUS_KEY` | `story_status` | hash `cell_id → status` | `live.py:23` |
| `STATUS_CHANNEL` | `status` | pub/sub channel | `live.py:24` |
| `EVENT_CHANNEL_PREFIX` | `events:` | pub/sub channel `events:<cell_id>` | `live.py:25` |
| `EVENT_LOG_PREFIX` | `events_log:` | list (bounded 500, newest-first) | `live.py:26` / `live.py:121-122` |

Write paths in `LivePublisher`:
- `set_status` (`live.py:81-93`) → `HSET story_status <cell_id> <status>` + `PUBLISH status`.
- `publish_event` (`live.py:95-125`) → `LPUSH events_log:<cell_id>` + `LTRIM … 0 499` + `PUBLISH events:<cell_id>`.

### Recommended key for the live phase (name + index/total)

**Add the phase to the existing `step_finish` event — no new Redis key.**

The event published at `workflow_runner.py:732-744` already carries the phase name in
free text; add a structured field to its `part`:

```json
{
  "type": "step_finish",
  "sessionID": "wf_<spec>_<model>",
  "part": {
    "text": "phase implement ok",
    "phase": { "name": "implement", "index": 3, "total": 4 },
    "tokens": { "input": …, "output": …, "reasoning": …, "total": … },
    "cost": 0.001
  }
}
```

This rides the two existing pipes (`events:<cell>` live stream **and** the retained
`events_log:<cell>` list), so the badge survives replay and works for both live and
already-running cells. The retained list is what `_retained_telemetry` reads to build the
matrix — so the phase reaches `/api/matrix` without a new hash.

*(Alternative, if phase must live in the status hash rather than the event stream: mirror
`story_status` with a new hash `story_phase` (`cell_id → {"name","index","total"}`), set
via a `LivePublisher.set_phase(...)` sibling to `set_status`. This is more work and splits
phase from the events that already flow; not recommended.)*

### Implementation touchpoints (for the follow-up change)

1. **Produce** — `workflow_runner.py:598-602`: iterate with an absolute index (`total = len(phases)`; `index` = original position, unaffected by `resume`'s `start_idx`). At `workflow_runner.py:732-744`, add `"phase": {"name": name, "index": <abs_index>, "total": total}` to `part`.
2. **Surface** — `admin/server.py:596-659` (`_step_sample`): read `part.phase` (guard non-dict) and include it in the returned sample dict; `_retained_telemetry` (`:662-742`) already forwards `samples`, so add a `latest_phase` shortcut on `cells[cell_id]` from the newest sample.
3. **Render** — `admin/static/control-room-core.js:72-123` (`extractSample`): carry `phase` through the browser-side sample; `admin/static/app.js:292-364` (`renderFleet`): append a badge `<span>` after `:335` reading the newest sample's `phase` (`implement 3/4`).

---

## 4. Dual-identity note (must resolve before wiring the badge)

A Control Room–launched run currently surfaces under **two** cells:

- `workflow_<uuid>` — set by `design_sessions.run_workflow` (`admin/design_sessions.py:699,724`),
  driven by `FINOPS_CELL_ID` (`:760`). Shows `queued → running → done/failed` plus stdout text.
- `wf_<spec>_<model>` — set by `run_workflow`'s own `_cell_id` (`workflow_runner.py:558`),
  which **ignores** the inherited `FINOPS_CELL_ID` (it constructs `LivePublisher(cell_id)` with
  an explicit id). This is where the `step_finish` phase events land.

Consequence: today the phase events appear on `wf_*` while the operator who pressed "Run
workflow" is pointed at `workflow_*` (`app.js:1822`: "select it in Fleet to watch the run").
To put the badge on the cell the operator actually watches, either (a) have `run_workflow`
**adopt** `FINOPS_CELL_ID` when set (fall back to `_cell_id` only when unset), or (b) render
the badge on the `wf_*` cell and reconcile the two identities in the portal. This decision
should be made before/with the badge work — it is the one non-mechanical step.

---

## 5. Test coverage for workflow publishing

| Test file | Covers | Does **not** cover |
|---|---|---|
| `tests/test_workflow_runner.py` | phase order, per-phase commit, resume, RAG ordering/provenance (`:47-156`, `:192-397`) | **publishing** — no assertion on `LivePublisher`, `publish_event`, `step_finish`, `story_status`, or phase index/total (no Redis in CI → the publisher self-disables, so the path is silently untested) |
| `tests/test_live.py` | `LivePublisher` mechanics: status hash+channel (`:48-60`), history log (`:63-74`), persist-before-publish ordering (`:77-99`), disable-after-failure (`:102-116`) | workflow-phase *content* (it publishes generic `text`/`tool_use` events) |
| `tests/test_admin_design_sessions.py:387` | the launch envelope: `story_status[execution_id] == "queued"` | the engine cell `wf_*` and its phase events |
| `tests/test_admin_server.py` | `/api/matrix` + `story_status` fixture (`:49`), `step_finish` fixtures (`:138-140`), status SSE boundary (`:235`), queue cells (`:306-308`) | phase fields on `step_finish` samples |
| `tests/test_admin_supervisor.py` | session→cell mappings with `wf_a` cells (`:103-216`) | phase publishing |
| `tests/test_ledger_fields.py:31-63` | `step_finish` token/cost shapes | phase fields |

**Gap to fill with the change:** extend `test_workflow_runner.py` with a
`FakePublisher`/`FakeRedis` (as in `tests/test_claude_agents_supervisor.py:54-75`) asserting
that each phase emits a `step_finish` whose `part.phase == {"name", "index", "total"}` and
that `set_status` transitions to `done`/`failed`; extend `tests/test_admin_server.py`'s
`_step_sample` fixtures to assert the `phase` object survives into the matrix sample.
