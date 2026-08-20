---
status: accepted
---
# Control Room review — UI + endpoints

Phase 4 (control_room) of `repo_review_fable`. Scope: `admin/server.py` (28 routes),
`admin/static/` (vanilla-JS dashboard), `docs/supervisor_design.md`, and the read-only pull
contract in `scripts/CONTEXT.md:117-128`. This is a delta on the prior Control Room reviews
(`docs/review/code_review.md`, `docs/review/architecture_review.md`, written against a ~367-line
`server.py`); the server has since grown to **1,520 lines / 28 routes** with three new surfaces:
supervisor flags + steer/interrupt, the canonical-state registry board, and Claude background
sessions. All `file:line` re-read at commit `1baff2a6f`.

---

## 1. Verdict: does the flag-only rail hold?

**Holds — at the supervisor, at the tool layer, and at the door — but "flag-only" is a narrower
claim than the name suggests.**

Three distinct layers must be checked separately:

1. **The supervisor's own code path is observe-only (CONFIRMED).** `scripts/supervise.py`'s
   `supervise_once` (`:337`) reads a cell's Redis event stream and `emit_flag` (`:221`) persists
   the verdict to `flags.jsonl` + `supervisor_flags` + (optionally) a KB observation. Neither calls
   `send_input` nor `interrupt`. `src/instrument/supervisor.py` deliberately has no OpenCode client
   dependency (`src/instrument/CONTEXT.md:97`). This is the invariant `docs/supervisor_design.md:5-8`
   states, and it is honored.

2. **No agent-callable tool wraps the POST routes (CONFIRMED).** `scripts/CONTEXT.md:128` is
   explicit: the control-plane agent pulls state via `.opencode/tools/dashboard.ts`
   (`monitor.py --json`) and `.opencode/tools/control_room.ts` (GET-only). The agent's own tool set
   cannot steer or interrupt.

3. **The server is, nevertheless, an actuation surface — but every actuation door is human-gated
   (CONFIRMED, with one outlier — see F1).** Six routes cross from observation into control:
   `POST /api/flags/<sid>/steer` (`admin/server.py:1124`), `/interrupt` (`:1151`),
   `POST /api/design-sessions/<pid>/input` (`:1098`) and `/interrupt` (`:1176`),
   `POST /api/claude-agents/<sid>/steer` (`:1420`), plus claude stop/respawn/rm/daemon-stop. All but
   one (`/api/experiments`, F1) pass through `_design_mutation_body` (`:381-401`) or
   `_claude_agent_mutation_body` (`:468-493`): loopback `remote_addr`, loopback `Host`, same-origin,
   JSON-only, 64 KiB cap, and a required `Idempotency-Key`. The steer/interrupt doors additionally
   revalidate *retained flagged ownership + exact cell mapping* at side-effect time via
   `_authorize_supervisor_action` (`:333-350`), so a stale browser selection cannot act after a
   remap (`:348-349` → 409). This is exactly `docs/supervisor_design.md` §3's boundary.

**The honest caveat:** the mutation boundary is *loopback trust + idempotency key + a
currently-flagged session*, not authentication. The same-host processes being supervised — the
opencode agents run on this machine — can satisfy loopback, mint an `Idempotency-Key`, and omit the
`Origin` header (non-browser clients don't send one, and the check at `:388-390` passes when absent).
The load-bearing gate is therefore `_authorize_supervisor_action`, which an agent could only defeat
by writing a forged `session_id` into `supervisor_flags` and `supervisor_session_cells` on framework
Redis (DB 1, port 6380). That is the *deliberate* design (the server now binds `127.0.0.1` by
default, `admin/server.py:1519` — the prior review's `0.0.0.0` is fixed), but it should be
documented as "trust-on-localhost", not presented as "agents cannot act". **Recommendation:** state
the threat model in one line in `admin/server.py`'s module docstring, and keep the flag/ownership
revalidation as the *only* thing standing between a local process and `send_input` — it currently is,
and that's correct.

---

## 2. Verdict: is the canonical-state board read-only?

**Yes, confirmed.** `GET /api/registry` (`admin/server.py:878-908`) and
`GET /api/registry/<entity_id>` (`:911-937`) are GET-only, read `experiments/data_manifest.json`
(the compacted registry array) directly, and — critically — **never touch Redis or Neo4j** (the
docstrings at `:879-893` and `:918-925` make the file-only design explicit). There is no POST/DELETE
route for the registry anywhere, and `scripts/registry.py` is a read-only CLI (`:6-8`). The UI
mirrors this: the registry is a lazy-loaded drawer (`admin/static/index.html:398-445`) with no write
affordance. The one "actuation" path the registry *could* feed (an actuation record with `causes`
pointing at a justifying observation, `:934-936`) is implemented read-only and has zero producers
today — consistent with `actuation_ingestion` being "built with ZERO call sites"
(`src/instrument/__init__.py:307`).

---

## 3. Endpoint review — what is missing, mislabeled, or fragile

### F1 (HIGH) — `/api/experiments` is the one money-spending route that skips the mutation boundary

- **Location:** `admin/server.py:1003-1023`.
- **What:** `POST /api/experiments` spawns `scripts/enqueue.py` (which builds and queues the ~30-cell
  experiment matrix → **real inference cost**) with `subprocess.run`. It reads `body["action"]` and
  has *no* loopback/Host/Origin/idempotency check — unlike `/api/queue/reinterleave`
  (`:1026-1052`), which is a cheap, reversible reorder and *is* wrapped in `_design_mutation_body()`.
- **Why it matters:** the prior review's C1 fixed only the "defaults to enqueue on empty body" half
  (`:1006-1008` now requires an explicit `action`). The auth half remains: it is the **only**
  mutation route without the trust boundary. Because the default bind is now `127.0.0.1`
  (`:1519`), this is masked today — but the moment an operator sets `FINOPS_HOST=0.0.0.0` to share
  the dashboard (the documented escape hatch, `:1518`), `/api/experiments` becomes a fully open,
  money-spending endpoint while every other mutation route stays loopback/same-origin/idempotency
  gated. This is an inconsistency, not just a missing guard: the *cheapest* mutation is hardened and
  the *most expensive* one is not.
- **Fix:** route `/api/experiments` through `_design_mutation_body()` (drop the `action` allowlist
  duplication in favor of the shared boundary), or at minimum apply the same loopback + `Idempotency-Key`
  checks before the `subprocess.run`.

### F2 (MEDIUM) — route inventory is stale in two places

- **Location:** `admin/server.py:5-19` (module docstring endpoint list) and
  `scripts/CONTEXT.md:117-128` (the "24 routes" table).
- **What:** the docstring lists 19 endpoints and omits `/api/flags`, `/api/flags/<sid>/steer`,
  `/interrupt`, `/api/registry`, `/api/registry/<entity_id>`, `/api/design-sessions/<pid>/spec|save|run`,
  `/api/queue/reinterleave`. `scripts/CONTEXT.md` says "24 API routes across 4 categories" but omits
  `/api/registry`, `/api/registry/<entity_id>`, `/api/queue/reinterleave`, and `GET /` — the actual
  count is **28**. The canonical-state registry routes were added in "round 2, plan step 17"
  (`admin/server.py:878`) without updating either inventory.
- **Fix:** regenerate the docstring list and `scripts/CONTEXT.md`'s table from the actual
  `@app.route` set (there are 28); the four-category split should gain a fifth "registry" category
  and move `/api/queue/reinterleave` out of the unnamed gap.

### F3 (MEDIUM) — the design-session `/input` route trusts the client's `delivery` mode

- **Location:** `admin/server.py:1098-1121` (`delivery=body.get("delivery", "queue")` at `:1118`)
  vs. the flag route's server-fixed `delivery="steer"` at `:1145`.
- **What:** `POST /api/flags/<sid>/steer` fixes `delivery` server-side (the client cannot choose
  queue vs. steer), but `POST /api/design-sessions/<pid>/input` passes `delivery` straight from the
  body. A design-session "Send" can therefore be silently upgraded to a "steer" by the client.
  Design sessions have their own portal-ownership model, so this is not the same vulnerability as a
  flagged session, but the asymmetry between the two "admit a prompt" surfaces is a latent foot-gun
  and contradicts the design's own principle that "the server, not the browser, fixes `delivery`"
  (`docs/supervisor_design.md:128`).
- **Fix:** either fix `delivery="queue"` for the design-session input route (adding a separate
  explicit steer route if needed), or validate `delivery` against an allowlist server-side.

### F4 (LOW) — `/api/registry` re-parses the entire manifest on every request

- **Location:** `admin/server.py:894` (`registry_cli.load_registry(DATA_MANIFEST_PATH)` inside the
  request handler) and again at `:927` for the lineage route.
- **What:** the whole `data_manifest.json` — including every entity's nested `versions` array — is
  read and `json.loads`-ed per request, with no cache. For a registry that grows with the corpus this
  is the same per-request full-file-parse shape the prior review flagged for `/api/matrix` (M1),
  now for a second surface.
- **Fix:** cache the parsed manifest with a small TTL (or key off the file mtime), since the file
  only changes when `generate_manifest.py` runs.

### F5 (LOW) — lineage route assumes single-match without asserting it

- **Location:** `admin/server.py:932` (`record = matches[0]`).
- **What:** compaction guarantees one row per `entity_id`, so `matches[0]` is correct today — but if
  a malformed/duplicate manifest ever yields two rows for one entity, the route silently returns the
  first. No `len(matches) > 1` warning, unlike `scripts/registry.py`'s `resolve_show`, which
  deliberately surfaces ambiguity (`scripts/registry.py:149-154`).
- **Fix:** mirror the CLI's ambiguity handling — return all matches (or a `409`/`ambiguous` marker)
  when `len(matches) > 1`.

---

## 4. UI review

- **The Needs-Attention rail implements the boundary correctly.** `index.html:162-171` renders the
  bounded rail with the always-visible footer "Supervisor flags. You decide." (`:171`), repeated above
  the action controls (`:238`). The steer button is `disabled` unless the flag is `reviewable` with an
  exact `cell_id` (`app.js:520-523`), the interrupt button requires a non-interrupted reviewable flag
  (`:523`), and the interrupt flow is a genuine two-step typed door — `openSupervisorInterruptDoor`
  sends no request, `confirmSupervisorInterrupt` sends `INTERRUPT <session_id>` only after an exact
  client match (`app.js:1709-1740`), with the server independently re-validating the phrase
  (`admin/server.py:1162-1163`). Detach is separate from Interrupt (`index.html:256-257`), matching
  the "Detach never interrupts" acceptance item (`docs/supervisor_design.md:183`). This is a faithful
  rendering of the spec.
- **The registry drawer is read-only but undiscoverable and un-debounced.** The canonical-state board
  is buried behind `#registry-toggle` (`index.html:371`) with no badge or count to signal it exists;
  and each filter change re-fetches the whole table (`app.js:1481-1490`) with no debounce — typing a
  `since` date fires a request per keystroke. Given the F4 full-file-parse cost server-side, this
  compounds. Add a lightweight debounce and a row-count on the toggle.
- **"Reported spend" provenance is still a bare "RETAINED WINDOW".** `index.html:22-25` shows the
  metric and a `RETAINED WINDOW` provenance tag, but `_retained_telemetry` computes `history_capped`
  per cell and globally (`admin/server.py:757, 769`) and the prior review's M2 ("history_capped
  never surfaced, so reported spend silently understates for chatty cells") is still not wired into
  the rail. Confirm and surface `history_capped` (a "±"/footnote when capped) — this is the one
  prior-review MAJOR that appears unaddressed in the current UI.

---

## 5. Observation vs actuation — what to expose now vs. gate

The clean line to draw is: **the Control Room already has an implicit "actuation" class** — the six
`POST` routes that call `send_input`/`interrupt`/the claude CLI. The registry board, matrix, flags,
events, routing, design-session *list/spec*, and claude *roster/logs/daemon status* are observation
and should stay GET-only (they are). The recommendation is to make the implicit split explicit and
keep the observe-only default:

1. **Expose now (observation, unchanged):** every current GET surface, including the registry board
   and lineage view. These are read-only by construction and need no gating.

2. **Already-actuation (keep, but formalize):** the steer/interrupt/control POST routes. They are
   correctly gated by loopback + same-origin + idempotency + ownership/mapping revalidation. The one
   defect is F1 — `/api/experiments` must join them under `_design_mutation_body()`. Consider a
   single `requires_actuation` decorator so the six routes (plus enqueue) share one boundary rather
   than three near-identical `_*_mutation_body()` copies (`admin/server.py:381, 468` — already
   flagged as duplication in the restructure review).

3. **Gate behind a future "actuation type" flag (do not build now):** any *new* control surface —
   fleet pause/resume, budget ceiling enforcement, automatic re-routing, daemon restarts on a timer,
   etc. — should be introduced as a named `actuation_type` that is **OFF by default** and enabled
   only by an explicit env opt-in (mirroring `FINOPS_HOST`). This preserves the observe-only default
   and gives the `_authorize_supervisor_action`-style revalidation a single choke point to extend.

4. **Tie actuation to the registry (the natural next step, already scaffolded):** the canonical-state
   layer has an `actuation_ingestion` producer (`authority=POLICY`, built + tested, **zero call
   sites** — `src/instrument/__init__.py:307`). The Control Room's steer/interrupt handlers are the
   obvious first caller: emit an `actuation` record whose `causes` points at the flag/observation that
   justified the intervention (`admin/server.py:934-936` already renders that one-hop link
   read-only). This makes "why did the system decide to act" auditable end-to-end — the very question
   the observation/actuation split exists to answer — without changing any observe-only default.

---

## 6. Priority

| # | Severity | Location | Change |
|---|---|---|---|
| F1 | HIGH | `admin/server.py:1003` | gate `/api/experiments` under `_design_mutation_body()` |
| F3 | MEDIUM | `admin/server.py:1118` | fix `delivery` server-side / allowlist it on design-session `/input` |
| F2 | MEDIUM | `admin/server.py:5` + `scripts/CONTEXT.md:117` | regenerate the 28-route inventory |
| M2-followup | MEDIUM | `admin/static/app.js` rail | surface `history_capped` on reported spend |
| F4/F5 | LOW | `admin/server.py:894, 932` | cache manifest; assert single-match on lineage |
| — | LOW | `admin/static/app.js:1481` | debounce registry filter fetch; badge the toggle |

**Bottom line:** the flag-only rail and the read-only registry board both hold as shipped. The
outstanding risk is not a violated invariant but an *inconsistent* one — the most expensive mutation
(`/api/experiments`) sits outside the trust boundary that every other actuation route now enforces.
