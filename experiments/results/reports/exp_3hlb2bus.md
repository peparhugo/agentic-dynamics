# Game Report: exp_3hlb2bus-baseline

**Model:** anthropic/claude-fable-5  |  **Task:** Task management API: Flask/SQLite/JWT...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:45:55

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.775

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.63) with moderate resource use ($1.2564, ~3282J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 0.0% |
| Quality/$ | 64 |
| Quality/J | 0.0003 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 57% (4/7 constraints) |
| Lines of code | 581 |
| Cyclomatic complexity | 134.0 |
| Code quality | 0.172 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.631** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 28 |
| Completion tokens | 14,260 |
| Reasoning tokens | 0 |
| **Total tokens** | **14,288** |
| Thinking ratio | 0.0% |
| Output efficiency | 99.8% |
| Input cost | $0.000008 |
| Output cost | $0.015686 |
| Reasoning cost | $0.000000 |
| **Total cost** | **$1.256440** |
| **Total energy** | **~3282 J** |
| Solution density | 0.040663 LOC/tok |
| Correctness/$ | 64 |
| Quality/J | 0.000192 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $1.2564  |  **Energy:** ~3282J  |  **Thinking:** 0%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 8 |
| Total lines | 581 |
| Functions | 45 |
| Classes | 3 |
| Functions/file | 5.6 |
| Classes/file | 0.4 |
| Avg lines/file | 73 |
| Type hints | 22% |
| Docstrings | 13% |
| Error handlers | 6 |
| Imports | 29 |
| Decorators | 34 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
