# Game Report: data_table-baseline

**Model:** anthropic/claude-fable-5  |  **Task:** [batch:data_table:baseline] claude_fable_5...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:18:34

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.775

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.56) with moderate resource use ($2.0531, ~5398J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 0.0% |
| Quality/$ [C] | 0 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 25% (1/4 constraints) |
| Lines of code [M] | 313 |
| Cyclomatic complexity [C] | 111.0 |
| Code quality [H] | 0.319 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.564** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 42 |
| Completion tokens [M] | 23,456 |
| Reasoning tokens [M] | 0 |
| Cache read tokens [M] | 445,750 |
| Cache write tokens [M] | 34,733 |
| **Total tokens** | **23,498** |
| Thinking ratio [C] | 0.0% |
| Output efficiency [C] | 99.8% |
| Input cost [M] | $0.000420 |
| Output cost [M] | $1.172800 |
| Reasoning cost [M] | $0.000000 |
| Cache cost [M] | $0.879913 |
| **Total cost** | **$2.053133** |
| **Total energy [X]** | **~5398 J** |
| Solution density [C] | 0.013320 LOC/tok |
| Correctness/$ [C] | 2 |
| Quality/J [C] | 0.000104 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $2.0531  |  **Energy:** ~5398J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_batch_batch_data_table_baseline claude_fable_5/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 7 |
| TS files | 10 |
| TSX files | 1 |
| Total lines (Py) | 313 |
| Total lines (TS/TSX) | 838 |
| Functions | 22 |
| Classes | 6 |
| Functions/file | 3.1 |
| Classes/file | 0.9 |
| Avg lines/file | 45 |
| Type hints | 173% |
| Docstrings | 50% |
| Error handlers | 1 |
| Imports | 19 |
| Decorators | 1 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
