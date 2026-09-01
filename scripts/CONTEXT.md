# `scripts/` — Scripts Reference (classification manifest)

75 command scripts plus two helper modules (`_bootstrap.py`, `_gen_instructions.py`), each
command in exactly one bucket (critique rec 5). The classification below is machine-parsed by
`tests/test_script_classification.py` — keep the marker lines intact. The `one-time` bucket
lives under `scripts/archive/`; the other buckets live at the top of `scripts/`.

<!-- scripts-classification: start -->
maintained: retro_session_routing.py evidence_prereq_gate.py cap_cascade_retrospective.py cap_coverage_routing_impact.py run.py sweep_parallel.py sweep_silent_mode.py batch_run.py remaining_batch.py multi_phase.py run_story.py batch_stories.py run_workflow.py record_discarded_tree.py enqueue.py worker.py monitor.py reinterleave_queue.py enqueue_analysis.py analysis_worker.py analyze_worktrees.py analyze_trajectories.py analyze_stories.py build_data.py check_branch_protection.py sync_data.py generate_manifest.py inventory.py kb_produce.py kb_produce_sources.py kb_produce_facts.py kb_produce_campaign_evidence.py kb_worker.py registry.py review_all.py review_stories.py trigger_reviews.py enqueue_reviews.py finalize_reviews.py spec_status.py subscription_usage.py pipeline.py validate_session.py verify_tests.py supervise.py claude_agents_supervisor.py orphan_sweep.py context_snapshot_report.py shadow_decision_report.py decision_arm_comparison.py run_cap_grit_grid.py measure_cap_grit_grid.py run_cap_2c_grid.py score_cap_2c.py run_cap_2d_grid.py score_cap_2d.py site_census_check.py run_cap_2e_grid.py score_cap_2e.py run_cap_2f_grid.py score_cap_2f.py graph_family_build.py graph_family_wall.py graph_family_preverify.py lease_watchdog.py
maintained: retro_session_routing.py evidence_prereq_gate.py cap_cascade_retrospective.py cap_coverage_routing_impact.py run.py sweep_parallel.py sweep_silent_mode.py batch_run.py remaining_batch.py multi_phase.py run_story.py batch_stories.py run_workflow.py record_discarded_tree.py enqueue.py worker.py monitor.py reinterleave_queue.py enqueue_analysis.py analysis_worker.py analyze_worktrees.py analyze_trajectories.py analyze_stories.py build_data.py bundle_artifacts.py check_branch_protection.py sync_data.py generate_manifest.py inventory.py kb_produce.py kb_produce_sources.py kb_produce_facts.py kb_produce_campaign_evidence.py kb_worker.py registry.py review_all.py review_stories.py trigger_reviews.py enqueue_reviews.py finalize_reviews.py spec_status.py subscription_usage.py pipeline.py validate_session.py verify_tests.py supervise.py claude_agents_supervisor.py orphan_sweep.py context_snapshot_report.py shadow_decision_report.py decision_arm_comparison.py run_cap_grit_grid.py measure_cap_grit_grid.py run_cap_2c_grid.py score_cap_2c.py site_census_check.py sync_surfaces.py system_snapshot.py aggregate_workflow_metrics.py lease_watchdog.py
maintained: retro_session_routing.py evidence_prereq_gate.py cap_cascade_retrospective.py cap_coverage_routing_impact.py run.py sweep_parallel.py sweep_silent_mode.py batch_run.py remaining_batch.py multi_phase.py run_story.py batch_stories.py run_workflow.py record_discarded_tree.py enqueue.py worker.py monitor.py reinterleave_queue.py enqueue_analysis.py analysis_worker.py analyze_worktrees.py analyze_trajectories.py analyze_stories.py build_data.py check_branch_protection.py sync_data.py generate_manifest.py inventory.py kb_produce.py kb_produce_sources.py kb_produce_facts.py kb_produce_campaign_evidence.py kb_worker.py registry.py review_all.py review_stories.py trigger_reviews.py enqueue_reviews.py finalize_reviews.py spec_status.py subscription_usage.py pipeline.py validate_session.py verify_tests.py supervise.py claude_agents_supervisor.py orphan_sweep.py context_snapshot_report.py shadow_decision_report.py decision_arm_comparison.py run_cap_grit_grid.py measure_cap_grit_grid.py run_cap_2c_grid.py score_cap_2c.py run_cap_2d_grid.py score_cap_2d.py site_census_check.py run_cap_2e_grid.py score_cap_2e.py run_cap_2f_grid.py score_cap_2f.py measure_delta_entropy.py compute_coordination_overhead.py lease_watchdog.py
maintained: retro_session_routing.py evidence_prereq_gate.py cap_cascade_retrospective.py cap_coverage_routing_impact.py run.py sweep_parallel.py sweep_silent_mode.py batch_run.py remaining_batch.py multi_phase.py run_story.py batch_stories.py run_workflow.py record_discarded_tree.py enqueue.py worker.py monitor.py reinterleave_queue.py enqueue_analysis.py analysis_worker.py analyze_worktrees.py analyze_trajectories.py analyze_stories.py build_data.py bundle_artifacts.py check_branch_protection.py sync_data.py generate_manifest.py inventory.py kb_produce.py kb_produce_sources.py kb_produce_facts.py kb_produce_campaign_evidence.py kb_worker.py registry.py review_all.py review_stories.py trigger_reviews.py enqueue_reviews.py finalize_reviews.py spec_status.py subscription_usage.py pipeline.py validate_session.py verify_tests.py supervise.py claude_agents_supervisor.py orphan_sweep.py context_snapshot_report.py shadow_decision_report.py decision_arm_comparison.py run_cap_grit_grid.py measure_cap_grit_grid.py run_cap_2c_grid.py score_cap_2c.py site_census_check.py sync_surfaces.py system_snapshot.py measure_delta_entropy.py compute_coordination_overhead.py lease_watchdog.py
historical: lab_grit.py lab_beta_from_corpus.py lab_basin_topology.py lab_basin_topology_neo4j.py lab_cache_economics.py lab_claude_audit.py lab_condition_effects.py lab_correctness_premium.py lab_flail_triggers.py lab_correctness_escape_quadrants.py lab_opencode_meta_analysis.py lab_quality_frontier.py lab_sonar_quality.py lab_story_arc.py lab_story_review.py lab_survival_horizon.py lab_task_routing.py lab_think_do_coupling.py lab_tool_archetypes.py lab_verification_frontier.py lab_verification_value.py
one-time: backfill_artifacts.py backfill_story_artifacts.py backfill_story_transcripts.py backfill_deep_metrics.py batch_analyze_ts_ssg.py finish_sweep.py regen_typescript_ssg.py backfill_sonar.py backfill_costs.py compute_sonar_deltas.py embed_sessions.py recovery_cost_table.py rescore_conventions.py recover_stories.py kb_produce_registry.py retract_payloadless_stories.py compute_qualitative_routing.py
fleet: dlq.py egress_proxy.py fleet_manager.py heartbeat.py probe_binaries.py review_unit.py spawn_wrapper.py dlq_triage.py retrieval_census.py
maintained: scan_docs_drift.py docs_drift_watchdog.py docs_proposal_gate.py
<!-- scripts-classification: end -->

- **maintained command** — reached via `agentic-dynamics <subcommand>` (the Stage 3 CLI).
- **historical analysis** — the 19 active lab books, reached via `agentic-dynamics analyze lab <name>`.
- **one-time migration** — archived to `scripts/archive/` (fold WS-10), not maintained.
- **fleet runtime module** — the fleet-ladder support modules under `scripts/fleet/` (the fleet
  manager, heartbeats, DLQ, the egress proxy, the binary probe, the review unit, and the
  sibling-spawn wrapper). Not CLI commands — they are invoked by the docker-compose services.
- **archive lint policy** (decided in `cap_stabilization_release` p2, hard rule 3) — the
  `one-time` bucket is IMMUTABLE HISTORICAL MATERIAL (frozen migrations, never re-run), but it
  is kept ruff-clean rather than excluded: its findings were trivial auto-fixes (unused imports
  + import sorting, zero semantic change), so `ruff check scripts/` stays exception-free and
  the adversarial reviewer sees a clean tree, not a carve-out. The per-file-ignores exclusion
  was rejected because ruff 0.16 has no catch-all selector (`"*"` is refused) — exclusion
  would mean listing rule codes, a fragile, widening-prone exception. Keep future archive
  additions lint-clean. *(This note was dropped when merge `26eb0e32b` reverted CONTEXT.md to
  main's version mid-campaign; restored by `cap_stabilization_release` p2-recheck.)*
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
| `check_branch_protection.py` | Release-time drift check: compares the live GitHub branch protection for `main` against the committed settings doc (`docs/release/branch_protection_settings.md`); exit 1 on drift | Before any release; run after any manual protection change |

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
| `run_workflow.py` | 434 | Runs an `agent_task` workflow (the execute phase) against a goal inside a git worktree; wrapped by the `run_workflow` tool (§3.1). Refreshes the spec status index (best-effort) after writing the run ledger. Runner hardening (cap_runner_hardening): `--phase-watchdog-min MIN` (phase stall watchdog — a session transcript silent for MIN minutes is SIGTERM'd and the phase fails `STALLED`; default `FINOPS_PHASE_WATCHDOG_MIN` env, else 20, 0 disables); `deploy_allowed: true` per-phase marker (default false — a phase that runs `firebase deploy` without it fails `DEPLOY_GATE`); commit-prefix enforcement (a manual commit during a phase that does not match `[workflow] <phase> — <goal prefix>` fails `COMMIT_PREFIX`). Runner hardening 2 (cap_runner_hardening2): the relabel tree-identity gate — post-phase the committed tree is compared against the discarded-trees ledger (`experiments/results/workflows/<spec>/discarded_trees.jsonl`, written by `workflow discard-tree` / `record_discarded_tree.py`); a discarded tree re-presented fails `RELABEL` with the identical-tree proof unless an operator-signed `approvals/<spec>/<phase>_tree_reuse.md` (committed before the phase) authorizes the reuse; the mechanical human checkpoint — a phase declaring `checkpoint: true` that succeeds stops the run with `awaiting_operator_approval` (phase status `awaiting`, exit 0), and a `--resume` refuses to proceed past an unsatisfied checkpoint unless `approvals/<spec>/<phase>_approval.md` is committed after the checkpoint commit with a real operator signature + date. The server-level orphan sweep (a sibling hardening, `orphan_sweep.py`) lives in the opencode session layer the runner cannot see. |
| `run_cap_grit_grid.py` | ~290 | E4 live-grid executor — runs `cap_grit_strength_grid` cells sequentially on sonnet-5 via `claude_cli` (story `task_manager_api`), applies the grit_retry policy, writes `LEDGER_FIELDS` attempt rows into `experiments/results/cap_grit_grid_ledger.json`, commits per cell, STOPs cleanly on Claude usage-cap errors (resumable). `--cell N` single-cell, `--dry-run` plan. |
| `measure_cap_grit_grid.py` | ~290 | E4 grid measurement — runs the spec's registered rules over `cap_grit_grid_ledger.json` via the compile evaluator (attempt_coverage_precheck, grit, verified_success_rate, cost_per_verified_outcome, rework_cost_report, retry_policy_fidelity, arm_comparison) into `experiments/results/cap_grit_grid_metrics.json`. Coverage-first: ratios reported before any denominator use; no fabricated attempts. |
| `run_cap_2c_grid.py` | 578 | `cap_adaptive_2c` p2 grid executor — runs the remaining cells of the pre-registered assignment table (24 cells, 6 stimulus classes × 2 arms), each in a fresh worktree with a unique `FINOPS_CELL_ID`: proposal emitted + validated BEFORE the outcome, static = recorded never applied, adaptive = applied exactly as proposed (rework = ONE bounded pass, verify = one pass, continue = null). Absent-class cells exercise the seam's refuse path in the designed degraded state. Writes per-cell records to `experiments/results/cap_adaptive_2c/cells/` + durable proposals to `.../proposals/`. Resumable (skips recorded cells); `--cell <id>` single-cell, `--dry-run` plan. |
| `score_cap_2c.py` | ~790 | `cap_adaptive_2c` p3 scorer — scores the heterogeneous grid from immutable p1/p2 artifacts only: join-validates every cell against the pre-registered table (a mismatch is invalid, not corrected), then emits `experiments/results/cap_adaptive_2c/cap_adaptive_2c_score_<ts>.json` (schema `cap_adaptive_2c_score/v1`): per-cell rows + per-arm aggregates + per-CLASS breakdown (cpvo + hit/harm per stimulus class) + the HARM table (wrong-apply measured, wrong-continue E_x-scaled at 11.47/28) + the ABSTENTION analysis (per-confidence-decile value(apply) vs value(abstain), the threshold curve, EXPLORATORY) + the decision-rule computation vs the pre-registered margin, plus a validation JSON tracing every verdict number to a field. `--dry-run` prints the tables, writes nothing. |
| `run_cap_2d_grid.py` | ~860 | `cap_adaptive_2d` p1+p2 grid executor — measures E1 (cap2d_correct_abstention_r1) + the incorrect_rebuilt impacted pre-verification probe (`--p1`), then runs the 28-cell abstention grid at 4-wide concurrency per the pre-registered assignment table. Per cell: fresh worktree + unique FINOPS_CELL_ID, candidate manifest FIRST, proposal emitted + validated BEFORE the outcome, the ABSTENTION decision shadow-evaluated per the pinned §0 table (DECLINE legs 1-3 / APPLY / APPLY-NULL; the abstention arm acts, status_quo applies exactly as proposed), independent pytest + post-hoc evaluator outcomes, durable proposals. Resumable (skips recorded cells); `--cell <id>` single-cell, `--dry-run` plan. |
| `score_cap_2d.py` | ~800 | `cap_adaptive_2d` p3 scorer — scores the 28-cell abstention grid from immutable p1/p2 artifacts only: join-validates every cell against the pre-registered table (a mismatch is invalid, not corrected), then emits `experiments/results/cap_adaptive_2d/cap_adaptive_2d_score_<ts>.json` (schema `cap_adaptive_2d_score/v1`): per-cell rows + per-arm aggregates + per-CLASS breakdown + the HARM table (wrong-apply within-campaign, wrong-continue E_x-scaled at 11.47/28) + the ABSTENTION DECISION-RULE computation (the four pre-registered legs: primary cpvo_harm comparison, capture rate on the low-information cells, flag-cost vs saved escape harm, the reused NI guard) + the confidence curve (EXPLORATORY — the rule stays confidence-free), plus a validation JSON tracing every verdict number to a field. `--dry-run` prints the tables, writes nothing. |
| `site_census_check.py` | | Mechanical preservation-gate census checker for apps/website/ — re-counts the incumbent feature census on the CURRENT committed source and compares every headline count against the baseline artifact (the revamp4 preservation contract). `--dry-run` plan. |
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
| `retro_session_routing.py` | 187 | Replays the workflow-run phase corpus as counterfactual session-policy arms (`continue`/`fork_cached`/`fork_blind`/`escalate`) — the evidence-seed study for `cap_session_routing_evidence.yaml`. Writes `session_routing_retrospective.json`. |
| `cap_cascade_retrospective.py` | ~290 | E2 confidence-gated cascade retrospective evaluator — runs `cap_confidence_cascade.yaml`'s measurement rules (confidence_coverage_precheck, escalation_trigger, cascade_cost_per_verified_outcome, arm_comparison) over the F1-sanitized workflow-run corpus into `cap_cascade_retrospective.json`. RETROSPECTIVE ONLY: escalation is counterfactual, never applied; `routing_arm_regret_theta_*` is 0.0 by construction (tautology) and `null_testable_theta_*` is the honest flag. |
| `cap_coverage_routing_impact.py` | ~330 | E3 coverage-impact re-run — `cap_coverage_routing_impact.yaml`'s rules over `canonical_corpus.resolve_findings()` (64 current finding rows): coverage-corrected `compute_routing` (as-is) vs the re-derived legacy zero-default formula (`lab_task_routing.py`'s aggregation), counting changed recommendations per task/model + direction, into `cap_coverage_routing_impact.json`. Reports BOTH raw key-presence coverage AND operational `cost_captured` coverage (the surface the formulas can actually diverge on); a null (zero changes) is a result, not a failure. |
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
| `bundle_artifacts.py` | ~330 | Artifact-governance bundle planner (external review P2) — implements the retention policy in `docs/designs/proposed/artifact_retention_policy.md`: scans `experiments/results/` and, by default (dry-run), prints the Tier-2 bundle-candidate inventory (path, size, sha256, age, reference-check). `--bundle-out <dir>` writes a content-addressed tar + committed manifest (member → sha256); `--prune` (operator-only, never the default) removes bundled members after re-verifying the manifest is git-tracked, member hashes match, the reference check passes (nothing referenced by `registry_index.jsonl` / `data_manifest.json`), and the in-flight age gate holds. `experiments/results/workflows/` is never a candidate. CLI: `agentic-dynamics data bundle`. |
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
| `kb_produce_facts.py` | 244 | Batch producer for the CAP fact plane (I1) — runs a registered reducer (`--reducer spec_status/v1`) over `experiments/specs/index.json` and persists the resulting `CanonicalFact`s through the existing pipe (`build_fact_record` → `record_to_artifact` → `record_to_event` → `publish_event`) onto `kb:v1:changes` (DB 2 on 6380) as `source_type="fact"`. `--dry-run` previews the would-emit count + samples; `--limit N`; `--repository-id`; `--revision`. Idempotent via the `CHECKPOINT_KEY` hash; sets `FINOPS_KB_WRITE=1`. Emits `operation=supersede` (same-entity version chain → `generate_manifest.py`'s `lifecycle_state`) when a fact's value changed since its last registration. |
| `kb_produce_campaign_evidence.py` | | Campaign-evidence producer — one [M] report per scored cell + aggregate from a cap_2a_score/v1 (or escalation/per-model) JSON: `record_to_artifact` (writes kb/<id>.json) -> `record_to_event` -> `publish_event` (DB 2 on 6380) + the registry row materialized at emit time (no live-consumer dependency). `--score <json> --campaign <name> [--dry-run]`. Sets `FINOPS_KB_WRITE=1`. |
| `context_snapshot_report.py` | ~100 | CAP I4's gate: aggregates admissibility/unknown/stale/conflict rates over every recorded `source_type="context_snapshot"` registry row (`experiments/data_manifest.json`) — read-only, no external dependency. `--json` for machine output. Zero rows (the default, until `run_workflow.py --cap-snapshot` is used) prints a note, not an error. |
| `shadow_decision_report.py` | ~50 | CAP I6's gate: agreement/divergence vs `step_routing` — reads `control.rules.load_shadow_decisions` (scans `KB_ARTIFACT_DIR` directly; never the registry — shadow decisions are `source_type="actuation"` artifacts deliberately never published, so `FINOPS_ACTUATION_ARMED` is never touched) and scores them via `compile_experiment.decision_calibration` (`decision_regret`). `--json` for machine output. Zero rows (until `run_workflow.py --cap-shadow`) prints a note, not an error. |
| `decision_arm_comparison.py` | ~120 | CAP I7's `compare_arms` hookup — the flip-decision evidence report: (1) `compile_experiment.compare_arms` over every REAL executed phase (`experiments/results/workflows/**/*.json`), grouped by `arm_factor="model"`, cost/quality loss; (2) `decision_calibration`'s agreement rate. Documents up front that shadow mode never independently measures the plane's own proposed outcome (only `step_routing`'s choice ever executes), so these are two complementary signals, not one fused arm comparison. `--json` for machine output. |
| `monitor.py` | 144 | Redis queue dashboard. `--watch` live, `--json` machine output (used by `apps/control_room/` dashboard). |
| `supervise.py` | 378 | Supervises running opencode sessions via a dedicated flash monitor session — flag-only, never steers. CLI for `agentic_dynamics/control/supervisor.py`'s Redis contracts. |
| `claude_agents_supervisor.py` | 260 | Supervises `claude --bg` background sessions — roster + owned-session relay only, structurally parallel to `supervise.py` but simpler. |
| `lease_watchdog.py` | ~180 | Lease-expiry watchdog (admission_leases p4) — sweeps the framework-Redis lease registry for expired admission leases and turns each into an advisory record: an expired CONCURRENCY lease becomes a supervisor flag (a worker outlived its execution slot); an expired BUDGET lease becomes a flag PLUS a quarantine entry against the run's worktree and results namespace (work that outlived its spend reservation produced unaccounted-for output — the audit's item 8). Durable `experiments/results/quarantine/quarantine.jsonl` + Redis `finops:quarantine:active` hash + `quarantine_events` hot list; flags share `supervise.py`'s `flags.jsonl` and `supervisor_flags` list. FLAG-ONLY — never kills, retries, resumes, or reschedules. The marks are consulted by the analyze chain (`analyze_worktrees.py`), the data chain (`inventory.py`) and the permanence gate (`system_snapshot.py`). Cadence `FINOPS_LEASE_WATCHDOG_INTERVAL` (default 300s); `--once` for one pass, `--json` for the machine report. Rules in `agentic_dynamics/control/lease_watchdog.py`, ledger in `agentic_dynamics/control/quarantine.py`. CLI: `agentic-dynamics supervise leases`. |
| `orphan_sweep.py` | ~170 | Server-level orphan sweep daemon (cap_runner_hardening2 §Gap 1) — observes the opencode session store read-only, detects orphaned delegations (a task whose parent session has no meaningful step after the spawn AND whose subagent terminated), records each as a dated, flagged event (durable `experiments/results/orphans/orphans.jsonl` + Redis `orphan_events` hot list + canonical registry `source_type=orphan`), reaps the orphaned subagent process if still alive, and surfaces the record. FLAG-ONLY (hard rule 2) — never restarts/retries/steers. Cadence `ORPHAN_SWEEP_INTERVAL` (default 300s); `--once` for one pass; core rule in `agentic_dynamics/control/orphan_sweep.py`. CLI: `agentic-dynamics supervise orphans`. |
| `record_discarded_tree.py` | ~80 | Relabel tree-identity gate's reset/rollback path (cap_runner_hardening2 §Gap 2) — records the tree a worktree is about to discard (`git rev-parse <commit>^{tree}`) onto the discarded-trees ledger `experiments/results/workflows/<spec>/discarded_trees.jsonl`, keyed (spec, branch, tree_hash, discarded_at); idempotent. The gate fails any phase whose committed tree is EXACTLY a recorded discarded tree (RELABEL + identical-tree proof) unless an operator-signed `approvals/<spec>/<phase>_tree_reuse.md` (committed before the phase) authorizes the reuse. FLAG-ONLY — records, never steers. CLI: `agentic-dynamics workflow discard-tree`. |
| `scan_docs_drift.py` | ~1370 | Deterministic docs-drift scanner (automatic_docs_sync p1) — the SOURCE-doc content rail, complementing the derived-surface regeneration rail. Re-derives each anchorable claim class from the code and compares it to what a source doc asserts, across six axes: `cli_surface` (documented flags/subcommands resolve — flags by AST over the backing script, subcommands through the real `cli._resolve`), `module_inventory` (ARCHITECTURE.md's plane table + its SHA-pinned module count, verified AT ITS PIN), `spec_lifecycle` (counts in the current-authority docs vs `experiments/specs/index.json`), `status_vocabulary` (mirrors `tests/test_doc_lifecycle.py`), `anchor_integrity` (every `file:line` anchor in ARCHITECTURE.md + `docs/architecture/current/` resolves to a file that has that line), `manifest_counts` (mirrors `tests/test_script_classification.py`). ZERO model calls — the only subprocess is read-only `git`; every finding carries a re-derivable `basis`. Emits a `docs-drift/v1` JSON report (findings + per-axis drift score). Reports, never edits — remediation is the proposal gate's call, not the scanner's. `--json PATH`, `--check AXIS`, `--fail-on-drift`, `--include-current`. CLI: `agentic-dynamics docs scan`. |
| `docs_drift_watchdog.py` | ~700 | Docs-drift watchdog (automatic_docs_sync p2) — the cadence + observation rail around `scan_docs_drift.py`. One pass scans in-process (zero model calls, inherited), writes `experiments/results/docs_drift/latest.json` + a `history.jsonl` trend line, resolves the flag lifecycle, and publishes the live board row. The flag is LEVEL state (`docs:drift:flag`, `flag_state.json`) with EDGE-triggered records: a durable `flags.jsonl` line, a push to the supervisor hot list, and an observation-rail record (`source_type=flag`, `FINOPS_KB_WRITE`-gated) are written only on a raise or a clear — so a week of unfixed drift is one flag, not 168. A scan that could not measure NEVER clears a raised flag (exit 2). The board row lands on `fleet:docs_drift` and is merged into `fleet:board` by `scripts/fleet/fleet_manager.py:_docs_drift_row`. Reports and flags, never edits — remediation is the p3 gate's call. Scheduled by `infrastructure/docs-drift-scan.{service,timer}`. `--check AXIS`, `--dry-run`, `--no-redis`, `--fail-on-drift`, `--results-dir`. CLI: `agentic-dynamics docs watch`. |
| `docs_proposal_gate.py` | ~1560 | Docs-drift proposal gate (automatic_docs_sync p3) — the policy over p1's instrument and p2's rail: **the machine proposes, the controller decides**. `propose` reads the watchdog's `latest.json`, and when stale+missing crosses the threshold (default >0) writes `proposal.json` (state `warranted`) surfacing the ready-made `docs_refresh_remediation` workflow with its budget estimate READ FROM THE SPEC (`stop.budget_usd`) — and **queues nothing** (`GateDecision.enqueued` is False on every propose path, by construction). `approve --by <who>` is the controller's explicit, attributed, durable signature (`approvals.jsonl` + the `docs:remediation:approved` mirror), bound to a `proposal_id` fingerprinting the *finding set* (not the git SHA), so a re-scan never invalidates a fresh signature but NEW drift does. `dispatch` is the only function that can enqueue: it refuses without a matching approval, then takes an `O_CREAT|O_EXCL` claim (`remediation.lock`) — the approve-runs-once mechanism — and submits through the existing `fleet:commands` path with the drift inventory as the run's goal context. A second approval while a run is in flight is a no-op (nothing recorded, nothing enqueued); a failed enqueue rolls the claim back; an expired claim is REPORTED, never auto-broken. `release --status completed|failed` is the manual terminal transition. A missing or unmeasured report yields `unmeasured` — it neither raises nor withdraws a proposal. The board row's `proposal_state`/`proposed_action` are resolved from `proposal.json` by `docs_drift_watchdog.build_board_row`. CLI: `agentic-dynamics docs gate status|propose|approve|dispatch|release`. |

## Lab Books (20 scripts — 8 core, 12 quarantined — + 8 deprecated)

**Classification: `scripts/lab_manifest.json`** (schema `lab-manifest/v1`), parsed by the typed
loader `agentic_dynamics.reporting.lab_manifest` and guarded by `tests/test_lab_manifest.py`.
Every lab carries `lab_status: canonical | historical | quarantined` + `publication_eligible`.
Note the axis: this is *not* the `historical:` bucket of the script-classification manifest above
(which says "a lab book, not a maintained command") — it says *which corpus a lab reads*.

The quarantine is the semantic-integrity release's item 1
(`docs/reviews/semantic_integrity_review.md` P0): a lab that reaches the **retired**
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
| `apps/control_room/server.py` | Flask backend — the **Control Room portal**, 31 routes across 6 API categories plus the static shell (below). Serves `apps/control_room/static/`. Port 8000 (`FINOPS_PORT`). |
| `apps/control_room/static/` | Vanilla-JS dashboard: Matrix grid, Cell Inspector (live transcript), Routing board, supervisor flags, design sessions, Claude background sessions. |

`apps/control_room/server.py`'s 31 routes, categorized:
- **Legacy telemetry** (7): `/api/matrix`, `/api/status` (SSE), `/api/events/<cell_id>` (SSE), `/api/routing`, `/api/subscription-usage`, `POST /api/experiments`, `POST /api/queue/reinterleave`
- **Supervisor flags** (3): `/api/flags`, `POST /api/flags/<session_id>/steer`, `POST /api/flags/<session_id>/interrupt`
- **Registry** (2): `/api/registry`, `/api/registry/<entity_id>`
- **Design sessions** (7): `/api/design-sessions`, `POST /api/design-sessions`, `/api/design-sessions/<portal_id>/spec`, `POST /api/design-sessions/<portal_id>/input`, `POST /api/design-sessions/<portal_id>/interrupt`, `POST /api/design-sessions/<portal_id>/save`, `POST /api/design-sessions/<portal_id>/run`
- **Claude background sessions** (9): `/api/claude-agents`, `POST /api/claude-agents`, `/api/claude-agents/<session_id>/logs`, `POST /api/claude-agents/<session_id>/stop`, `POST /api/claude-agents/<session_id>/respawn`, `POST /api/claude-agents/<session_id>/rm`, `POST /api/claude-agents/<session_id>/steer`, `/api/claude-agents/daemon`, `POST /api/claude-agents/daemon/stop`
- **Docs health** (2): `/api/docs-health`, `POST /api/docs-health/approve` — the docs-drift rail's surface (green/yellow/red + the controller's approve affordance; see `scripts/scan_docs_drift.py` → `docs_drift_watchdog.py` → `docs_proposal_gate.py`)
- **Static shell** (1): `GET /`

Full endpoint reference: `docs/architecture/current/supervisor_design.md`, `docs/architecture/current/spec.md`.

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
so those arms are writable. Design: `docs/architecture/current/2026-08-14_experiment-spec-and-compiler-design.md`.
