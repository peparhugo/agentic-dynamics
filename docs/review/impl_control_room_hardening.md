---
status: implemented
implemented_by: feature/control-room-hardening
---
# Implementation trace — Control Room hardening (F1–F5) + actuation tie-in

This document traces each finding in `docs/review/control_room.md` to its concrete fix in the
code, and records the verification result. It is the follow-on to the prior review
(`control_room.md` §6 "Priority") and the two implementation phases:

1. **harden** — F1 + F3 + F2 + F4 + F5 (the mutation boundary, the route inventory, the
   registry endpoints).
2. **record_actuation** — the first actuation call site (§5.4 item 4).

Every `file:line` reference below is against the current working tree.

---

## 1. Verification summary

| Surface | Command | Result |
|---|---|---|
| Server contract tests | `pytest tests/test_admin_server.py -q` | **39 passed** |
| Knowledge-stream tests | `pytest tests/test_knowledge_stream.py -q` | **20 passed** |
| Frontend structural tests | `pytest tests/test_admin_frontend.py -q` | **12 passed** |
| Actuation-producer tests | `pytest tests/test_actuation_ingestion.py -q` | **10 passed** |
| Required gate | `pytest tests/test_admin_server.py tests/test_knowledge_stream.py -q` | **59 passed** |

The required gate from the task (`tests/test_admin_server.py tests/test_knowledge_stream.py`)
passes: **59 passed**.

---

## 2. Finding → fix trace (summary)

| Finding | Severity | Finding location | Fix location | Status |
|---|---|---|---|---|
| F1 — `/api/experiments` skips the mutation boundary | HIGH | `admin/server.py:1003` (then) | `admin/server.py:1126`, `admin/static/app.js:1581` | **PASS** |
| F2 — stale 24-route inventory | MEDIUM | `admin/server.py:5`, `scripts/CONTEXT.md:117` | `admin/server.py:5`, `scripts/CONTEXT.md:117` | **PASS** |
| F3 — design-session `/input` trusts client `delivery` | MEDIUM | `admin/server.py:1118` (then) | `admin/server.py:174`, `admin/server.py:1245` | **PASS** |
| F4 — `/api/registry` re-parses manifest per request | LOW | `admin/server.py:894` (then) | `admin/server.py:886` (`_load_registry_cached`) | **PASS** |
| F5 — lineage assumes single-match | LOW | `admin/server.py:932` (then) | `admin/server.py:1042` (409 `ambiguous`) | **PASS** |
| Actuation tie-in (§5.4) | — | `src/instrument/actuation_ingestion.py` (zero call sites) | `admin/server.py:388`, `:1288`, `:1319` | **PASS** |

---

## 3. F1 — `/api/experiments` joins the shared mutation boundary

**Finding.** `POST /api/experiments` spawned `scripts/enqueue.py` (the ~30-cell matrix → real
inference cost) from a bare `request.get_json` + action check with no loopback / Host /
same-origin / idempotency gate. It was the *only* money-spending mutation outside the trust
boundary that every other actuation route enforces, and the *cheapest* mutation
(`/api/queue/reinterleave`) was hardened while the *most expensive* one was not.

**Fix** (`admin/server.py:1126-1152`, `api_experiments`):
- The handler now calls `_design_mutation_body()` first (loopback `remote_addr` + loopback
  `Host` + same-origin `Origin` + JSON-only + 64 KiB cap + required `Idempotency-Key`), then
  drops the duplicated `action` allowlist in favor of a single `action in ("enqueue", "clear")`
  check, and wraps the `subprocess.run` in `_idempotent_design_response("experiments", …)`.

  *Reasoning:* wrapping in the idempotency response (not just the body gate) preserves the
  retry/replay contract of every other mutation — a doubled enqueue would spend real money
  twice, so the `SET NX` reservation is exactly the guarantee this route needs.
- The frontend `runQueueAction` (`admin/static/app.js:1581`) now sends
  `Idempotency-Key: mutationKey()` so the browser button keeps working against the hardened
  endpoint.

**Tests** (`tests/test_admin_server.py`): `test_experiments_requires_idempotency_key`,
`test_experiments_rejects_non_loopback_remote`, `test_experiments_rejects_unknown_action`,
`test_experiments_enqueue_spawns_subprocess`, `test_experiments_clear_appends_flag`; plus
`test_enqueue_client_sends_idempotency_key` in `tests/test_admin_frontend.py`.

**Result:** PASS — the route is registered, loopback-gated, and reaches the subprocess with the
correct argv only through the boundary.

---

## 4. F2 — regenerate the 28-route inventory

**Finding.** The module docstring listed 19 endpoints; `scripts/CONTEXT.md` claimed "24 API
routes across 4 categories" and omitted `/api/registry`, `/api/registry/<entity_id>`,
`/api/queue/reinterleave`, and `GET /`. The actual `@app.route` set is **28**.

**Fix:**
- Module docstring `admin/server.py:5-39` rewritten to enumerate all 28 routes across 5 API
  categories (legacy telemetry 6, supervisor flags 3, registry 2, design sessions 7, claude
  background sessions 9) plus the static shell (`GET /`).
- `scripts/CONTEXT.md:117-126` regenerated to the same 28-route / 5-category table, moving
  `/api/queue/reinterleave` out of the unnamed gap into "Legacy telemetry" and adding the
  "Registry" and "Static shell" rows.

  *Reasoning:* the five-category split is "the prior four + registry" per the review; the two
  POST queue routes (`/api/experiments`, `/api/queue/reinterleave`) stay in the telemetry/queue
  category, and `GET /` is listed as the static shell because it is not an API route.

**Test** (`tests/test_admin_server.py`): `test_route_inventory_covers_all_registered_routes` —
introspects `server.app.url_map`, asserts **28** non-static Rule objects (GET+POST on a shared
path register two rules, so the assertion counts rules, not deduped path strings), and asserts
membership of the previously-omitted surfaces.

**Result:** PASS — 28 routes, all five categories present, no stale count anywhere (verified no
remaining "24 routes"/"4 categories" string in the tree).

---

## 5. F3 — fix `delivery` server-side on design-session `/input`

**Finding.** `POST /api/design-sessions/<portal_id>/input` passed `delivery` straight from the
body, so a client "Send" could be silently upgraded to a "steer" — asymmetric with the flag
route, whose `delivery="steer"` is fixed server-side.

**Fix** (`admin/server.py`):
- Module constant `DESIGN_DELIVERY_MODES = ("queue", "steer")` (`admin/server.py:174`).
- `api_design_session_input` (`admin/server.py:1245-1252`) now validates the resolved
  `delivery` against that allowlist *before* the idempotency reservation, rejecting anything
  else with `400`.

  *Reasoning:* validating before `_idempotent_design_response` means an invalid request never
  reserves an idempotency key; and the allowlist (rather than hard-coding `"queue"`) keeps the
  legitimate "steer" button working while closing the smuggling path — the server, not the
  browser, now owns the set of admissible modes.

**Tests** (`tests/test_admin_server.py`): `test_design_session_input_rejects_unknown_delivery`,
`test_design_session_input_forwards_allowlisted_delivery`.

**Result:** PASS.

---

## 6. F4 — cache the parsed manifest

**Finding.** `api_registry` and `api_registry_lineage` called
`registry_cli.load_registry(DATA_MANIFEST_PATH)` on every request — a per-request full-file
parse of `data_manifest.json` (including every entity's `versions` array).

**Fix** (`admin/server.py:886-905`, `_load_registry_cached`):
- New helper caches the parsed registry array in `_REGISTRY_CACHE`
  (`admin/server.py:185`), keyed on `(path, mtime_ns, size)`.
- Both `api_registry` (`admin/server.py:1005`) and `api_registry_lineage`
  (`admin/server.py:1038`) call `_load_registry_cached` instead of `load_registry` directly.
- A missing file caches `[]` under `(path, None, None)`; when the file appears its key changes
  and the cache misses.

  *Reasoning:* the manifest is only rewritten by `generate_manifest.py`, so mtime+size is a
  stronger invalidation signal than a wall-clock TTL — there is no stale window between a
  rewrite and a periodic flush, and no per-request parse. The two routes only ever read (never
  mutate) the returned list, so returning the cached list object is safe.

**Tests** (`tests/test_admin_server.py`): `test_api_registry_caches_parsed_manifest` (a second
request does not re-parse), `test_api_registry_cache_invalidates_on_rewrite` (a size change
busts the cache).

**Result:** PASS.

---

## 7. F5 — lineage surfaces ambiguity

**Finding.** `api_registry_lineage` did `record = matches[0]` with no `len(matches) > 1` guard —
a malformed/duplicate manifest would silently return the first row, unlike
`scripts/registry.py`'s `cmd_show` which prints all candidates.

**Fix** (`admin/server.py:1042-1052`):
- When `len(matches) > 1`, the route now returns `409` with
  `{"error": "ambiguous", "entity_id", "count", "records": matches}` (all matches), mirroring
  the CLI's ambiguity handling instead of guessing.

**Test** (`tests/test_admin_server.py`): `test_api_registry_lineage_flags_ambiguity`.

**Result:** PASS.

---

## 8. Actuation tie-in (§5.4 item 4) — the first call site

**Finding.** `actuation_ingestion` was built + tested with **zero call sites**; the review
designated the Control Room's steer/interrupt handlers as the natural first caller: emit an
`actuation` record whose `causes` points at the flag/observation that justified the
intervention, making "why did the system decide to act" auditable end-to-end.

**Fix** (`admin/server.py`):
- `_emit_actuation_record` (`admin/server.py:388-439`) derives the flag's canonical
  `knowledge_id` via `observation_ingestion.derive_flag_record`, builds the `actuation` record
  with `causes = flag_record.knowledge_id` (`authority=POLICY`, `[P]`), and publishes through
  `knowledge_stream.publish_event(..., authorized=True, armed=True, source_type="actuation")`.
  The whole emit is wrapped in `try/except` — **best-effort by construction**: a DB-2 KB outage
  can never block the steer/interrupt that already succeeded.
- `api_supervisor_steer` (`admin/server.py:1288`) emits `actuation_kind="steer"` with
  `requested_action={"prompt": …}` after `send_input` succeeds; `api_supervisor_interrupt`
  (`admin/server.py:1319`) emits `actuation_kind="interrupt"` after `interrupt` succeeds. Both
  live inside the idempotency action, so a replayed request emits exactly once.

  *Reasoning:* `authorized=True`/`armed=True` are passed as explicit keyword args rather than
  mutating the `FINOPS_KB_WRITE` / `FINOPS_ACTUATION_ARMED` env flags, which would race across
  Flask's `threaded=True` request handlers. The human operator's explicit POST is itself the
  authorization/arming signal.

**Invariant update.** `tests/test_actuation_ingestion.py::test_no_call_sites_construct_actuation_records`
now treats `admin/server.py`'s steer/interrupt as the *sole legitimate* call site (it was
removed from the guarded list) while keeping `scripts/supervise.py` and
`src/instrument/workflow_runner.py` guarded; the `actuation_ingestion.py` module docstring was
updated to state the same.

**Tests** (`tests/test_admin_server.py`): `test_supervisor_steer_emits_exactly_one_actuation_record`
(end-to-end: exactly one publish, `causes == derive_flag_record(flag).knowledge_id`,
`source_type="actuation"`, `armed=True`, `authorized=True`),
`test_supervisor_interrupt_emits_exactly_one_actuation_record`,
`test_actuation_emit_is_best_effort_and_never_blocks_the_steer` (KB down → steer still 200),
`test_get_only_paths_never_emit_actuation` (flags/registry/matrix GETs emit nothing).

**Result:** PASS.

---

## 9. Full test result (as of this write-up)

```
$ pytest tests/test_admin_server.py tests/test_knowledge_stream.py -q
.......................................................              [100%]
59 passed
```

Broader surrounding suite (admin + actuation + observation + knowledge):

```
$ pytest tests/test_admin_server.py tests/test_admin_frontend.py \
    tests/test_admin_claude_agents.py tests/test_admin_claude_agents_frontend.py \
    tests/test_admin_design_sessions.py tests/test_admin_supervisor.py \
    tests/test_actuation_ingestion.py tests/test_observation_ingestion.py \
    tests/test_knowledge_ingestion.py tests/test_knowledge_stream.py -q
204 passed
```

---

## 10. Bottom line

All six findings are fixed and verified. The two load-bearing invariants the review cared about
still hold, now consistent across the surface:

- Every mutation route — including the most expensive one — passes through the same loopback /
  same-origin / JSON / size-cap / `Idempotency-Key` boundary.
- The observation/actuation split is now *explicit* in code: steer/interrupt emit a
  `POLICY`-authority actuation record citing the flag observation that justified them, while
  the flag-only supervisor and workflow runner remain call-site-free.
