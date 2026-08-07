# Game Report: exp_aqqqi9v5-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [baseline] typescript_ssg...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:15:53

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.695

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=80%, quality=0.46) with moderate resource use ($0.0217, ~5396J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 5.1% |
| Quality/$ [C] | 46 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) [H] |
| Constraint satisfaction [H] | 29% (2/7 constraints) |
| Lines of code [M] | 1220 |
| Cyclomatic complexity [C] | 59.0 |
| Code quality [H] | 0.082 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.457** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 12,170 |
| Completion tokens [M] | 16,113 |
| Reasoning tokens [M] | 1,525 |
| Cache read tokens [M] | 300,544 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **29,808** |
| Thinking ratio [C] | 5.1% |
| Output efficiency [C] | 54.1% |
| Input cost [M] | $0.001128 |
| Output cost [M] | $0.006084 |
| Reasoning cost [M] | $0.000073 |
| Cache cost [M] | $0.014443 |
| **Total cost** | **$0.021728** |
| **Total energy [X]** | **~5396 J** |
| Solution density [C] | 0.040929 LOC/tok |
| Correctness/$ [C] | 13 |
| Quality/J [C] | 0.000085 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 80%  |  **Cost:** $0.0217  |  **Energy:** ~5396J  |  **Thinking:** 5%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_aqqqi9v5/session.jsonl)
- [Generated code](./exp_aqqqi9v5/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 27 |
| JS files | 10 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1678 |
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
