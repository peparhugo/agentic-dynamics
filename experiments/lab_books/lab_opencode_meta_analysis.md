---
experiment_id: lab_opencode_meta_analysis
title: "Lab Book 13: opencode-Driven Meta-Analysis — The Model Analyzing Itself"
hypothesis: "DeepSeek v4-flash, given experiment data through the opencode harness, can produce qualitative analysis of experiment patterns that identifies non-obvious relationships and generates actionable insights — and the analysis itself is measurable, costed, and traceable."
null_hypothesis: "Model-generated analysis of its own experiment data produces no insights beyond what human-labelled metadata already captures."
status: planned
created: 2026-08-10
data_sources:
  - experiments/results/_results_summary.json
  - experiments/results/reports/exp_*/session.jsonl
  - ChromaDB collection: session_embeddings
  - Neo4j graph database
analysis_script: scripts/analyze_with_opencode.py
infrastructure:
  - src/instrument/opencode_analyzer.py (OpencodeAnalyzer)
  - src/instrument/opencode.py (run_opencode_agentic)
  - deepseek/deepseek-v4-flash via opencode harness
---

# Lab Book 13: opencode-Driven Meta-Analysis — The Model Analyzing Itself

## Hypothesis

**H1:** DeepSeek v4-flash, given experiment data through the opencode harness, can produce qualitative analysis of experiment patterns that identifies non-obvious relationships and generates actionable insights. The analysis itself is a measurable experiment — costed, traced, and evaluated by the same instrument.

**H0:** Model-generated analysis of its own experiment data produces no insights beyond what human-labelled metadata already captures.

## Motivation

This is the capstone of the new infrastructure stack. The original experiments measured how models code under perturbation. Now we close the loop: we have the same model analyze its own behavior.

Using `run_opencode_agentic()` with `deepseek/deepseek-v4-flash`, we spawn analysis sessions where the model:
1. Reads experiment data (session traces, metrics, aggregates)
2. Produces qualitative analysis (narrative, pattern detection, recommendations)
3. Writes analysis to files in a sandbox worktree
4. The session is recorded — producing its own `session.jsonl`, token counts, and cost

This creates a **meta-experiment**: a measured, costed, traceable analysis that itself becomes part of the experiment corpus. We can measure what analysis costs (~$0.001-0.005/session with v4-flash) and whether the analysis quality justifies that cost.

## Methodology

**Design:** Run 5-10 analysis sessions through `OpencodeAnalyzer`, each targeting a different analytical lens:

| Session | Analysis Task | Data Fed | Expected Output |
|---------|---------------|----------|-----------------|
| A | Session deep-dive | Full session.jsonl + metrics for exp_0s36_d3n | `analysis.md`: approach assessment, efficiency analysis, verdict |
| B | Pairwise comparison | Baseline vs perturbed metrics + session traces | `comparison.md`: what changed, was cost justified |
| C | Model profile | All 119 DeepSeek sessions (batch) | `analysis.md`: patterns across DeepSeek runs |
| D | Strategy analysis | Filter: strategy=wasteful (3 sessions) | `analysis.md`: what makes a session wasteful |
| E | Perturbation class comparison | Manifold vs semantic aggregated stats | `analysis.md`: which perturbation class is harder |
| F | Cost anomaly detection | Top 10 most expensive sessions | `analysis.md`: what drives high costs |
| G | Cross-model comparison | DeepSeek vs Claude on shared tasks | `analysis.md`: when is Claude worth it |
| H | Lab book synthesis | Grit Matrix + Basin Topology results | `analysis.md`: emergent themes across analyses |

**Infrastructure:**
- `OpencodeAnalyzer` — wraps `run_opencode_agentic(prompt, model="deepseek/deepseek-v4-flash", standardize=False, enforce_pytest=False)`
- Each session gets a temp worktree with git, producing `session.jsonl` and `analysis.md` / `comparison.md`
- Results archived to `experiments/results/reports/meta_*/`
- Cost tracked via `AgenticResult.estimated_cost_usd`

**Sample:** 8 analysis sessions targeting 8 different analytical lenses. Total estimated cost: $0.008-0.040 (8 × ~$0.003/analysis).

## Data Sources

- `experiments/results/_results_summary.json` — 227 entries with all metrics
- `experiments/results/reports/exp_*/session.jsonl` — full reasoning traces
- `experiments/results/_trajectory_aggregate.json` — per-model aggregates
- `experiments/results/lab_*.json` — existing lab book results (for synthesis)

## Analysis Steps

1. **Session deep-dive.** Feed `exp_0s36_d3n` (DeepSeek, typescript_ssg, baseline, cost=$0.024, correctness=1.0) to v4-flash. Ask for approach assessment and efficiency analysis.

2. **Pairwise comparison.** Feed baseline (`exp_0s36_d3n`) vs perturbed (`exp_brg802xf`, shift_framing_s0.5, cost=$0.013, correctness=1.0). Ask: "How did the perturbation change behavior?"

3. **Model profile.** Feed a batch of all 119 DeepSeek sessions. Ask: "What patterns emerge across DeepSeek's experiment runs?"

4. **Strategy analysis.** Feed all sessions classified as `wasteful`. Ask: "What characterizes these wasteful runs? What do they have in common?"

5. **Perturbation class comparison.** Feed aggregated stats for manifold vs semantic perturbations. Ask: "Which perturbation class is harder and why?"

6. **Cost anomaly detection.** Feed the 10 most expensive sessions. Ask: "What drives high cost in these sessions?"

7. **Cross-model comparison.** Feed DeepSeek vs Claude stats on shared tasks. Ask: "When is Claude's premium justified?"

8. **Lab book synthesis.** Feed Grit Matrix + Basin Topology results. Ask: "What are the emergent themes across these analyses?"

9. **Measure analysis cost.** For each session, record `estimated_cost_usd`, `total_tokens`, `duration_s`. Aggregate across all 8.

10. **Evaluate analysis quality.** Manual review of each `analysis.md`. Score on: coherence (1-5), insight (1-5), actionability (1-5). Compare against random-chance baseline.

## Expected Output

**Table: Analysis Session Metrics**

| Session | Task | Tokens | Cost | Duration | Files Produced | Exit Code |
|---------|------|--------|------|----------|---------------|-----------|
| A | Session deep-dive exp_0s36_d3n | ~15K | ~$0.003 | ~30s | analysis.md | 0 |
| B | Pairwise comparison | ~18K | ~$0.004 | ~35s | comparison.md | 0 |
| C | Model profile (119 sessions) | ~25K | ~$0.005 | ~45s | analysis.md | 0 |
| D | Strategy analysis (wasteful) | ~12K | ~$0.002 | ~25s | analysis.md | 0 |
| E | Perturbation class comparison | ~15K | ~$0.003 | ~30s | analysis.md | 0 |
| F | Cost anomaly detection | ~15K | ~$0.003 | ~30s | analysis.md | 0 |
| G | Cross-model comparison | ~18K | ~$0.004 | ~35s | analysis.md | 0 |
| H | Lab book synthesis | ~20K | ~$0.004 | ~40s | analysis.md | 0 |
| **Total** | | **~138K** | **~$0.028** | **~4.5 min** | | |

**Table: Analysis Quality Assessment**

| Session | Coherence (1-5) | Insight (1-5) | Actionability (1-5) | Composite |
|---------|-----------------|---------------|---------------------|-----------|
| A | 4 | 3 | 3 | 3.3 |
| B | 4 | 4 | 4 | 4.0 |
| C | 3 | 5 | 4 | 4.0 |
| D | 4 | 4 | 5 | 4.3 |
| ... | | | | |

## Interpretation Guide

- **If analysis cost < 1% of experiment cost:** Meta-analysis is essentially free — run it on every session
- **If v4-flash analysis quality ≥ 3.0 composite:** The model produces useful qualitative insights
- **If v4-flash analysis quality < 2.5:** Model-generated analysis is noise — need human or larger model
- **If v4-flash identifies patterns not captured by lab books:** The model sees structure humans missed
- **If v4-flash analysis correlates with existing lab book findings:** The model validates human analysis
- **Cost-quality tradeoff:** v4-flash costs ~$0.003/analysis. At $0.028 for 8 analyses, the cost is negligible compared to the main experiment budget (~$50+).

## Expected Findings

1. v4-flash produces coherent, insightful analysis for individual sessions (sessions A, B)
2. Batch pattern recognition is stronger than single-session analysis (sessions C, D, E)
3. The model identifies patterns that match human-labelled lab book findings (session H)
4. Analysis cost is negligible: $0.028 for 8 comprehensive analysis sessions
5. The model is weaker on quantitative reasoning than qualitative pattern description
6. v4-flash can serve as a first-pass analyst — flagging interesting sessions for human review

## Relationship to Existing Analyses

| Existing Lab Book | This Meta-Analysis Adds |
|-------------------|------------------------|
| `lab_grit_matrix` | Qualitative interpretation of quadrant patterns |
| `lab_claude_audit` | Narrative on when Claude's premium is justified |
| `lab_basin_topology` | Natural-language basin type descriptions per model |
| `lab_flail_triggers` | Pattern detection in flailing sessions |
| `lab_reasoning_divergence` | Interpretation of divergence matrix |
| `lab_semantic_clusters` | Natural-language cluster labelling |

## Artifacts

- Analysis script: `scripts/analyze_with_opencode.py`
- Core module: `src/instrument/opencode_analyzer.py` (OpencodeAnalyzer)
- Analysis outputs: `experiments/results/reports/meta_*/` (8 session directories with analysis.md, session.jsonl, meta.json)
- Aggregate meta-metrics: `experiments/results/lab_opencode_meta_analysis.json`
