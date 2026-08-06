# Game Report: remove_critical_constraint_s0.5-perturbed

**Model:** exp_05ngi4l9  |  **Task:** [remove_critical_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:47:59

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.691

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=80%, quality=0.47) with moderate resource use ($0.0335, ~7688J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 7.2% |
| Quality/$ | 36 |
| Quality/J | 0.0001 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 29% (2/7 constraints) |
| Lines of code | 809 |
| Cyclomatic complexity | 64.0 |
| Code quality | 0.124 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.465** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 20,562 |
| Completion tokens | 19,835 |
| Reasoning tokens | 3,151 |
| **Total tokens** | **43,548** |
| Thinking ratio | 7.2% |
| Output efficiency | 45.5% |
| Input cost | $0.005552 |
| Output cost | $0.021819 |
| Reasoning cost | $0.000441 |
| **Total cost** | **$0.033538** |
| **Total energy** | **~7688 J** |
| Solution density | 0.018577 LOC/tok |
| Correctness/$ | 29 |
| Quality/J | 0.000061 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 80%  |  **Cost:** $0.0335  |  **Energy:** ~7688J  |  **Thinking:** 7%

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 17 |
| JS files | 7 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1230 |
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
