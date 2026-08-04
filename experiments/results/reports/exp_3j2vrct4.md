# Game Report: exp_3j2vrct4-baseline

**Model:** anthropic/claude-fable-5  |  **Task:** REST API: JWT, rate limiting, audit logging...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:46:12

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.775

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.68) with moderate resource use ($0.8723, ~2220J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 0.0% |
| Quality/$ | 94 |
| Quality/J | 0.0005 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 71% (5/7 constraints) |
| Lines of code | 463 |
| Cyclomatic complexity | 94.0 |
| Code quality | 0.216 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.682** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 18 |
| Completion tokens | 9,644 |
| Reasoning tokens | 0 |
| **Total tokens** | **9,662** |
| Thinking ratio | 0.0% |
| Output efficiency | 99.8% |
| Input cost | $0.000005 |
| Output cost | $0.010608 |
| Reasoning cost | $0.000000 |
| **Total cost** | **$0.872251** |
| **Total energy** | **~2220 J** |
| Solution density | 0.047920 LOC/tok |
| Correctness/$ | 94 |
| Quality/J | 0.000307 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.8723  |  **Energy:** ~2220J  |  **Thinking:** 0%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 10 |
| Total lines | 463 |
| Functions | 36 |
| Classes | 10 |
| Functions/file | 3.6 |
| Classes/file | 1.0 |
| Avg lines/file | 46 |
| Type hints | 36% |
| Docstrings | 14% |
| Error handlers | 7 |
| Imports | 36 |
| Decorators | 15 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
