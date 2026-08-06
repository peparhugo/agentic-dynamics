# Game Report: exp_f1cezegh-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [baseline] typescript_ssg...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:24:03

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.769

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.53) with moderate resource use ($0.0167, ~3949J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 2.8% |
| Quality/$ [C] | 60 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 29% (2/7 constraints) |
| Lines of code [M] | 1178 |
| Cyclomatic complexity [C] | 73.0 |
| Code quality [H] | 0.085 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.528** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 9,312 |
| Completion tokens [M] | 12,636 |
| Reasoning tokens [M] | 634 |
| Cache read tokens [M] | 308,992 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **22,582** |
| Thinking ratio [C] | 2.8% |
| Output efficiency [C] | 56.0% |
| Input cost [M] | $0.000703 |
| Output cost [M] | $0.003888 |
| Reasoning cost [M] | $0.000025 |
| Cache cost [M] | $0.012100 |
| **Total cost** | **$0.016716** |
| **Total energy [X]** | **~3949 J** |
| Solution density [C] | 0.052165 LOC/tok |
| Correctness/$ [C] | 17 |
| Quality/J [C] | 0.000134 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0167  |  **Energy:** ~3949J  |  **Thinking:** 3%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_f1cezegh/session.jsonl)
- [Generated code](./exp_f1cezegh/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 16 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1164 |
| Functions | 0 |
| Classes | 0 |
| Functions/file | 0 |
| Classes/file | 0 |
| Avg lines/file | 0 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 0 |
| Imports | 0 |
| Decorators | 0 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
