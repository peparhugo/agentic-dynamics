# Game Report: exp__ygf4hz3-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [baseline] typescript_ssg...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:44:49

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.712

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.53) with moderate resource use ($0.0337, ~10636J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 31.3% |
| Quality/$ | 30 |
| Quality/J | 0.0001 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 29% (2/7 constraints) |
| Lines of code | 910 |
| Cyclomatic complexity | 114.0 |
| Code quality | 0.110 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.533** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 17,781 |
| Completion tokens | 12,155 |
| Reasoning tokens | 13,654 |
| **Total tokens** | **43,590** |
| Thinking ratio | 31.3% |
| Output efficiency | 27.9% |
| **Total cost** | **$0.033702** |
| **Total energy** | **~10636 J** |
| Solution density | 0.020876 LOC/tok |
| Correctness/$ | 50 |
| Quality/J | 0.000050 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0337  |  **Energy:** ~10636J  |  **Thinking:** 31%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp__ygf4hz3/session.jsonl)
- [Generated code](./exp__ygf4hz3/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 14 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 894 |
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
