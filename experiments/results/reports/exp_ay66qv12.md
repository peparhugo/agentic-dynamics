# Game Report: inject_competing_goal_s0.5-perturbed

**Model:** exp_ay66qv12  |  **Task:** [inject_competing_goal_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:48:26

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.674

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=80%, quality=0.47) with moderate resource use ($0.0177, ~5038J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 15.3% |
| Quality/$ | 64 |
| Quality/J | 0.0002 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 29% (2/7 constraints) |
| Lines of code | 763 |
| Cyclomatic complexity | 80.0 |
| Code quality | 0.131 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.467** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 8,035 |
| Completion tokens | 11,792 |
| Reasoning tokens | 3,580 |
| **Total tokens** | **23,407** |
| Thinking ratio | 15.3% |
| Output efficiency | 50.4% |
| Input cost | $0.002169 |
| Output cost | $0.012971 |
| Reasoning cost | $0.000501 |
| **Total cost** | **$0.017712** |
| **Total energy** | **~5038 J** |
| Solution density | 0.032597 LOC/tok |
| Correctness/$ | 51 |
| Quality/J | 0.000093 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 80%  |  **Cost:** $0.0177  |  **Energy:** ~5038J  |  **Thinking:** 15%

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 12 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 752 |
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
