# File map, signatures, and dependencies. No theory. No methodology.

## Architecture
```
perturb.py → backends.py → opencode.py / claude_adapter.py → [LLM] → trajectory.py
                        ↓
solution.py + basin.py + efficiency.py + recovery.py → strategy.py → game_report.py

story.py ── mutation.py, commit_analysis.py, review.py, entropy.py, codebase_graph.py, lsp_diagnostics.py
routing.py ── recommend model per task type from experiment results
live.py ──── Redis pub/sub telemetry (feeds admin portal)
```

## Dependencies
language.py is foundation (no internal deps) → mutation → story → opencode.
Core measurement chain (perturb, opencode, trajectory, solution, efficiency, basin, strategy, game_report) is standalone.
Everything re-exported through `__init__.py`.

Backend seam: `backends.py` routes `anthropic/*` → `claude_adapter.py` (Claude CLI, subscription-safe),
everything else → `opencode.py`. Both emit opencode-format JSONL and return `AgenticResult`.
`streaming.py` provides the shared line-by-line subprocess runner both backends use.
`live.py` publishes events/status to Redis (env-driven via `FINOPS_CELL_ID`).

## Key Signatures
```
run_opencode_agentic(prompt, *, model, thinking_effort, thinking_budget_tokens,
                     output_token_limit, timeout, silent_mode, enforce_pytest, workdir) -> AgenticResult

perturb_prompt(prompt, operator_name, strength, *, rng_seed) -> (str, Perturbation)

evaluate_solution(code, *, constraints, baseline_code, language,
                  run_pytest, workdir, test_timeout) -> SolutionMetrics

measure_basin_escape(baseline_solution, perturbed_solution, *,
                     baseline_metrics, perturbed_metrics, language) -> BasinMetrics

compute_efficiency(result, *, model, baseline_metrics) -> EfficiencyMetrics
  PROVIDER_PRICING: dict of per-model cost rates

classify_strategy(reasoning, solution, efficiency) -> StrategyReport

run_story(story, *, model, condition, codebase_path, output_dir, compiler_model) -> StoryResult
  PerturbationCondition: CLEAN, BAD_SEED, EARLY_DEGRADE, LATE_DEGRADE
  BUILTIN_STORIES: task_manager_story, static_site_gen_story, notification_service_story

compile_mutation(spec, operator, strength, *, codebase_path, model, cache_dir) -> MutationArtifact
apply_mutation(artifact, target_path) -> bool

analyze_commit(worktree, commit_hash, language, baseline_ast) -> CommitAnalysis
review_commit(worktree, commit_hash, *, model, timeout) -> CommitReview
compute_entropy(codebase_path, *, language) -> EntropyProfile
build_graph(codebase_path, *, language) -> CodebaseGraph
run_diagnostics(codebase_path, *, language) -> LSPReport
detect_language(path) -> LanguageProfile
parse_codebase(path, profile) -> CodebaseAST

stream_subprocess(cmd, *, workdir, timeout, on_line) -> StreamResult

run_claude_agentic(prompt, *, model, thinking_effort, thinking_budget_tokens,
                   output_token_limit, timeout, workdir) -> AgenticResult

run_agentic(prompt, *, model, backend, **kwargs) -> AgenticResult
get_backend_for_model(model) -> "opencode" | "claude_cli"

LivePublisher(cell_id).publish_status(status) / .publish_event(event)
make_publisher() -> LivePublisher | None

compute_routing(entries) -> dict   # per-task recs + strategy simulation
recommend_route(task_type, entries, *, correctness_threshold, lead_margin) -> dict
```

## Script map
```
scripts/run.py            — experiment: perturb → invoke → evaluate
scripts/run_story.py      — multi-session story CLI
scripts/analyze_worktrees.py — worktrees → GameReport .md + _results_summary.json
scripts/analyze_trajectories.py — session.jsonl → trajectory JSON
scripts/inventory.py      — refresh, list, stats, worktrees, report
scripts/build_data.py     — inventory+results → firebase/public/data.js
scripts/validate_session.py — pytest on generated code
scripts/enqueue.py + worker.py — Redis experiment queue
scripts/backfill_artifacts.py + backfill_sonar.py — data migration
scripts/monitor.py        — Redis queue dashboard (--json for machine output)
scripts/generate_manifest.py — SHA256 manifest
scripts/pipeline.py       — YAML-driven phase orchestration (plans.yaml; 11 kinds)
scripts/plan.py           — [deprecated] hardcoded phase orchestration, superseded by pipeline.py
14 scripts/lab_*.py       — ignore *_DEPRECATED_bge_m3

admin/server.py           — Flask portal: SSE telemetry + routing (port 8000, FINOPS_PORT)
.opencode/tools/dashboard.ts — pull tool: Redis status matrix via monitor.py --json
```

## Test files
```
tests/test_story.py (330L), test_mutation.py (193L), test_commit_analysis.py
test_codebase_graph.py, test_language.py, test_entropy.py
test_review_agent.py, test_lsp.py (188L), test_opencode_events.py
test_trajectory_embedding.py, test_embeddings.py, test_perturb.py
test_recovery.py, test_pricing.py, test_ollama_analyzer.py
test_opencode_analyzer.py, test_correctness_lineage.py, test_solution.py
test_adapter.py, test_graph.py
test_streaming.py, test_claude_adapter.py, test_backends.py, test_live.py, test_routing.py
```

## Navigation
```
Task: instrument logic → Read src/instrument/CONTEXT.md
Task: experiments     → Load skill: instrument
Task: analysis        → Load skill: analyze
Task: lab books       → Load skill: lab-books
Task: pipeline        → Read scripts/CONTEXT.md
Task: website         → Read firebase/CONTEXT.md
Task: configs         → Read experiments/CONTEXT.md
```
