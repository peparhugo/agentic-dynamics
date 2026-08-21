---
name: lab-books
description: Running structured lab book analyses against accumulated experiment data. Each lab book answers a specific research question using _results_summary.json, inventory.json, and trajectory data. Contains full knowledge of all 19 active lab books and their data dependencies.
---

# Lab Books Skill — Full Lab Analysis Knowledge

You are running structured scientific analyses against the AI FinOps Dynamics experiment corpus. This skill injects knowledge of all lab books, their data dependencies, and common analysis patterns.

## Prerequisites (ALWAYS run these first)

```bash
python scripts/inventory.py refresh          # Rebuild inventory
python scripts/analyze_worktrees.py          # Regenerate _results_summary.json
python scripts/analyze_trajectories.py       # Regenerate trajectory aggregates
```

Lab books read from these files in `experiments/results/`:
- `_results_summary.json` — **RETIRED** (see the quarantine below) per-experiment solution + efficiency + strategy metrics
- `_trajectory_summary.json` — per-transcript step-level data
- `_trajectory_aggregate.json` — per-model trajectory aggregates
- `inventory.json` — experiment registry

## QUARANTINE — check `scripts/lab_manifest.json` before running or citing a lab

`experiments/results/_results_summary.json` is a **retired** corpus. Every lab that reaches it,
directly or transitively, is `lab_status: quarantined` in `scripts/lab_manifest.json`
(12 of the 20): it is **not** run by `scripts/reproduce.sh` and its output is **not** published to
the website. It still runs by hand — but its numbers are historical and must never be presented
as current findings or written into `apps/website/`.

The 8 canonical labs are: `cache_economics`, `condition_effects`, `grit`, `quality_frontier`,
`story_arc`, `story_review`, `verification_frontier`, `verification_value`.

**Grit has exactly one meaning:** `G(s) = P(test_executed_success | perturbation_strength = s)`,
implemented by `scripts/lab_grit.py`. Never use the word for the correctness x escape quadrants
(`lab_correctness_escape_quadrants.py`, quarantined).

```bash
python3 -m agentic_dynamics.reporting.lab_manifest --reproduce     # the core set
python3 -m agentic_dynamics.reporting.lab_manifest --quarantined   # the excluded set
```

## The canonical lab contract (writing or editing a publication lab)

A publication-eligible lab has exactly one input door and must declare its lineage:

```python
from agentic_dynamics.reporting.canonical_corpus import load_canonical_tables
from agentic_dynamics.reporting.lab_contract import attach_contract

tables = load_canonical_tables("story", "review")   # current registry rows only
output = compute(tables.stories, tables.reviews)
attach_contract(output, "lab_<name>.py", tables)    # embeds the 6 lineage fields
```

Never glob `experiments/results/{stories,reviews,analysis}/` in a publication lab — the registry
chooses the files. `build_data.py` recomputes the registry identity and rejects any lab JSON
whose embedded `input_manifest_sha256` is stale (logged by lab name), so a lab must be re-run
after the corpus changes. `metric_definition_version` is declared in `scripts/lab_manifest.json`,
not in the lab source.

Source: `docs/review/semantic_integrity_review.md` P0. The lab descriptions below still describe
the pre-quarantine world; the manifest is authoritative.

## Lab Books (19 total — 7 canonical, 12 quarantined)

### Cost & Pricing Analysis

**1. lab_claude_audit.py** (216L) — "Where did Claude's $47.54 go?"
- Per-task cost, correctness, LOC, narration penalty breakdown
- Compares Claude vs DeepSeek on overlapping tasks
- Output: `experiments/results/legacy_labs/lab_claude_audit.json`

**2. lab_correctness_premium.py** (202L) — "Does Claude's premium buy anything?"
- Head-to-head correctness on 13 overlapping task types
- Controls for perturbation class and strength
- Output: `experiments/results/legacy_labs/lab_correctness_premium.json`

### Behavioral Analysis

**3. lab_correctness_escape_quadrants.py** — "Correctness × escape × cost visualization" (renamed from lab_grit_matrix.py in s4; quarantined)
- 2D bubble chart data: x=escape, y=correctness, size=cost
- Per-model, per-perturbation class breakdown
- Output: `experiments/results/legacy_labs/lab_correctness_escape_quadrants.json`

**4. lab_flail_triggers.py** (183L) — "What makes a model flail?"
- Failure patterns by model, perturbation class, task type
- Identifies conditions where models fall into recovery loops
- Output: `experiments/results/legacy_labs/lab_flail_triggers.json`

**5. lab_tool_archetypes.py** (146L) — "Does tool choice predict code quality?"
- Write-dominant vs bash-dominant vs balanced tool usage patterns
- Correlates tool-call distributions with solution quality
- Output: `experiments/results/legacy_labs/lab_tool_archetypes.json`

### Strategy & Topology

**6. lab_task_routing.py** (235L) — "Optimal model-per-task routing"
- Simulates 3 routing strategies across 30 task types
- Cost-optimal, quality-optimal, and blended routing
- Output: `experiments/results/legacy_labs/lab_task_routing.json`

**7. lab_basin_topology.py** (209L) — "Attractor basin topology per model"
- Classifies each model's basin shape: shallow/broad, deep/narrow, multi-modal, flat
- Uses basin escape scores + trajectory distances
- Output: `experiments/results/legacy_labs/lab_basin_topology.json`

**8. lab_survival_horizon.py** (195L) — "Sessions-to-bankruptcy"
- "Infinite game" framing: how many sessions before fixed budget exhausted?
- Per model, per budget level
- Output: `experiments/results/legacy_labs/lab_survival_horizon.json`

### Advanced Analysis

**9. lab_sonar_quality.py** (248L) — "Code quality signals from SonarQube"
- Bugs, vulnerabilities, code smells, complexity across all experiments
- Quality gate pass rates per model
- Output: `experiments/results/lab_sonar_quality.json`

**10. lab_think_do_coupling.py** (318L) — "How coupled are thinking and doing?"
- Think/do phase dynamics analysis from trajectory data
- Measures lag between reasoning and action
- Output: `experiments/results/lab_think_do_coupling.json`

**11. lab_story_review.py** (220L) — "What review patterns emerge across stories?"
- Per-story review aggregation from commit_analysis + review
- Identifies common strengths and weaknesses across multi-session stories
- Output: `experiments/results/lab_story_review.json`

## Graph-Based Analysis (requires neo4j running)

**12. lab_basin_topology_neo4j.py** (193L) — "Basin topology via Neo4j"
- Graph-based attractor basin classification
- Requires Docker: `docker-compose -f infrastructure/docker-compose.yml up -d neo4j`
- Output: `experiments/results/legacy_labs/lab_basin_topology_neo4j.json`

## Meta-Analysis

**13. lab_opencode_meta_analysis.py** (178L) — "Patterns in opencode experiments"
- Meta-analysis of experiment structure and outcomes
- Analyzes experiment design itself as data
- Output: `experiments/results/legacy_labs/lab_opencode_meta_analysis.json`

## Newer Labs (story-era + frontier)

**14. lab_story_arc.py** (116L) — "How does a story's quality/cost arc evolve across sessions?"
- Per-session trajectory over the 5-session story format
- Output: `experiments/results/lab_story_arc.json`

**15. lab_condition_effects.py** (102L) — "Do perturbation conditions move outcome metrics?"
- CLEAN / BAD_SEED / EARLY_DEGRADE / LATE_DEGRADE comparison
- Output: `experiments/results/lab_condition_effects.json`

**16. lab_cache_economics.py** (94L) — "What is cache hits worth in dollars/rework?"
- Cache-hit economics from session transcripts
- Output: `experiments/results/lab_cache_economics.json`

**17. lab_quality_frontier.py** (99L) — "Where is the quality-per-cost frontier per model?"
- Pareto frontier across correctness/cost/maintainability
- Output: `experiments/results/lab_quality_frontier.json`

**18. lab_verification_frontier.py** (110L) — "What verification depth buys what correctness?"
- Verification-effort vs verified-outcome frontier
- Output: `experiments/results/lab_verification_frontier.json`

**19. lab_verification_value.py** (121L) — "Is independent verification worth its cost?"
- Agent-authored vs independent-evaluator value delta
- Output: `experiments/results/lab_verification_value.json`

## DEPRECATED Lab Books (retired in Stage 1)

The 8 `*_DEPRECATED_bge_m3.py` lab scripts (drift_trajectories, reasoning_volatility,
cross_model_reasoning, divergence_cascades, cluster_stability, recovery_curves,
reasoning_divergence, semantic_clusters) used bge-m3 embeddings via Ollama and were retired in
Stage 1 — superseded by `agentic_dynamics.measurement.semantic_validation` (no embeddings).

## Running a Lab

```bash
# Standard pattern:
python scripts/lab_grit.py                # Run the formal Grit metric
cat experiments/results/lab_grit.json | python -m json.tool | head -50  # Inspect

# All labs follow the same pattern:
python scripts/lab_<name>.py
# Output: experiments/results/lab_<name>.json
# Methodology: experiments/lab_books/lab_<name>.md
```

## Lab Book Methodology Documents

Living at `experiments/lab_books/lab_<name>.md`. Each defines:
- Hypothesis being tested
- Data sources (which JSON files)
- Analysis steps
- Interpretation guidance

These are the "experiment plan" documents — lab scripts are the implementation.

## Data Dependencies Map

```
lab_claude_audit.py        → _results_summary.json, inventory.json
lab_correctness_escape_quadrants.py → _results_summary.json (QUARANTINED)
lab_grit.py                → canonical registry resolver (finding + story)
lab_correctness_premium.py → _results_summary.json
lab_flail_triggers.py      → _results_summary.json, _trajectory_aggregate.json
lab_tool_archetypes.py     → _trajectory_aggregate.json
lab_task_routing.py        → _results_summary.json
lab_basin_topology.py      → _results_summary.json, _trajectory_aggregate.json
lab_survival_horizon.py    → _results_summary.json
lab_sonar_quality.py       → _results_summary.json
lab_think_do_coupling.py   → _trajectory_summary.json
lab_story_review.py        → _results_summary.json, stories/*.json
```

## Common Patterns When Adding a New Lab

1. Create methodology doc: `experiments/lab_books/lab_<name>.md`
2. Create script: `scripts/lab_<name>.py` that reads from standard JSON sources
3. Output to: `experiments/results/lab_<name>.json`
4. Run with: `python scripts/lab_<name>.py`

## Labs as Measurement Rules (proposed)

In the spec/compiler model, each lab book is a **measurement rule** (`plane: "measurement"`):
it consumes ledger/attempt fields and produces information. `compile_experiment.py`'s
`evaluate_rules` phase will drive these from `spec.rules` instead of one-off scripts. A control
rule (e.g. `model_cascade`) can only be authored after its `requires` (e.g. `confidence`) are
produced by a measurement rule — instrument before policy. Design:
`code_reviews/2026-08-14_experiment-spec-and-compiler-design.md`.

## Common Gotchas

- Always refresh inventory + regenerate summary before running labs.
- The DEPRECATED lab scripts use bge-m3 embeddings which are slow — avoid them.
- Some labs require neo4j Docker container running. Skip if unavailable.
- Lab output JSON files are intermediate — they're consumed by website but not committed directly.
- If a lab crashes with KeyError, likely _results_summary.json is stale. Regenerate it.
- `lab_story_review.py` depends on story worktrees having been run first.
