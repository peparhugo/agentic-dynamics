# `scripts/` — Scripts Reference (classification manifest)

72 command scripts plus two helper modules (`_bootstrap.py`, `_gen_instructions.py`), each
command in exactly one bucket (critique rec 5). The classification below is machine-parsed by
`tests/test_script_classification.py` — keep the marker lines intact. The `one-time` bucket
lives under `scripts/archive/`; the other buckets live at the top of `scripts/`.

<!-- scripts-classification: start -->
maintained: retro_session_routing.py run.py sweep_parallel.py sweep_silent_mode.py batch_run.py remaining_batch.py multi_phase.py run_story.py batch_stories.py run_workflow.py enqueue.py worker.py monitor.py reinterleave_queue.py enqueue_analysis.py analysis_worker.py analyze_worktrees.py analyze_trajectories.py analyze_stories.py build_data.py sync_data.py generate_manifest.py inventory.py kb_produce.py kb_produce_sources.py kb_worker.py registry.py review_all.py review_stories.py trigger_reviews.py enqueue_reviews.py finalize_reviews.py spec_status.py pipeline.py validate_session.py verify_tests.py supervise.py claude_agents_supervisor.py
historical: lab_grit.py lab_basin_topology.py lab_basin_topology_neo4j.py lab_cache_economics.py lab_claude_audit.py lab_condition_effects.py lab_correctness_premium.py lab_flail_triggers.py lab_correctness_escape_quadrants.py lab_opencode_meta_analysis.py lab_quality_frontier.py lab_sonar_quality.py lab_story_arc.py lab_story_review.py lab_survival_horizon.py lab_task_routing.py lab_think_do_coupling.py lab_tool_archetypes.py lab_verification_frontier.py lab_verification_value.py
one-time: backfill_artifacts.py backfill_story_artifacts.py backfill_story_transcripts.py backfill_deep_metrics.py batch_analyze_ts_ssg.py finish_sweep.py regen_typescript_ssg.py backfill_sonar.py backfill_costs.py compute_sonar_deltas.py embed_sessions.py recovery_cost_table.py rescore_conventions.py recover_stories.py kb_produce_registry.py retract_payloadless_stories.py
<!-- scripts-classification: end -->

- **maintained command** — reached via `agentic-dynamics <subcommand>` (the Stage 3 CLI).
- **historical analysis** — the 19 active lab books, reached via `agentic-dynamics analyze lab <name>`.
- **one-time migration** — archived to `scripts/archive/` (fold WS-10), not maintained.
- **deprecated** — none remain: WS-09 (`review_worker.py`) retired in this phase; the WS-01
  scripts (`plan.py`, `analyze_with_ollama/opencode`, `build_graph`, 8 `*_DEPRECATED_bge_m3`)
  were retired in Stage 1.

## Primary Entry Points

| Script | What it does | When to use |
|--------|-------------|-------------|
| `run.py` (502 lines) | Full experiment pipeline — perturb → invoke → evaluate → report | Running a single experiment config |
| `analyze_worktrees.py` (1398 lines) | Post-hoc Game Report generator from `/tmp/exp_*` worktrees | After experiments complete; fills gap for sessions that only collected raw cost data |
| `inventory.py` (392 lines) | Experiment/worktree inventory CLI | `inventory.py refresh` to rebuild, `list`/`stats`/`report` to inspect |
| `build_data.py` (1188 lines) | Generates `apps/website/data.js` from inventory + results | Push updated data to website |
| `pipeline.py` (1267 lines) | YAML-driven phase orchestration (`experiments/definitions/configs/plans.yaml`) | Multi-phase DAG runs (ci, deploy, full_matrix, feature, ship_features, cross_models) |
| `agentic_dynamics/experiment/compile_experiment.py` (not in scripts/) | spec → DAG compiler, **written**; no standalone CLI — invoke via the `compile_experiment` tool (§3.1) or the Python API directly | Compiling a spec into a DAG |

## Experiment Runners

| Script | Lines | Purpose |
|--------|-------|---------|
| `run.py` | 502 | Primary runner. `python scripts/run.py <config.yaml> --model <provider/model>`. Produces JSON + Markdown game reports. `--backend {auto,opencode,claude_cli}` routes `anthropic/*` to the Claude CLI adapter. |
| `batch_run.py` | 110 | Parallel batch runs on DeepSeek via `ThreadPoolExecutor`. |
| `multi_phase.py` | 128 | Iterative development: understand → build → refactor → add_feature. Measures compounding effects. |
| `remaining_batch.py` | 81 | Runs remaining uncompleted experiment cells one at a time. |
| `finish_sweep.py` | 73 | Completes remaining silent-mode sweep cells. |
| `sweep_parallel.py` | 99 | 4 models × 2 silent modes × 2 operators = 16 parallel subprocess runs. |
| `sweep_silent_mode.py` | 287 | Measures "natural" vs "forced-silent" cost gap (Explanation Tax decomposition). |
| `sweep_parallel.sh` | 141 | Bash equivalent of parallel silent-mode sweep. |
| `batch_stories.py` | 116 | Batch experiment runner — executes all DeepSeek matrix cells sequentially. |
| `recover_stories.py` | 217 | Session timeout recovery — continues timed-out opencode sessions via `--session`. |
| `run_workflow.py` | 88 | Runs an `agent_task` workflow (the execute phase) against a goal inside a git worktree; wrapped by the `run_workflow` tool (§3.1). Refreshes the spec status index (best-effort) after writing the run ledger. |
| `spec_status.py` | 94 | Regenerates the **derived** spec lifecycle index — `experiments/specs/index.json` (machine schema) + `experiments/specs/STATUS.md` (agent-facing table) — from `experiments/definitions/*.yaml` + `workflows/**/*.yaml` and the run ledgers in `experiments/results/workflows/<spec>/*.json`. Thin CLI over `agentic_dynamics.experiment.spec_status`; `--dry-run`, `--json`, `--print`, `--spec <name>`. Never hand-edit the two artifacts. |

## Post-Hoc Analysis

| Script | Lines | Purpose |
|--------|-------|---------|
| `analyze_worktrees.py` | 1398 | **Primary analysis script.** Reads worktrees, evaluates code, runs full analysis stack (solution, basin, strategy), produces GameReport markdown files. `--no-tests` flag skips pytest. |
| `analyze_trajectories.py` | 435 | Parses `session.jsonl` transcripts. Produces `_trajectory_summary.json` and `_trajectory_aggregate.json`. |
| `validate_session.py` | 99 | Runs `pytest` on generated code in worktrees. Replaces heuristic correctness with actual test pass/fail. |
| `verify_tests.py` | 140 | Independent test execution — runs each story cell's own test suite; sole source of truth for the `test_executed_success` ledger field. |
| `review_all.py` | 156 | Review every story directly (ThreadPoolExecutor, no Redis). Writes `reviews/review_{story_id}.json`. Grounds reviews in AST/Sonar/convention mechanics. |
| `review_stories.py` | 91 | Batch commit + story review runner. |
| `review_worker.py` | 190 | [deprecated] Redis review-queue worker (SDK bridge). Superseded by `review_all.py`; retired in Stage 3. |
| `trigger_reviews.py` | 79 | Waits for analysis to drain, then enqueues + spawns review workers (async handoff between post-hoc phases via the Redis queue on 6380). |
| `enqueue_reviews.py` | 145 | Scans story result JSONs, finds worktree commits, enqueues review jobs to Redis. |
| `finalize_reviews.py` | 89 | Merges per-session review files (`review_{story_id}_S{n}.json`) written by `review_worker.py` into aggregate JSONs. |
| `analyze_stories.py` | 172 | Post-hoc story analysis — analyzes story worktrees after experiments complete. |
| `analysis_worker.py` | 158 | Pops analysis jobs from Redis, runs AST + SonarQube per story via `analyze_story_worktree`. |
| `enqueue_analysis.py` | 86 | Scans story result JSONs and enqueues one post-hoc analysis job per story with no existing analysis, into Redis. |
| `rescore_conventions.py` | 57 | Re-runs convention scoring on all worktrees, updating the convention score + violations in `analysis_{story_id}.json`. |
| `compute_sonar_deltas.py` | 99 | Computes baseline-vs-perturbed SonarQube deltas (bugs, code smells, cognitive complexity, duplication, maintainability, security) for all entries in `_results_summary.json`. |
| `embed_sessions.py` | 161 | Indexes all experiment `session.jsonl` reasoning steps into ChromaDB. |
| `build_graph.py` | 99 | Builds the Neo4j experiment knowledge graph — nodes for models, configs, runs, perturbation operators, strategies. |
| `analyze_with_ollama.py` | 111 | Qualitative experiment analysis via DeepSeek R1 on Ollama — narrative commentary over metrics/session data. |
| `analyze_with_opencode.py` | 162 | Qualitative experiment analysis via a real opencode session on DeepSeek v4-flash (the analysis itself is a measured, cost-tracked experiment). |

## Data Pipeline & Maintenance

| Script | Lines | Purpose |
|--------|-------|---------|
| `inventory.py` | 392 | Reads opencode.db, worktrees, results JSONs, config YAMLs. Commands: `refresh`, `list`, `stats`, `worktrees`, `report`. |
| `agentic_dynamics/core/constants.py` | — | Shared constants (DB path, result dirs, model configs). Was `scripts/_constants.py`; moved into the package in Stage 1. |
| `build_data.py` | 1188 | Produces `window.DYNAMICS_DATA` with provenance-tagged [M]/[C]/[H]/[P]/[X] measurements for the website. Includes a `routing` section from `agentic_dynamics.control.routing.compute_routing`. |
| `sync_data.py` | 290 | Normalizes every `stories/*.json` result into `sessions.parquet` + `stories.parquet` for clean querying; run before `build_data.py`. |
| `generate_manifest.py` | 79 | Generates `data_manifest.json` — schema version, file SHA256s, git commit, opencode version, known limitations. |
| `backfill_artifacts.py` | 264 | Copies generated code from `/tmp/exp_*` to `experiments/results/reports/`. Extracts session transcripts from SQLite. |
| `backfill_story_transcripts.py` | 135 | Recovers per-session `session_{n}.jsonl` transcripts for story worktrees from `opencode.db` (merges `(fork #N)` continuations). Writes to `experiments/results/stories/transcripts/`. |
| `backfill_story_artifacts.py` | 90 | Copies generated source code from story worktrees (`/tmp/story_*`) into persistent storage. |
| `backfill_costs.py` | 265 | Fixes story result costs + test metrics from the opencode DB + worktrees (repairs an old, buggy cost parser). |
| `backfill_deep_metrics.py` | 75 | Adds LSP + solution + basin + strategy metrics to existing analysis files. |
| `backfill_sonar.py` | 228 | Non-destructive SonarQube backfill — enriches existing results with code quality metrics via Docker `sonar-scanner`. |
| `regen_typescript_ssg.py` | 172 | Reconstructs TypeScript SSG worktrees from opencode DB part records. |
| `batch_analyze_ts_ssg.py` | 159 | Runs `analyze_worktrees` on just the typescript_ssg worktrees. |
| `recovery_cost_table.py` | 87 | Extracts baseline vs perturbed cost by operator×strength from DB. |
| `enqueue.py` | 209 | Fills Redis `story_jobs` queue (30 cells) + seeds `story_status` hash. |
| `worker.py` | 193 | `BRPOP` worker: runs `run_story.py`, sets `FINOPS_CELL_ID`, publishes status transitions to Redis. |
| `kb_worker.py` | 204 | Knowledge-base ingestion worker — runs a named consumer group (`kb-chroma-v1` / `kb-neo4j-v1` / `kb-ledger-v1`) against the Redis Streams change plane (`kb:v1:changes`, DB 2 on 6380), structurally parallel to `worker.py`. Reclaims stale messages, XACKs only after the destination confirms the idempotent upsert keyed by `knowledge_id`, dead-letters after capped retries. |
| `kb_produce.py` | 191 | Batch producer for the knowledge base — `load_results` → `derive_records` → `record_to_artifact` (writes the per-record `experiments/results/kb/<knowledge_id>.json`) → `record_to_event` → `publish_event` onto `kb:v1:changes` (DB 2 on 6380). `--dry-run` previews the would-emit count + samples, best-effort deduping against the checkpoint hash (degrades to the raw count when Redis is down); `--limit N` caps; `--repository-id` scopes `entity_id`. Idempotent via the `CHECKPOINT_KEY` hash (`knowledge_id` is the idempotence key). Sets `FINOPS_KB_WRITE=1` (the `publish_event` write guard) for the run. |
| `kb_produce_sources.py` | 337 | Batch producer for the code / quality / policy / spec sources (sibling of `kb_produce.py`) — `derive_code_records` / `derive_quality_records` / `derive_policy_records` / `derive_spec_records` → the same pointer contract (`record_to_artifact` → `record_to_event` → `publish_event`) onto `kb:v1:changes` (DB 2 on 6380). `--source {code,quality,policy,spec,all}`, `--limit N`, `--repository-id`, `--revision`. Idempotent via the `CHECKPOINT_KEY` hash; sets `FINOPS_KB_WRITE=1` (the write guard) for the run. The `spec` source reads the generated `experiments/specs/index.json` and is the only one that can emit `operation=supersede` (same-entity version chain → `generate_manifest.py`'s `lifecycle_state`). |
| `monitor.py` | 144 | Redis queue dashboard. `--watch` live, `--json` machine output (used by `apps/control_room/` dashboard). |
| `supervise.py` | 378 | Supervises running opencode sessions via a dedicated flash monitor session — flag-only, never steers. CLI for `agentic_dynamics/control/supervisor.py`'s Redis contracts. |
| `claude_agents_supervisor.py` | 260 | Supervises `claude --bg` background sessions — roster + owned-session relay only, structurally parallel to `supervise.py` but simpler. |

## Lab Books (20 scripts — 8 core, 12 quarantined — + 8 deprecated)

**Classification: `scripts/lab_manifest.json`** (schema `lab-manifest/v1`), parsed by the typed
loader `agentic_dynamics.reporting.lab_manifest` and guarded by `tests/test_lab_manifest.py`.
Every lab carries `lab_status: canonical | historical | quarantined` + `publication_eligible`.
Note the axis: this is *not* the `historical:` bucket of the script-classification manifest above
(which says "a lab book, not a maintained command") — it says *which corpus a lab reads*.

The quarantine is the semantic-integrity release's item 1
(`docs/review/semantic_integrity_review.md` P0): a lab that reaches the **retired**
`experiments/results/_results_summary.json`, directly or transitively, is quarantined —
`reproduce.sh` does not run it (its default set is derived from the manifest) and `build_data.py`
does not publish it (rejections are logged by lab name). The file stays, and
`agentic-dynamics analyze lab <name>` still runs it by hand.

**The canonical lab contract (item 2).** A publication-eligible lab obeys two rules, enforced in
code (`tests/test_lab_contract.py`):

1. **One input door** — `agentic_dynamics.reporting.canonical_corpus.load_canonical_tables()`,
   the registry resolver over `experiments/data_manifest.json`. Only `lifecycle_state ==
   "current"` rows; the registry chooses the payload files, so tombstoned/superseded records and
   stray directory contents cannot enter. No `_results_summary.json`, no `stories/*.json` glob.
2. **Embedded lineage** — the output JSON carries a `lab_contract` block
   (`agentic_dynamics.reporting.lab_contract`) with `input_dataset_id`,
   `input_manifest_sha256`, `registry_version`, `metric_definition_version`,
   `data_integrity_policy`, `requires_external_service`. `build_data.py` re-computes the current
   registry identity and **rejects a stale artifact**, logging the lab name and the reason.

The identity hash covers `schema_version` + the `registry` array — deliberately not the whole
manifest file, because the manifest records `data.js`'s hash and publishing would otherwise
invalidate the very labs it just published.

| Script | Status | Question Answered | Key Output |
|--------|--------|-------------------|------------|
| `lab_cache_economics.py` | canonical | What is cache hits worth in dollars/rework? | Cache-hit economics from session transcripts |
| `lab_grit.py` | canonical | **Grit** — how much test-executed success survives perturbation? | `G(s) = P(test_executed_success \| perturbation_strength = s)` per strength, model, class |
| `lab_condition_effects.py` | canonical | Do perturbation conditions move outcome metrics? | CLEAN/BAD_SEED/EARLY/LATE_DEGRADE comparison |
| `lab_quality_frontier.py` | canonical | Where is the quality-per-cost frontier? | Pareto frontier across correctness/cost/maintainability |
| `lab_story_arc.py` | canonical | How does a story's quality/cost arc evolve? | Per-session trajectory over the 5-session story |
| `lab_story_review.py` | canonical | What review patterns emerge across stories? | Per-story review aggregation |
| `lab_verification_frontier.py` | canonical | What verification depth buys what correctness? | Verification-effort vs verified-outcome frontier |
| `lab_verification_value.py` | canonical | Is independent verification worth its cost? | Agent-authored vs independent-evaluator delta |
| `lab_basin_topology.py` | quarantined | What is each model's attractor basin topology? | Shallow/broad, deep/narrow, multi-modal, flat classifications |
| `lab_basin_topology_neo4j.py` | quarantined | What is basin topology via Neo4j? | Graph-based attractor basin classification (Neo4j nodes are summary-loaded) |
| `lab_claude_audit.py` | quarantined | Where did Claude's $47.54 go? | Per-task cost/correctness/LOC/narration penalty |
| `lab_correctness_premium.py` | quarantined | Does Claude's premium buy anything? | Head-to-head correctness on 13 overlapping task types |
| `lab_flail_triggers.py` | quarantined | What makes a model flail? | Failure patterns by model, perturbation class, task type |
| `lab_correctness_escape_quadrants.py` | quarantined | What does correctness × escape × cost look like? | 2D bubble chart data (renamed from `lab_correctness_escape_quadrants.py` in s4; quadrant `high_grit` → `robust`) |
| `lab_opencode_meta_analysis.py` | quarantined | What patterns in opencode experiments? | Meta-analysis (also spends live inference) |
| `lab_sonar_quality.py` | quarantined | What code quality signals exist? | Sonar-based code quality analysis (stdout only) |
| `lab_survival_horizon.py` | quarantined | How many sessions before bankruptcy? | Sessions-to-exhaustion per model, per budget |
| `lab_task_routing.py` | quarantined | What's the optimal model-per-task routing? | 3 routing strategies simulated across 30 task types |
| `lab_think_do_coupling.py` | quarantined | How coupled are thinking and doing? | Think/do phase dynamics from trajectory data |
| `lab_tool_archetypes.py` | quarantined | Does tool choice predict code quality? | Write-dominant vs bash-dominant vs balanced patterns |

Deprecated (`*_DEPRECATED_bge_m3`, 8 scripts): drift_trajectories, reasoning_volatility,
cross_model_reasoning, divergence_cascades, cluster_stability, recovery_curves,
reasoning_divergence, semantic_clusters. Superseded by `semantic_validation.py`.

## Control Room Portal (`apps/control_room/`)

| File | Purpose |
|------|---------|
| `apps/control_room/server.py` | Flask backend — the **Control Room portal**, 28 routes across 5 API categories plus the static shell (below). Serves `apps/control_room/static/`. Port 8000 (`FINOPS_PORT`). |
| `apps/control_room/static/` | Vanilla-JS dashboard: Matrix grid, Cell Inspector (live transcript), Routing board, supervisor flags, design sessions, Claude background sessions. |

`apps/control_room/server.py`'s 28 routes, categorized:
- **Legacy telemetry** (6): `/api/matrix`, `/api/status` (SSE), `/api/events/<cell_id>` (SSE), `/api/routing`, `POST /api/experiments`, `POST /api/queue/reinterleave`
- **Supervisor flags** (3): `/api/flags`, `POST /api/flags/<session_id>/steer`, `POST /api/flags/<session_id>/interrupt`
- **Registry** (2): `/api/registry`, `/api/registry/<entity_id>`
- **Design sessions** (7): `/api/design-sessions`, `POST /api/design-sessions`, `/api/design-sessions/<portal_id>/spec`, `POST /api/design-sessions/<portal_id>/input`, `POST /api/design-sessions/<portal_id>/interrupt`, `POST /api/design-sessions/<portal_id>/save`, `POST /api/design-sessions/<portal_id>/run`
- **Claude background sessions** (9): `/api/claude-agents`, `POST /api/claude-agents`, `/api/claude-agents/<session_id>/logs`, `POST /api/claude-agents/<session_id>/stop`, `POST /api/claude-agents/<session_id>/respawn`, `POST /api/claude-agents/<session_id>/rm`, `POST /api/claude-agents/<session_id>/steer`, `/api/claude-agents/daemon`, `POST /api/claude-agents/daemon/stop`
- **Static shell** (1): `GET /`

Full endpoint reference: `docs/designs/current/supervisor_design.md`, `docs/spec.md`.

The portal is a human-facing live dashboard; the control-plane agent pulls state via `.opencode/tools/dashboard.ts` (which calls `monitor.py --json`) and `.opencode/tools/control_room.ts` (§3.1, read-only GET routes only). No agent-callable tool wraps the `POST` steer/interrupt/control routes — those are human-operator-only, by design (see `supervisor.ts`/`control_room.ts` in §3.1). No events are pushed back into opencode — Redis is the single shared state.

## Spec/Compiler (written)

`compile_experiment.py` (`agentic_dynamics/experiment/compile_experiment.py` — not in `scripts/`, no standalone
CLI) compiles an `ExperimentSpec` into a DAG (validate → cells → execute → measure → compare →
writeup → adapt) and generalizes the existing transport:

| New kind | Generalizes / replaces |
|---|---|
| `experiment_matrix` | `_gen_matrix_cells` (`pipeline.py:394`) + `enqueue.py` matrix |
| `experiment_run` | `enqueue.py` + `worker.py` + `run_story.py` (unchanged) |
| `evaluate_rules` | the 19 lab books, driven by `spec.rules` |
| `compare_arms` | `routing.simulate_strategies` (`routing.py:98`) |
| `writeup` | lab-book template from `spec.question` + metrics |
| `adapt` | new campaign loop — tweak one factor, emit next grid |

Ordering: instrument `confidence` (plus `answer`/`explanation` token split, attempt/timestamp
fields) before authoring `model_cascade`/`dynamics` control arms — the validator refuses unmet
`requires`. `confidence` is now measured ([H] per-attempt, `src/agentic_dynamics/adapters/opencode.py:113`),
so those arms are writable. Design: `docs/designs/current/2026-08-14_experiment-spec-and-compiler-design.md`.
