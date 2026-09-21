---
status: accepted
---

# Loose-ends register — opened 2026-09-21

**What this is.** The standing inventory of open, un-triaged work found by the 2026-09-21
session (the merges, the live world-model-loop runs, and the docs-drift / watchdog / queue
sweeps). Each item carries a stable ID, its current status, where the evidence lives, and the
next action.

**How to use it.** A future session picks an ID, acts, and records the close in the item's row
(and in its own session close). Statuses: `open` · `in flight` · `fixed (awaiting flag clear)` ·
`parked (decided: no action)`.

## A. Rails & hygiene

| ID | item | status | evidence | next action |
|---|---|---|---|---|
| L1 | **Docs drift, 5 items** — 2× cli_surface (mental-model "full CLI" missing `--fork-checkpoint`/`--parent-run-id`), 1× spec_lifecycle (README count 235 vs index 236), 2× manifest_counts (coverage stale + orphan `_command_journal.py`) | **fixed 2026-09-21 (two stages)** | stage 1 (PR #113): the CLI flags, the manifest helper, the latent anchor. Stage 2 (this PR): the five parked `control_room_*` specs **committed**, the modified `control_room_run_journey.yaml` committed, the index/STATUS regenerated (`world_model_loop` + `world_model_loop_refusal_probe` now indexed; `control_room_working_slice` dropped — no file), README → 236 (11+225). **Scan: 0 / 1,443** | flag clears on the next watchdog transition to drift 0 |

**L1 note (resolved).** The local "dirt" was a real corpus/index inconsistency in **both**
directions: main's committed index listed five `control_room_*` specs whose files were never
committed (a stale regeneration) and missed the two `world_model_loop` specs that were committed
later. Both directions are closed by committing the parked files + regenerating the index + README
together. **Closing addendum (the sync after #116):** a sixth parked spec,
`control_room_working_slice.yaml`, surfaced once the checkout synced to main — committed in the
same wave, with the corpus/index/README/data.js all at **237 (11 + 226)**. Stage 1 also fixed a latent anchor: `ARCHITECTURE.md` cited a gitignored run ledger
(`green_main_closure`) that no fresh clone or scan worktree can resolve.
| L2 | **Fleet job-row rot** — `4eb6c446982e` stuck `running` since 2026-09-01 (its runs actually **succeeded**); sibling `3a60905572d1` recorded `failed` | **fixed 2026-09-21** | the new `fleet_manager.py sweep-stale-jobs` rail: the ghost is now `completed`, reconciled from its own ledger (`docs_refresh_remediation/20260901T133313Z.json (ok)`); `stale_ts` preserves the prior timestamp; report-only by default, `--apply` to write | none — the docs-drift proposal gate can re-propose |
| L3 | **DLQ piles** — `story_jobs:dead_letter` 85 · `fleet_jobs:dead_letter` 43 · `analysis_jobs:dead_letter` 17 | **fixed 2026-09-21** | `dlq.py triage --out … --apply`: the 145 entries are archived to `experiments/results/fleet/dlq_report_20260921.json` (80 KB; counts by reason + full entries) and the live lists are cleared. **No requeues** — re-driving a dead job EXECUTES it; that stays a per-entry operator act via `requeue_one`. Diagnostic cluster: `launch-broker unreachable ×7` (the broker was down at some point — a fleet-reliability signal worth watching) | none |
| L4-note | **broker-unreachable cluster** (inside L3) — 7 fleet submits died with `Connection refused — /run/launch-broker.sock` | open | `dlq_report_20260921.json` `fleet_jobs` entries | if it recurs, check the broker unit's restart history (`journalctl --user -u agentic-dynamics-launch-broker`) |
| L4 | **Supervisor flags** — 69 entries: 68 `orphaned` delegation flags (newest **2026-08-27**) + 1 `off_track` (docs-drift, cleared by L1) | open | redis list `supervisor_flags`; file `experiments/results/supervisor/` | a fresh `supervise.py --once` pass when live state is wanted; decide an aging policy (observe-only rail keeps history by design) |
| L5 | **Projection watermark rows stale** — rows report lag 15; live `XINFO` says lag 0/pending 0 for all four groups | open (self-clearing) | `projection_lag()` vs `XINFO GROUPS kb:v1:changes` | clears on the next processed batch; if it persists, an orchestrator-side refresh |
| L6 | **Phase watchdog** — healthy; 4 stall events on record | parked | `stall_evidence` on ledgers: 2026-08-27 `p2_run_grid`, 2026-08-28 `p0_pin_spec`, 2026-09-01 `p4_activation_gate` (docs run), 2026-09-20 `synthesis_rerun` | none |
| L17 | **KB finding-layer backfill** — `kb_backfill_findings` derives **208 wave findings**, none present in the local KB store (`already_present=0`) | **fixed 2026-09-21** | ran: `emitted_new=41, already_present=167` (41 new wave findings incl. today's runs; the refusal probe recorded `not-merge-ready`); verified through the reader (`knowledge read`) | none |
| L18 | **`source_uri` uses the container path** — fleet emissions record `file:///repo/experiments/...`; the bytes land durably in the right place (reports + `kb/*.json` verified in the checkout), but the pointer is not host-resolvable | **fixed 2026-09-21** | `_pointer_uri` normalizes pointers to the documented repo-relative form at the emit seam (+ fail-first regression); 144 host-absolute + 11 container-prefix historical rows stay as-is (a supersede pass can re-emit if wanted) | none |
| L19 | **Promote-path robustness** — `_require_branch` accepted only a LOCAL `main` (fleet run clones are checked out detached: the first promotion needed a hand-made branch); the squash subject was rewritten by the run worktree's commit-msg hook (main landed as `[workflow] g_adversarial — …`) | **fixed 2026-09-21** | `promote.py`: base resolves from `origin/<base>` when the local branch is absent + `commit --no-verify` for the promotion commit; two fail-first regressions (base fallback; hook bypass) | none |

## B. Repo & store state

| ID | item | status | evidence | next action |
|---|---|---|---|---|
| L7 | **Worktree + clone sprawl** — 164 registered worktrees (all on disk), ~3,119 `/tmp` exp/story/wt dirs, and **42 GB** of run clones in `/tmp/agentic-dynamics-runs` (96 dirs) | **partially fixed 2026-09-21** | the new `fleet_manager.py prune-runs` rail (report-only by default): **54 clones pruned = 21.9 GB freed** (42→21 GB); the **24 `promotable` clones are kept — an unpromoted candidate's commits exist nowhere else**; 17 failed-within-keep + 1 merged-within-keep skipped. Policy: `merged`/`cancelled` after 3 days, `failed` after 7; unknown provenance is never pruned | the remaining `promotable` backups need a promote-or-abandon decision per candidate; worktree removal still needs a policy (see L8 note) |
| L8 | **Unmerged branches** — 55 local + 11 remote `feature/*` ahead of main (2026-08-14 → 2026-09-19, up to 20 commits) | **partially fixed 2026-09-21** | triage executed: **110 fully-merged local branches deleted** (their commits are ancestors of main — names only), **52 unmerged branches archived to `refs/archive/*`** (non-destructive copies) and kept for review; **101 further deletions were skipped — those branches are checked out by `/tmp` worktrees** (they clear once the worktree policy removes the stale trees); remote branches untouched | worktree policy (which of the 164 to retire) unblocks the rest |
| L9 | **Spec lifecycle** — 24 `failed` + 6 `blocked` specs (last runs 2026-08-14 → 2026-09-16) | **proposal attached 2026-09-21** | the full table (name · status · last-run) is below; several are demonstrably superseded (the mental model names `admission_leases`, `control_db_publication`/`control_db_evidence`, `promote_row_closeout`, the `cap_site_revamp*` chain as landed work) | batch decision needed: mark the demonstrably-landed ones closed/superseded (a status sweep across their YAMLs), rerun or close the rest. **Controller's call — content decisions, not mechanical.** |
| L10 | **Legacy data stores** — `experiments/results/legacy_labs/` (20 entries + README), quarantine store (README only) | parked | dir READMEs | leave as documented; revisit only if a consumer appears |

**L9 — the stalled-spec table (for the batch decision).** 30 specs carry `failed`/`blocked` from
their last run (2026-08-14 → 2026-09-16). The mental model already names several as landed work
(`admission_leases`, `control_db_publication`, `control_db_evidence`, `promote_row_closeout`, the
`cap_site_revamp*` chain) — those are candidates to close/supersede; the rest need a rerun-or-close
call.

| spec | status | last run |
|---|---|---|
| control_room_portal | failed | 2026-08-14 |
| design_sessions | failed | 2026-08-14 |
| claude_background_sessions | failed | 2026-08-14 |
| evidence_redesign | failed | 2026-08-14 |
| workflow_step_routing | blocked | 2026-08-14 |
| agentic_dynamics_rebrand | failed | 2026-08-14 |
| rag_knowledge_base | failed | 2026-08-14 |
| remediation_data_integrity | blocked | 2026-08-15 |
| routing_kb_wiring | blocked | 2026-08-17 |
| canonical_state_design | failed | 2026-08-18 |
| semantic_integrity_release | failed | 2026-08-21 |
| cap_shadow_campaign | blocked | 2026-08-24 |
| cap_addendum_implement | failed | 2026-08-24 |
| cap_site_revamp2 | failed | 2026-08-26 |
| cap_site_revamp3 | failed | 2026-08-27 |
| cap_site_revamp4 | failed | 2026-08-27 |
| cap_adaptive_2c | failed | 2026-08-27 |
| cap_site_revamp4_diagrams | failed | 2026-08-27 |
| cap_adaptive_2d | failed | 2026-08-28 |
| fleet_ladder_implementation | blocked | 2026-08-30 |
| concurrency_ladder | failed | 2026-08-31 |
| control_room_usage_wiring | failed | 2026-09-01 |
| admission_leases | blocked | 2026-09-01 |
| control_db_publication | failed | 2026-09-02 |
| control_db_evidence | failed | 2026-09-02 |
| engine_gaps_verifier_revision | failed | 2026-09-02 |
| authoring_product_aio | failed | 2026-09-03 |
| promote_row_closeout | failed | 2026-09-04 |
| flash_exploration_build | failed | 2026-09-10 |
| control_room_instrument_build | failed | 2026-09-16 |

## C. Loop & arc follow-ups

| ID | item | status | evidence | next action |
|---|---|---|---|---|
| L11 | **Notes-collision convention** — loop runs commit `notes/*.md` at fixed paths; two runs conflicted at merge time (#109) | open | `notes/ci-preflight/` namespacing precedent; loop design doc | namespace run notes per run/task on the next loop touch |
| L12 | **Loop candidates from `run-0fad6c313dcd`** — `emit-observability`, `emit_scope` split (metadata findings land in the cell scope), run-workflow skill amendments | open | `notes/minted.md` (7 pattern/v1 records minted); posterior §UPDATES | fold into the next loop iteration; doc/skill amendments stay reviewed commits |
| L13 | **Re-run → promote** — `run-79fbc7f23d61` (v1.3.1 code) | **fixed 2026-09-21** | promoted → main `1217356c4` (squash: the emit-seam guard + the run record + 7 `pattern/v1` skills; control row `merged`, promotions row recorded; decision `6010a8da…`) | none — the next loop iteration starts from L11/L12 |
| L14 | **Item-5 fork rating** — the rating package (arms + comparison + brief) is in main | with the controller | `experiments/results/fork_contemplation/item5/` | the controller rates; the rating sets the fork policy |

## D. Process

| ID | item | status | evidence | next action |
|---|---|---|---|---|
| L15 | **Session close** for the 2026-09-21 unit | **fixed 2026-09-21** | slug `aio-world-model-loop-live-merge-closeout`; knowledge_id `d1e99149…` (`session-close/v1`) | none |
| L16 | **Supervisor flag storage split** — live flags in the `supervisor_flags` redis list; `experiments/results/supervisor/` holds only `monitor_session.json` | parked | noted during the 2026-09-21 landscape | document in the next supervisor touch |

## Not forgotten (recorded, resolved)

The 2026-09-21 session's own findings and fixes, for continuity: the reader-verb CI repair
(`e5a2d1f43`), fleet scopes (PR #110), the clone-aware artifact gates + the loop v1.3/v1.3.1
(PRs #111/#112), the retrieval-audit re-run (PR #107), the live loop's findings F1/F2/F8
(decision `a40bcf16…`). See the session close and the decision records.
