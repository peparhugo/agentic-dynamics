# Game Report: exp_wo0bkk9m-baseline

**Model:** anthropic/claude-fable-5  |  **Task:** Authenticated REST API with JWT...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T03:08:30

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.775

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.66) with moderate resource use ($0.6322, ~1586J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 0.0% |
| Quality/$ | 132 |
| Quality/J | 0.0006 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 57% (4/7 constraints) |
| Lines of code | 298 |
| Cyclomatic complexity | 41.0 |
| Code quality | 0.336 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.664** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 12 |
| Completion tokens | 6,893 |
| Reasoning tokens | 0 |
| **Total tokens** | **6,905** |
| Thinking ratio | 0.0% |
| Output efficiency | 99.8% |
| Input cost | $0.000003 |
| Output cost | $0.007582 |
| Reasoning cost | $0.000000 |
| **Total cost** | **$0.632214** |
| **Total energy** | **~1586 J** |
| Solution density | 0.043157 LOC/tok |
| Correctness/$ | 132 |
| Quality/J | 0.000418 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.6322  |  **Energy:** ~1586J  |  **Thinking:** 0%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 7 |
| Total lines | 298 |
| Functions | 29 |
| Classes | 17 |
| Functions/file | 4.1 |
| Classes/file | 2.4 |
| Avg lines/file | 43 |
| Type hints | 53% |
| Docstrings | 14% |
| Error handlers | 6 |
| Imports | 19 |
| Decorators | 10 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_wo0bkk9m/code/)
