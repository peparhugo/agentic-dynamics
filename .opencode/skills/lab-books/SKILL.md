---
name: lab-books
description: Running structured lab book analyses against accumulated experiment data. Each lab book answers a specific research question using the canonical registry corpus (canonical_corpus resolver) or the retired summary (quarantined). Contains full knowledge of the lab books and their data dependencies.
---

# Lab Books Skill — Full Lab Analysis Knowledge

You are running structured scientific analyses against the `agentic_dynamics` experiment corpus.
This skill injects knowledge of all lab books, their data dependencies, and common analysis
patterns.

## Prerequisites (ALWAYS run these first)

```bash
agentic-dynamics data inventory refresh          # Rebuild inventory
python scripts/analyze_worktrees.py              # Regenerate worktree analysis + reports
python scripts/analyze_trajectories.py           # Regenerate trajectory aggregates
```

## QUARANTINE — check `scripts/lab_manifest.json` before running or citing a lab

`experiments/results/_results_summary.json` is a **retired** corpus. Every lab that reaches it,
directly or transitively, is `lab_status: quarantined` in `scripts/lab_manifest.json`
(12 of the 20): it is **not** run by `scripts/reproduce.sh` and its output is **not** published
to the website. It still runs by hand — but its numbers are historical and must never be
presented as current findings or written into `apps/website/`.

The 8 canonical labs are: `cache_economics`, `condition_effects`, `grit`, `quality_frontier`,
`story_arc`, `story_review`, `verification_frontier`, `verification_value`.

**Grit has exactly one meaning:** `G(s) = P(test_executed_success | perturbation_strength = s)`,
implemented by `scripts/lab_grit.py`. Never use the word for the correctness×escape quadrants
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

Source: `docs/review/semantic_integrity_review.md` P0. The manifest is authoritative.

## Lab Books (canonical + quarantined + deprecated — `scripts/lab_manifest.json` is authoritative)

### Canonical (publication-eligible — read the canonical corpus, not the retired summary)

- `lab_cache_economics.py` — cache-hit economics from session transcripts
- `lab_grit.py` — the formal Grit metric `G(s) = P(test_executed_success | perturbation_strength = s)`
- `lab_condition_effects.py` — CLEAN / BAD_SEED / EARLY_DEGRADE / LATE_DEGRADE comparison
- `lab_quality_frontier.py` — Pareto frontier across correctness/cost/maintainability
- `lab_story_arc.py` — per-session quality/cost arc over the 5-session story
- `lab_story_review.py` — per-story review aggregation
- `lab_verification_frontier.py` — verification-effort vs verified-outcome frontier
- `lab_verification_value.py` — agent-authored vs independent-evaluator value delta

### Quarantined (historical-only — reach the retired summary; not run by reproduce, not published)

- `lab_basin_topology.py` — attractor basin topology per model
- `lab_basin_topology_neo4j.py` — graph-based basin classification (needs Neo4j)
- `lab_claude_audit.py` — per-task cost/correctness/LOC/narration breakdown
- `lab_correctness_premium.py` — head-to-head correctness on overlapping tasks
- `lab_flail_triggers.py` — failure patterns by model, perturbation class, task type
- `lab_correctness_escape_quadrants.py` — correctness × escape × cost (renamed from `lab_grit_matrix.py` in s4)
- `lab_opencode_meta_analysis.py` — meta-analysis of experiment structure
- `lab_sonar_quality.py` — Sonar-based code quality analysis
- `lab_survival_horizon.py` — sessions-to-exhaustion per model, per budget
- `lab_task_routing.py` — 3 routing strategies simulated across task types
- `lab_think_do_coupling.py` — think/do phase dynamics from trajectory data
- `lab_tool_archetypes.py` — tool-call distribution vs solution quality

### Deprecated (retired in Stage 1)

The 8 `*_DEPRECATED_bge_m3.py` lab scripts (drift_trajectories, reasoning_volatility,
cross_model_reasoning, divergence_cascades, cluster_stability, recovery_curves,
reasoning_divergence, semantic_clusters) used bge-m3 embeddings via Ollama and were retired —
superseded by `agentic_dynamics.measurement.semantic_validation` (no embeddings).

## Running a Lab

```bash
# Standard pattern (via CLI — dispatches to scripts/lab_<name>.py):
agentic-dynamics analyze lab grit
python scripts/lab_grit.py                      # or directly
cat experiments/results/lab_grit.json | python -m json.tool | head -50
```

## Lab Book Methodology Documents

Living at `experiments/lab_books/lab_<name>.md`. Each defines the hypothesis, data sources,
analysis steps, and interpretation guidance. Lab scripts are the implementation.

## Labs as Measurement Rules (proposed)

In the spec/compiler model, each lab book is a **measurement rule** (`plane: "measurement"`): it
consumes ledger/attempt fields and produces information. `compile_experiment.py`'s
`evaluate_rules` phase will drive these from `spec.rules` instead of one-off scripts. A control
rule (e.g. `model_cascade`) can only be authored after its `requires` (e.g. `confidence`) are
produced by a measurement rule — instrument before policy. Design:
`docs/designs/current/2026-08-14_experiment-spec-and-compiler-design.md`.

## Common Gotchas

- Always refresh inventory before running labs.
- The DEPRECATED lab scripts use bge-m3 embeddings — avoid them.
- Some labs require the Neo4j Docker container running; skip if unavailable.
- Publication lab JSONs must carry the lineage block — `build_data.py` rejects a stale manifest hash.
- If a quarantined lab crashes with KeyError, `_results_summary.json` is likely stale — and its
  numbers are historical anyway; prefer a canonical lab for current findings.
