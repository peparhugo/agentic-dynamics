---
status: accepted
---

# Control Room Live Board Audit

**Date:** 2026-09-01
**Scope:** the phases board's full data path — `story_phase` hash (db1/6380), the
`_parse_phases` consumer, the `/api/matrix` + `/api/status` payloads, the app.js board
rendering, and the runner's live telemetry (`set_status` / `set_phase` / `publish_event`)
— audited for a liveness signal that could distinguish LIVE runs from history.
**Change policy:** audit only. No implementation files were changed in this phase.

## Result

**LOG: PASS — audit completed; liveness-signal inventory produced; the board has no
liveness dimension today, and the events-log tail is the one consumable signal.**

The phases board is cumulative and undated end-to-end. The `story_phase` hash carries
only the phase payload `{name, index, total}` with no published-at timestamp and no TTL;
the `_parse_phases` consumer forwards exactly those three fields; `/api/matrix` serves
them as-is; and the app.js board draws a phase badge on every fleet card regardless of
lifecycle status, with no age, no LIVE NOW section, and no live/all filter. A dead
process whose last `set_phase` succeeded renders identically to a live run — `running`
status frozen in the status hash (no TTL), the last phase badge shown, no age anywhere.

One usable-but-partial liveness signal exists and is currently unread for this purpose:
the `events_log:{cell_id}` tail. Of 136,028 retained events across 565 logs, 90,013
carry a top-level `timestamp` (ms epoch) — these are the raw opencode session events
(`adapters/opencode.py` publishes each session line verbatim). The tail entry of an
opencode cell is therefore a last-activity time. It is NOT a clean signal: claude-cell
events and the runner's own boundary events carry no timestamp, an event-free phase
(test/checkpoint) freezes the tail mid-run, and the field is only exposed today inside
`_step_sample` cost aggregation, never surfaced for liveness.

**LIVE_CHECK: PASS (read-only).** The running Control Room at `100.83.229.3:8001`
served `/api/matrix` live: 269 phase entries, every one `{name, index, total}` with no
timestamp/age/live field; execute-stage `running=3`; `telemetry.available=true`. The
default loopback `:8000` listener is not the Control Room (empty/opaque response), the
same finding as the 2026-09-01 usage-wiring audit.

## Chain Audit

| Stage | Evidence | Assessment |
|---|---|---|
| Writer — `story_phase` | `src/agentic_dynamics/control/live.py:26` (`PHASE_KEY="story_phase"`), `:98-111` (`set_phase` — `hset(cell_id, json.dumps(phase))`, no timestamp, no TTL). Callers: `workflow_runner.py:2789` (per-phase start, `{name, index, total}`), `:2775` (full-count hints for `--only-phase`). | Writes the payload ONLY. No published-at, no server clock, no expiry. |
| Consumer — `_parse_phases` | `apps/control_room/services/telemetry.py:206-226` | Decodes `name`/`index`/`total`; drops entries without a `name`; a timestamp in the stored JSON would be discarded even if one were added. |
| API — `/api/matrix` | `apps/control_room/routes/telemetry.py:72` (`hgetall(PHASE_KEY)`), `:90` (`"phases": _parse_phases(...)`); `:80-89` legacy flat fields + `:92` `stages`. | `phases: {cell_id: {name,index,total}}`. No `live`, no `last_phase_ts`, no `age_seconds`. |
| API — `/api/status` (SSE) | `routes/telemetry.py:107-130` subscribes `STATUS_CHANNEL` and forwards raw pub/sub payloads; payload written as `{"cell_id", "status"}` (`live.py:80,94`; `worker.py:388,473`; `workflow_runner.py:3170`). | Transitions only. No timestamp, no phase, ephemeral (pub/sub — nothing to poll). |
| API — `/api/events/<cell_id>` (SSE) | `routes/telemetry.py:133-172` — replay of `events_log:{cell_id}` (bounded 500, `live.py:139-140`) then the live channel. | Carries the timestamped opencode events (see below) but is only connected by the selected-cell inspector (`app.js:1634-1657`), never by the board. |
| Event writer — `publish_event` | `live.py:113-143` — `lpush` + `ltrim(0,499)` + `publish`. Raw opencode session lines forwarded verbatim by `adapters/opencode.py:421`; claude-translated events by `adapters/claude_adapter.py:389`; runner-authored boundary events by `workflow_runner.py:2681` (start text), `:3104` (phase `step_finish`), `:3155` (checkpoint). | Retains a bounded tail per cell. Raw opencode lines carry top-level `timestamp`; claude-translated and runner-authored events carry none. |
| Status writer — `story_status` | `live.py:84-96` (`set_status`), `worker.py:386-388` (`running` at spawn; terminal transitions only on normal completion `:464-479,493,516,523`), `workflow_runner.py:2680/2750/3170`, `supervise.py:210`, `claude_agents_supervisor.py:205`. | Plain status string, no timestamp, no TTL. A killed/crashed worker never flips `running`. |
| Execute-stage cells | `src/agentic_dynamics/control/pipeline_status.py:57,72` — `cells = hgetall(status_key)`. | The board's cell set IS the cumulative status hash; nothing expires or ages it. |
| Rendering — app.js | `app.js:1927` (`state.phases` from `/api/matrix`), `:467-473` (`phaseLabel` → "2/2 test"), `:451-452` (badge hidden only when no phase — shown for done/failed cells too), `:66` (`filter:"all"`), `:2929-2933` (chips), `board-fleet.js:100-107` (all/running/risk). | The "phases list" is the per-card badge on the fleet grid. No age, no live section, no live filter. |
| Durable run ledger (not in the board path) | `experiments/results/workflows/<spec>/*.json` — `started_at`/`ended_at`/state. | A history source, but the board reads Redis only; never consulted for liveness. |

## Answers

**(a) Do the phase entries carry timestamps (published-at) or only the phase payload?**

Only the phase payload. Every entry is exactly `{"name": ..., "index": ..., "total": ...}`
written by `LivePublisher.set_phase` (`control/live.py:98-111`) with no timestamp field
and no TTL on the key. Live-verified against db1/6380: 269 entries, all three-field, key
TTL `-1`; and the running portal's `/api/matrix` served all 269 with no ts/age/live field.
The consumer (`_parse_phases`, `services/telemetry.py:206-226`) extracts only those three
fields, so even a stored timestamp would not survive the parse.

**(b) Does the runner's live telemetry (`set_status` / `publish_event`) leave anything the
board could consume for liveness?**

Three surfaces, one usable:

| Runner surface | What it leaves | Usable for liveness? |
|---|---|---|
| `story_status` hash (`set_status`) | cell_id → status string | **No.** No time, no TTL; `running` persists forever after a crash. |
| `story_phase` hash (`set_phase`) | cell_id → `{name,index,total}` | **No.** No published-at; no TTL. |
| `events_log:{cell_id}` (`publish_event`) | bounded 500-entry tail | **Partial — the one usable signal.** 90,013/136,028 retained events carry a top-level `timestamp` (ms epoch); the newest retained event per cell is a last-activity proxy. Caveats: (i) claude-translated events and the runner's own boundary events are untimestamped — 186/565 logs have zero timestamped events; (ii) an event-free phase (test/checkpoint, `run_suite`) freezes the tail mid-run while the run is still alive; (iii) the timestamp is currently read only inside `_step_sample` (`services/telemetry.py:44-51,101`) and never surfaced. |
| `/api/status` + `/api/events/<id>` SSE | live-only transitions / replay+live | **No for the board.** Ephemeral pub/sub (plus bounded replay) — not pollable for liveness; the status payload has no timestamp. |

**(c) What does a dead-run-with-fresh-phase look like today?**

Indistinguishable from a live run. A worker that dies after its last `set_phase` leaves:
`story_status[cell] = "running"` frozen (the worker only flips to `done`/`failed`/`timeout`
on a normal completion path — `worker.py:386-388` vs `:472-523`), `story_phase[cell] =
{name, index, total}` from the last phase start, and `events_log:{cell}` frozen. The board
renders a RUNNING card with a phase badge, sorts it first (`core.sortCellIds`), counts it
in the stage's `running`, and keeps it under the running filter — forever. Historical
finished cells retain their phase badge too (badge is shown whenever a phase exists,
regardless of status — `app.js:451-452`), so the 269-entry wall is badge-identical to the
live runs.

Live example at audit time (2026-09-01): three cells were `running`. The genuinely-live
`wf_control_room_live_board_deepseek_deepseek_v4_flash` ("1/2 p1_board_audit", last event
0.0 min ago) and the `wf_test_suite_speed_deepseek_deepseek_v4_flash` ("1/4
p1_profile_triage", 1.8 min ago) render exactly like `wf_retrieval_activation_augment_proof_deepseek_deepseek_v4_flash`
("2/2 test", last event 6.4 min ago) — which could be a stalled/dead cell or a live
event-free test phase. Nothing on the card says which.

## Gap Table

| Surface | Liveness signal available | Gap |
|---|---|---|
| `story_phase` hash | None in the payload (`{name,index,total}` only) | No published-at timestamp; no TTL — a phase published last week is byte-identical to one published now. |
| `_parse_phases` consumer | Reads only `name`/`index`/`total` | Would discard a timestamp even if the hash carried one; no age/liveness derivation. |
| `/api/matrix` `phases` block | None surfaced | Serves the undated three-field shape; no `live`/`last_phase_ts`/`age_seconds` per run. |
| `/api/status` SSE | Live transitions only (pub/sub) | Ephemeral, not pollable; payload `{cell_id, status}` carries no time; the board uses it only for transient status overrides (`app.js:2018-2030`). |
| `events_log:{cell_id}` tail | Tail-event `timestamp` on opencode cells (90,013/136,028 retained events; 379/565 logs have at least one) | Not read for liveness; 186/565 logs have zero timestamped events (claude cells, runner-only cells); event-free phases freeze the tail mid-run; not aggregated for the board. |
| `/api/events/<cell_id>` SSE | Full timestamped replay | Only the selected-cell inspector connects; the board never consumes it. |
| `story_status` hash | None (plain string) | No time, no TTL; a crashed worker leaves `running` forever — the board cannot tell "started minutes ago and died" from "actively running". |
| app.js board | Phase badge per card | Shown regardless of status; no age, no LIVE NOW section, no live/all filter; chips are all/running/risk only (`board-fleet.js:100-107`). |
| Workflow run ledger (durable) | `started_at`/`ended_at`/state | Board reads Redis only; the ledger is never consulted for liveness. |

## Liveness-Signal Inventory (the p1 deliverable)

Measured against live db1/6380 (framework Redis, port 6380) on 2026-09-01:

| Signal | Exists? | Freshness | Consumers today | Verdict |
|---|---|---|---|---|
| `story_phase` entry timestamp | **No** — payload is `{name,index,total}` only | n/a | badge only | **ABSENT** |
| `story_phase` key TTL | **No** — TTL `-1` | n/a | none | **ABSENT** |
| `story_status` value timestamp | **No** — plain string | n/a | lifecycle word | **ABSENT** |
| `story_status` key TTL | **No** — TTL `-1` | n/a | none | **ABSENT** |
| `events_log:{cell_id}` tail timestamp | **Yes (partial)** — 90,013/136,028 retained events; 379/565 logs; story cells 500/500, opencode workflow cells ~464/500, claude cells 0/206 | newest retained event | cost sampling only | **USABLE WITH CAVEATS** |
| `/api/status` SSE | live transitions | real-time | status overrides | **NOT POLLABLE** |
| `/api/events/<id>` SSE | replay + live | real-time | selected-cell inspector | **NOT BOARD-CONSUMED** |
| Workflow ledger `started_at`/`ended_at`/state | durable files | post-run | spec index | **NOT IN BOARD PATH** |

## Live Verification Record

Read-only requests; nothing was started, restarted, or steered.

| Request | Observed result |
|---|---|
| `GET http://100.83.229.3:8001/api/matrix` | 200 — 269 `phases` entries, all `{name,index,total}`; none with ts/age/live; `running=3`; `telemetry.available=true`. |
| `GET http://127.0.0.1:8000/api/matrix` | Empty/opaque response — not the Control Room (same finding as the usage-wiring audit). |
| `HGETALL story_phase` (db1/6380, python) | 269 entries, all three-field; key TTL `-1`. |
| `HGETALL story_status` (db1/6380) | 66 entries, plain status strings (incl. long-complete story cells); key TTL `-1`. |
| `LRANGE events_log:*` sample + full scan (db1/6380) | 565 keys; 136,028 events; 90,013 with top-level `timestamp`; 379 keys with ≥1 timestamped event. |

## Completion Handoff

p2 (the implementation phase) should infer LIVE from the existing telemetry per hard rule
1 — the natural source is the `events_log:{cell_id}` tail timestamp as `last_phase_ts`,
because it is the only field in the board's Redis path that carries time, and it is
already retained and already parsed by `_event_timestamp`. The three caveats must become
explicit states, not silent gaps: claude cells and runner-boundary cells yield
`age-unknown` (graceful per hard rule 2); an event-free phase (test/checkpoint) can freeze
a live run's tail, so the window must tolerate that (the 10-minute window already
overlaps the event-free test-phase shape at this repo's scales); and a dead run keeps a
fresh-looking phase until the window passes — which is the designed "stalled run leaves
LIVE NOW and shows its age" behavior (hard rule 3). Add the live/all filter + LIVE NOW
section per the spec, and test the four states (fresh-phase live / old-phase historical /
no-timestamp age-unknown / filter) in `tests/test_admin_frontend.py` +
`tests/test_admin_server.py`.

## p2 Implementation Verification (2026-09-01)

**LOG: PASS — the live dimension is implemented and verified; committed on the
`control_room_live_board` workflow. The window, never the publishing process, decides
liveness.**

The handoff's design is implemented with one deliberate strengthening: `LivePublisher.set_phase`
now stamps every phase write with `published_at` (`src/agentic_dynamics/control/live.py:104`,
stamp at `:34`), so "a phase published within the live window" is literal for every new write;
the events-log tail remains the fallback (`services/telemetry.py:_tail_stamps`) for legacy
phases and is the "runner's live telemetry" signal. `_parse_phases` takes the newer of the two
(phase stamp OR telemetry tail) as `last_phase_ts`, so a stale-stamped run whose telemetry is
still fresh stays LIVE, and a run with neither renders `age-unknown`.

| Spec item | Implementation | Tests | Result |
|---|---|---|---|
| (a) API marks each run `{live, last_phase_ts, age_seconds}`; age-unknown when no timestamp | `_parse_phases(payloads, *, tails, now)` (`services/telemetry.py:293`) — `live = ts exists AND age <= LIVE_WINDOW_SECONDS` (600s, `:24`); `age_seconds = max(0, floor(now − last_dt))`; route wires `_tail_stamps` (`routes/telemetry.py:88`, one pipelined head read per phase cell) | `test_matrix_marks_fresh_phase_live`, `test_matrix_marks_old_phase_historical_with_age`, `test_matrix_marks_no_timestamp_run_historical_age_unknown`, `test_matrix_runner_telemetry_tail_dates_an_unstamped_phase`, `test_matrix_liveness_uses_the_newer_of_phase_and_telemetry`, `test_matrix_marks_exactly_the_window_says`, `test_matrix_phase_from_dead_process_not_live_past_window` | PASS |
| (b) LIVE NOW section above the board (live runs, newest first, i-of-N + age) + live/all filter; historical section = current list with ages | `#live-now` section above `#fleet-controls` (`index.html`), `renderLiveNow`/`liveNowRows`/`phaseBadgeLabel` (`app.js`) over `fleet.livePhaseEntries` (newest-first, `board-fleet.js`), `data-filter="live"` chip feeding `facet.liveIds` into `matchesFacet`; card badges carry `· <age>` | `test_live_now_section_mounted_above_the_full_board`, `test_client_renders_live_now_from_the_api_live_dimension`, `test_board_fleet_handles_live_filter_and_orders_live_newest_first`, `test_live_now_styles_are_present` | PASS |
| (c) Stalled-run rule: past the window a run leaves LIVE NOW and shows its age in history | `live = age <= 600s`; a 660s run is historical with `age_seconds: 660` and its card shows `11m ago` | `test_matrix_phase_from_dead_process_not_live_past_window` | PASS |
| (d) Four states + filter + exact-window API | 7 API tests (above) + 4 frontend structural tests (above); all pinned to `server._utc_now` for determinism | `tests/test_admin_server.py`, `tests/test_admin_frontend.py` | PASS |
| VERIFY both directions: fresh phase → LIVE; old-only → not; dead-process phase → not live (window, not process) | the window predicate is the only decision; the dead-process case pins `published_at` 11 min old under a frozen `running` status | `test_matrix_marks_fresh_phase_live` (fresh → live), `test_matrix_marks_old_phase_historical_with_age` (old → not), `test_matrix_phase_from_dead_process_not_live_past_window` (dead → not) | PASS |

State matrix (pinned at `_utc_now = 2026-09-01T12:00:00Z`, `LIVE_WINDOW_SECONDS = 600`):

| State | Fixture | `live` | `last_phase_ts` | `age_seconds` |
|---|---|---|---|---|
| fresh-phase run | `published_at = 11:58:00Z` (120s) | True | `2026-09-01T11:58:00Z` | 120 |
| old-phase run | `published_at = 11:30:00Z` (1800s) | False | `2026-09-01T11:30:00Z` | 1800 |
| no-timestamp run | no stamp, empty tail | False | None | None (age-unknown) |
| window boundary | 11:50:01Z (599s) / 11:49:59Z (601s) | True / False | — | 599 / 601 |
| dead process, past window | `published_at = 11:49:00Z` (660s), status frozen `running` | False | `2026-09-01T11:49:00Z` | 660 |
| unstamped + fresh tail | no stamp, tail `11:59:00Z` | True | `2026-09-01T11:59:00Z` | 60 |

Full-suite run: 2967 passed, 9 skipped, 3 pre-existing failures unrelated to this change
(README By-the-Numbers drift + conflict markers in `docs/reviews/docs_architecture_refresh_remediation.md`
— both reproduce on the pre-p2 tree). Targeted suites
(`test_live.py`, `test_admin_server.py`, `test_admin_frontend.py`, `test_docs_health.py`): 134 passed.
