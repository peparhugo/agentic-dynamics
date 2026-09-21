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
| L1 | **Docs drift, 5 items** — 2× cli_surface (mental-model "full CLI" missing `--fork-checkpoint`/`--parent-run-id`), 1× spec_lifecycle (README count 235 vs index 236), 2× manifest_counts (coverage stale + orphan `_command_journal.py`) | **fixed in this PR** | `scripts/scan_docs_drift.py` fresh scan was 5/1,443 drift; report `experiments/results/docs_drift/latest.json` | flag clears on the next watchdog transition to drift 0 |

**L1 note (checkout dirt).** Two of the five items were real (the CLI flags; the unclassified
`_command_journal.py` helper). The spec-count item was the **main checkout's dirt**: six untracked
`control_room_*` spec YAMLs (plus a modified `control_room_run_journey.yaml`) regenerate the index
to 236 while the COMMITTED index — and the README — hold 235, so local scans report a count drift
that does not exist in a clean tree. Commit or park those specs; then regenerate the index and
README together. The register also fixed a latent anchor: `ARCHITECTURE.md` cited a gitignored run
ledger (`green_main_closure`) that no fresh clone or scan worktree can resolve.
| L2 | **Fleet job-row rot** — `4eb6c446982e` stuck `running` since 2026-09-01 (its runs actually **succeeded**); sibling `3a60905572d1` recorded `failed` | open | `fleet:jobs` hash; run ledgers `experiments/results/workflows/docs_refresh_remediation/20260901T01*` | add a stale-fleet-job reconcile to `scripts/fleet/fleet_manager.py` (no rail prunes job rows today; `control sweep-zombies` covers control runs only) |
| L3 | **DLQ piles** — `story_jobs:dead_letter` 85 · `fleet_jobs:dead_letter` 43 · `analysis_jobs:dead_letter` 17 | open | `scripts/fleet/dlq.py` (`list_dead`/`requeue_one`) | triage pass: requeue the real ones, archive the historical (story DLQ is Aug-31 experiment-era; fleet DLQ holds broker-unreachable ×7 + binding refusals ×5) |
| L4 | **Supervisor flags** — 69 entries: 68 `orphaned` delegation flags (newest **2026-08-27**) + 1 `off_track` (docs-drift, cleared by L1) | open | redis list `supervisor_flags`; file `experiments/results/supervisor/` | a fresh `supervise.py --once` pass when live state is wanted; decide an aging policy (observe-only rail keeps history by design) |
| L5 | **Projection watermark rows stale** — rows report lag 15; live `XINFO` says lag 0/pending 0 for all four groups | open (self-clearing) | `projection_lag()` vs `XINFO GROUPS kb:v1:changes` | clears on the next processed batch; if it persists, an orchestrator-side refresh |
| L6 | **Phase watchdog** — healthy; 4 stall events on record | parked | `stall_evidence` on ledgers: 2026-08-27 `p2_run_grid`, 2026-08-28 `p0_pin_spec`, 2026-09-01 `p4_activation_gate` (docs run), 2026-09-20 `synthesis_rerun` | none |
| L17 | **KB finding-layer backfill** — `kb_backfill_findings` derives **208 wave findings**, none present in the local KB store (`already_present=0`) | **fixed 2026-09-21** | ran: `emitted_new=41, already_present=167` (41 new wave findings incl. today's runs; the refusal probe recorded `not-merge-ready`); verified through the reader (`knowledge read`) | none |
| L18 | **`source_uri` uses the container path** — fleet emissions record `file:///repo/experiments/...`; the bytes land durably in the right place (reports + `kb/*.json` verified in the checkout), but the pointer is not host-resolvable | **fixed 2026-09-21** | `_pointer_uri` normalizes pointers to the documented repo-relative form at the emit seam (+ fail-first regression); 144 host-absolute + 11 container-prefix historical rows stay as-is (a supersede pass can re-emit if wanted) | none |
| L19 | **Promote-path robustness** — `_require_branch` accepted only a LOCAL `main` (fleet run clones are checked out detached: the first promotion needed a hand-made branch); the squash subject was rewritten by the run worktree's commit-msg hook (main landed as `[workflow] g_adversarial — …`) | **fixed 2026-09-21** | `promote.py`: base resolves from `origin/<base>` when the local branch is absent + `commit --no-verify` for the promotion commit; two fail-first regressions (base fallback; hook bypass) | none |

## B. Repo & store state

| ID | item | status | evidence | next action |
|---|---|---|---|---|
| L7 | **Worktree + clone sprawl** — 164 registered worktrees (all on disk), ~3,119 `/tmp` exp/story/wt dirs, and **42 GB** of run clones in `/tmp/agentic-dynamics-runs` (96 dirs) | open | `git worktree list`; `du -sh /tmp/agentic-dynamics-runs` | prune policy: `git worktree prune` for dead registrations; archive/remove old `/tmp` trees and run clones (keep the current run's until promoted) |
| L8 | **Unmerged branches** — 55 local + 11 remote `feature/*` ahead of main (2026-08-14 → 2026-09-19, up to 20 commits) | open | `git for-each-ref` vs `main` | per-branch triage: merge / archive to `refs/archive/*` / delete; start with the newest (chroma-healthcheck, control-room-run-journey, graph-leg-closeout) |
| L9 | **Spec lifecycle** — 24 `failed` + 6 `blocked` specs (last runs 2026-08-14 → 2026-09-16) | open | `experiments/specs/INDEX`/`STATUS.md` statuses | per-spec verdict (supersede / close / rerun); start with recent-activity ones: `control_db_publication`, `engine_gaps_verifier_revision`, `control_room_instrument_build` |
| L10 | **Legacy data stores** — `experiments/results/legacy_labs/` (20 entries + README), quarantine store (README only) | parked | dir READMEs | leave as documented; revisit only if a consumer appears |

## C. Loop & arc follow-ups

| ID | item | status | evidence | next action |
|---|---|---|---|---|
| L11 | **Notes-collision convention** — loop runs commit `notes/*.md` at fixed paths; two runs conflicted at merge time (#109) | open | `notes/ci-preflight/` namespacing precedent; loop design doc | namespace run notes per run/task on the next loop touch |
| L12 | **Loop candidates from `run-0fad6c313dcd`** — `emit-observability`, `emit_scope` split (metadata findings land in the cell scope), run-workflow skill amendments | open | `notes/minted.md` (7 pattern/v1 records minted); posterior §UPDATES | fold into the next loop iteration; doc/skill amendments stay reviewed commits |
| L13 | **Re-run → promote** — `run-79fbc7f23d61` (v1.3.1 code) | **in flight** | control packet `active_runs`; clone `/tmp/agentic-dynamics-runs/run-79fbc7f23d61/repo` | `workflow promote --dry-run` → promote on completion |
| L14 | **Item-5 fork rating** — the rating package (arms + comparison + brief) is in main | with the controller | `experiments/results/fork_contemplation/item5/` | the controller rates; the rating sets the fork policy |

## D. Process

| ID | item | status | evidence | next action |
|---|---|---|---|---|
| L15 | **Session close** for the 2026-09-21 unit | open | this register + decision records | write after L13 lands |
| L16 | **Supervisor flag storage split** — live flags in the `supervisor_flags` redis list; `experiments/results/supervisor/` holds only `monitor_session.json` | parked | noted during the 2026-09-21 landscape | document in the next supervisor touch |

## Not forgotten (recorded, resolved)

The 2026-09-21 session's own findings and fixes, for continuity: the reader-verb CI repair
(`e5a2d1f43`), fleet scopes (PR #110), the clone-aware artifact gates + the loop v1.3/v1.3.1
(PRs #111/#112), the retrieval-audit re-run (PR #107), the live loop's findings F1/F2/F8
(decision `a40bcf16…`). See the session close and the decision records.
