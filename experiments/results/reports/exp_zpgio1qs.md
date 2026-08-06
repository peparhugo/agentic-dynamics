# Game Report: exp_zpgio1qs-baseline

**Model:** openai/gpt-5  |  **Task:** [baseline] typescript_ssg...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T01:12:15

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.688

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=80%, quality=0.48) with moderate resource use ($0.2201, ~7179J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 8.5% |
| Quality/$ | 47 |
| Quality/J | 0.0001 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 29% (2/7 constraints) |
| Lines of code | 514 |
| Cyclomatic complexity | 89.0 |
| Code quality | 0.195 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.480** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 36,516 |
| Completion tokens | 9,750 |
| Reasoning tokens | 4,288 |
| **Total tokens** | **50,554** |
| Thinking ratio | 8.5% |
| Output efficiency | 19.3% |
| Input cost | $0.009859 |
| Output cost | $0.010725 |
| Reasoning cost | $0.000600 |
| **Total cost** | **$0.220121** |
| **Total energy** | **~7179 J** |
| Solution density | 0.010167 LOC/tok |
| Correctness/$ | 38 |
| Quality/J | 0.000067 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 80%  |  **Cost:** $0.2201  |  **Energy:** ~7179J  |  **Thinking:** 8%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_zpgio1qs/session.jsonl)
- [Generated code](./exp_zpgio1qs/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 9 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 493 |
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
