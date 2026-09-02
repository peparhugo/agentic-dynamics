---
status: accepted
---

# control_db_publication — independent adversarial review (p7)

**Role:** the independent adversarial reviewer — a DIFFERENT model and session (deepseek-v4-flash
vs the opus-5 author; the house independence convention). This review tried to **falsify** the
P1/P2 control-plane wave, not certify it. Every claim below was re-derived from the actual code,
a live SQLite/CLI probe, or a test run — never asserted.

**Spec under review:** `workflows/repository/control_db_publication.yaml` (p1→p8). Branch tip:
`e15afbdeb` (`[workflow] p6_publication_receipt`), 12 commits ahead of `main`. The review fixes
below were made **on this branch** (p7's "FIX on the branch or RECORD" mandate) and are included
in this commit's tree.

## Attack plan and re-verification

Attacked in the mandate's order: (1) control db authority, (2) outbox + child contract,
(3) watermark visibility, (4) control packet derivation, (5) surface generation, (6) publication.
Independent harness state: the exact p8 test-gate list from the spec was run before and after the
fixes below.

## Finding table

| # | attack | re-verification evidence | fix-or-record | residual scope |
|---|---|---|---|---|
| F1 | **(6)/(5) — `publish_release.py` is an unclassified script, so the branch's own p8 test gate is RED** | `tests/test_script_classification.py::test_manifest_covers_every_script_with_zero_orphans` failed: `orphans (on disk, unclassified): ['publish_release.py']`. `scripts/CONTEXT.md`'s manifest (the machine-parsed classification) had no `publish_release.py` entry, while p6 added the script. The spec's p8 gate lists this test, so the mandated harness gate would fail as-is. | **FIXED on branch** — added `maintained: publish_release.py` to `scripts/CONTEXT.md`. Re-ran the full p8 gate list: **400 → 401 passed, 0 failed**. | none — a one-line classification the p6 phase missed. |
| F2 | **(2) — the P0-2 child contract is only half-held: `--only-phase` children still write run ledgers and refresh the spec index** | `scripts/run_workflow.py` `_run_workflow_cli` wrote the ledger JSON (`out_dir/<ts>.json`, lines 587–591) and called `_refresh_index` (line 608) **unconditionally**, including child mode. The orchestrator's cell env (`scripts/fleet/spawn_wrapper.py` `build_phase_request`, `scripts/fleet/docker_executor.py`) does **not** set `FINOPS_SKIP_SPEC_INDEX`. `_control_open_run`/`_control_terminal_write` are child-inert (no run row, no emission) — p2 removed the child's *knowledge* emission — but the partial child ledger lands in the shared rw `experiments/results` mount and `spec_status.py` reads it as run evidence. The spec's hard rule 2 ("children never emit knowledge, refresh indexes, or write ledgers independently") was violated for two of its three verbs. | **FIXED on branch** — gated the ledger write and `_refresh_index` on `not args.only_phase` (parent aggregates; the child's stdout envelope is its only record). Preserved the attack-4 source-pin test (`test_attack4_no_mutation_window…` still anchors the exact terminal-write line). Re-ran `test_fact_auto_emit` + `test_fact_auto_emit_adversarial` + `test_workflow_runner` + `test_admin_server`: **159 passed**. | none for the child ledger/index path. The opt-in `emit_self` phase-emit path remains (see F6). |
| F3 | **(3)/(4) — the ONE control packet renders a STALE projector's recorded zero-lag as `0`: a dead projector reads "caught up"** | Live probe: a `registry` watermark with `lag_events=0` and `last_success_at` 12h old rendered `projection_lag: {registry: 0}` with **no** `degraded` note (the note only fires for `None` lag). p3's own rule ("a stale recorded 0 must not be believed") was lost at the packet surface — the Control Room's `/api/projections` carries health, but the packet the master reads every turn did not. | **FIXED on branch** — `build_packet` now carries a projection's lag only when its health is `CURRENT` or `LAGGING`; `STALE`/`FAILING` render `null` + a `degraded` note. New test pins it (`test_a_stale_projections_recorded_zero_lag_is_not_carried_as_zero`). Re-ran `test_control_status.py`: **54 passed**; live probe now renders `{registry: null}` + `degraded: lag unknown for: registry`. | none for the packet surface. |
| F4 | **(1) — code paths still treat a run ledger as the authoritative run state: `--resume` and the spec index** | `workflow_runner._completed_phases_from_index` (the `--resume` fallback, `workflow_runner.py:924`) reads the latest run **ledger** via the spec index's `results_pointer` to decide which phases are `ok`/skippable. `experiment/spec_status.py` derives the spec index's run-derived columns (`active`, status, `results_pointer`) from `experiments/results/workflows/**/*.json`. Neither consults `control.db`'s `step_attempts`. | **RECORDED as accepted limitation** — the spec_catalog is documented (control_plane_vocabulary.md §"The relationships that matter") as indexing *specs* outside the run-state chain, so its ledger derivation is a broad accepted residual; the `--resume` fallback, however, answers a run-state question from the ledger and is a genuine residual ledger-as-authority path. **Recommended follow-up:** re-point `_completed_phases_from_index` to control-db `step_attempts`. Not fixed here: the git-log primary resume path is unaffected, and re-pointing is a deeper change better done deliberately. | `--resume`'s ledger fallback; the spec index's run-derived columns. |
| F5 | **(6) — `publish release --dry-run` touches the working tree: it regenerates the tracked `apps/website/data.js`** | Code path re-derived: the dry-run branch of `publish_release.main()` runs `build()` (default `run_build_data`) unless `--skip-build` is passed; `build_data.py:2441-2442` writes the **tracked** `apps/website/data.js`. A dry run on a tree whose data.js is stale (the normal pre-publish state) therefore modifies the tree. It does **not** touch the control database (read-only handle), does not deploy, and does not write receipts. The dry-run test injects a fake builder, so this side effect is real in production and invisible to the suite. | **RECORDED as accepted limitation** — the build is the fidelity rehearsal (it proves the build succeeds and checks the freshly-built data), the dirty artifact is the same file a real publish ships, and `--skip-build` gives a strict no-touch dry run. If a fully-clean rehearsal is wanted, snapshot+restore `data.js` around the dry run — a small, operator-visible design choice left to the author. | the dry-run's data.js regeneration. |
| F6 | **(2) — a phase can still emit knowledge directly: the opt-in `emit_self` path bypasses the outbox** | `workflow_runner._emit_self_finding` (`workflow_runner.py:908`) calls `knowledge_ingestion.emit_phase_finding` → `publish_event` directly when `rag_params.emit_self` is true — not through the outbox. Default OFF; no committed spec enables it. | **RECORDED as accepted limitation** — opt-in, dormant, pre-existing; the KB write guard still applies; the outbox covers the run's terminal emission. If `emit_self` is ever enabled, that path is not at-least-once. | the `emit_self` phase emit (dormant). |

## Clean (re-verified, not asserted)

- **(1) Vocabulary + immutability.** `RunState` is exactly the twelve mandated values; the schema's
  `CHECK` constraints reject a thirteenth state at the SQL level. Terminal immutability holds twice:
  live probe — `UPDATE runs SET model='x'` on a `failed` run via raw SQL raises `sqlite3.IntegrityError`
  (the `runs_terminal_immutable` trigger), and `transition_run` refuses with `TerminalStateError`.
  The evidence tables (`gate_results`/`approvals`/`promotions`/`run_transitions`/`publication_receipts`)
  are append-only via `BEFORE UPDATE/DELETE` triggers. A run is reconstructible from `control.db` alone
  (`reconstruct_run`); the ledger is a pointer column, never a fallback source inside this module.
- **(1) No overloaded "completed".** The control plane stores state strings only; the only four-value
  vocabulary (`succeeded/awaiting/failed/cancelled`) lives in the *ledger* and is translated by
  `run_state_from_ledger_state` (`succeeded → promotable`, never `merged`/`published`). `pipeline_status.py`'s
  "completed" refers to the story-queue cell state machine, a different plane.
- **(2) At-least-once re-derived.** `OutboxPublisher._attempt` order is artifact → publish → **ack** →
  bookkeep → mark delivered. `mark_outbox_delivered` fires only after the stream ack; a crash in the gap
  leaves the row `pending` and it re-delivers (consumers key on `knowledge_id`). Pinned by
  `test_redelivery_after_a_crash_between_ack_and_mark` and `test_a_row_stays_pending_when_the_stream_never_acknowledges`.
  An unreachable stream charges **no** row an attempt (`DrainReport.stream_error`), so a Redis blip does not
  burn the whole queue's retry budget. The parent's terminal write (`outbox.record_terminal_run`) is one
  `BEGIN IMMEDIATE` transaction: transition + result envelope + every event, all-or-nothing.
- **(3) Stale is visible where it matters.** `classify` orders the verdicts so `STALE` dominates a recorded
  zero lag; unknown lag is `NULL`, never fabricated `0`; the kb-worker refreshes on every batch (empty
  included) and records connection errors as `last_error`. `apps/control_room/routes/telemetry.py:145`
  `api_projections` reads `projection_watermarks.read_report()` with a distinct 503 `control_db_unavailable`.
- **(4) safe_actions DERIVED.** `derive_safe_actions` builds every entry from db rows plus
  `control_db.ALLOWED_TRANSITIONS` — the same graph the database enforces — with a 1:1 approve/awaiting
  invariant. Live probe (seeded awaiting run): `[{approve, …}, {cancel, …}]`, both legal edges. No
  hard-coded action list anywhere. `control_epoch` advances on every run-state transition (live: create→1,
  running→2, failed→3). Note: approvals/gate/watermark/outbox writes do **not** move the epoch — faithful
  to "bumps on every state transition" (only runs have state), but a master must diff packet content, not
  the epoch alone.
- **(4) Packet integrity.** `CONTROL_STATUS_SCHEMA` (JSON Schema) + dependency-free `validate_packet`
  agree; packet is a pure function of injected git/heartbeat/clock inputs; `agentic-dynamics control status`
  exits 3 on a missing control db (distinct from an empty packet) — verified live.
- **(5) Surfaces collapse + `--check`.** `render_root()` emits root `AGENTS.md`/`CLAUDE.md` from
  `agent_config/`; `--check` passes on the committed tree, and a live drift probe (append to
  `agent_config/rules.md`, no regen) exits **1** with `stale: AGENTS.md` (restored clean afterwards). CI
  (`pytest.yml` `surfaces` job) runs it. The default master context (`AGENTS.md` = rules.md + `mental-model.md`
  + `conventions.md`) carries **no** run-state tables, no system snapshot, and no 177-spec list — only the
  pointer to `control status --json`.
- **(6) Publication one transaction + every page.** `check_site_consistency` discovers pages via
  `rglob("*.html")` — every page, not just `index.html` — and runs two independent checks (data-stat
  fallbacks + a declared-positive prose net over body and meta/OG/Twitter text). `verify_projections`
  refuses on `lagging`/`stale`/`failing`/`unknown` (a stale zero-lag is not believed). `--dry-run` needs no
  operator; a real publish refuses without `--operator` (P0). Both hosts deploy, both outcomes are recorded
  as separate rows, and a failed host is visible, not omitted.

## Accepted residual scope (explicit)

The deep-review findings this wave closes had residual edges, and three survive here as accepted:

1. **Ledger-as-authority for `--resume` and the spec index (F4).** The control db is authoritative for the
   runs it records, but the resume fallback and the spec index still read the ledger. The publish gate and
   the packet never read the ledger — so the *public* surfaces are unambiguously control-db-derived — but a
   future re-point of `--resume`/`spec_status` to `step_attempts` is the last ledger removal.
2. **`--dry-run` regenerates tracked `data.js` (F5).** Scope: the dry run is a build-and-verify rehearsal,
   not a zero-touch plan; `--skip-build` is the strict mode.
3. **Control Room + supervisor are not yet re-pointed to the control packet.** The `/api/projections`
   route is wired to the watermark surface; the other portal status routes and `supervise.py` still read
   Redis/session files. The mandate allowed the portal to "wrap" the packet; the re-point is post-merge
   operator work.

## Harness gate (p8) — measured, before and after

The spec's p8 list (10 families) was run twice:

| state | result |
|---|---|
| as-shipped (before F1–F3 fixes) | **400 passed, 1 failed** — `test_script_classification.py::test_manifest_covers_every_script_with_zero_orphans` (F1) |
| after fixes (this commit) | **401 passed, 0 failed** (test_control_db, test_outbox, test_projection_watermarks, test_control_status, test_agent_config_render, test_doc_lifecycle, test_script_classification, test_cli_resolution, test_publish_release, test_spawn_wrapper) |

Also green: `test_fact_auto_emit` + `test_fact_auto_emit_adversarial` (the attack-4 source-pin test),
`test_workflow_runner`, `test_admin_server`, `test_dependency_direction`, `test_data_flow`, `ruff check`
on all touched files, and `python3 scripts/_gen_instructions.py --check`.

## Release verdict

**The `control_db_publication` branch is MERGE-READY to `main` with this review's three fixes (F1–F3)
included.** The four attack axes that could have falsified the wave — terminal-state immutability,
at-least-once delivery, packet-derived safe_actions, and every-page HTML consistency — all re-verified
clean; the three fixed findings were branch defects, not design failures. The accepted residuals (F4–F6)
are scoped and reasoned, not silent.

**What the operator must do after merge:**

1. **Arm the publication gate.** Run `agentic-dynamics publish release --candidate-sha <main-sha> --dry-run --skip-build`
   for a strict no-touch rehearsal (or without `--skip-build` to rehearse the build). The FIRST real
   `publish release --candidate-sha <sha> --operator <controller>` is a P0 action — deploy both hosts and
   confirm two `succeeded` rows + a `publication/v1` receipt land in `control.db`.
2. **Re-point the Control Room routes (and optionally the supervisor) to the control packet.** `/api/projections`
   is already on the watermark surface; the status routes and `supervise.py` should consume `control-status/v1`.
3. **Regenerate derived surfaces + the spec index** after merge: `agentic-dynamics surfaces sync` and
   `python scripts/spec_status.py` (the surfaces job will also gate this on CI).
4. **Decide the two follow-ups** recorded here: re-point `--resume`'s ledger fallback to `control.db`
   `step_attempts` (F4), and whether `--dry-run` should default to `--skip-build` (F5).
5. **Promote the `surfaces` status check to REQUIRED** in branch protection (a P0 controller action) — it is
   wired and green but not yet blocking, per the note in `pytest.yml`.
