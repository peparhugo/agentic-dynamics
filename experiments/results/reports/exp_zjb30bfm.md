# Game Report: standardized_retry-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [standardized_retry] deepseek_(retry)...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:56:20

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.801

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.67) with moderate resource use ($0.0138, ~3031J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.316 |
| Architecture div | 0.000 |
| Structure div | 0.338 |
| Thinking ratio | 3.3% |
| Quality/$ | 72 |
| Quality/J | 0.0003 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 43% (3/7 constraints) |
| Lines of code | 314 |
| Cyclomatic complexity | 24.0 |
| Code quality | 0.418 |
| Novelty vs baseline | 0.716 |
| **Composite** | **0.670** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 18,390 |
| Completion tokens | 5,161 |
| Reasoning tokens | 794 |
| **Total tokens** | **24,345** |
| Thinking ratio | 3.3% |
| Output efficiency | 21.2% |
| **Total cost** | **$0.013816** |
| **Total energy** | **~3031 J** |
| Solution density | 0.012898 LOC/tok |
| Correctness/$ | 93 |
| Quality/J | 0.000221 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0138  |  **Energy:** ~3031J  |  **Thinking:** 3%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_zjb30bfm/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 7 |
| Total lines (Py) | 314 |
| Functions | 34 |
| Classes | 3 |
| Functions/file | 4.9 |
| Classes/file | 0.4 |
| Avg lines/file | 45 |
| Type hints | 46% |
| Docstrings | 0% |
| Error handlers | 0 |
| Imports | 24 |
| Decorators | 9 |
| Test files | 1 |
| Test file rate | 14% |
| Parse errors | 0 |
