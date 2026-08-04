# Game Report: exp_ednngz36-baseline

**Model:** anthropic/claude-fable-5  |  **Task:** REST API with JWT & rate limiting...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:51:52

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.775

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.68) with moderate resource use ($0.9377, ~2149J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 0.0% |
| Quality/$ | 97 |
| Quality/J | 0.0005 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 71% (5/7 constraints) |
| Lines of code | 456 |
| Cyclomatic complexity | 116.0 |
| Code quality | 0.219 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.683** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 28 |
| Completion tokens | 9,333 |
| Reasoning tokens | 0 |
| **Total tokens** | **9,361** |
| Thinking ratio | 0.0% |
| Output efficiency | 99.7% |
| Input cost | $0.000008 |
| Output cost | $0.010266 |
| Reasoning cost | $0.000000 |
| **Total cost** | **$0.937719** |
| **Total energy** | **~2149 J** |
| Solution density | 0.048713 LOC/tok |
| Correctness/$ | 97 |
| Quality/J | 0.000318 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.9377  |  **Energy:** ~2149J  |  **Thinking:** 0%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 10 |
| Total lines | 456 |
| Functions | 40 |
| Classes | 12 |
| Functions/file | 4.0 |
| Classes/file | 1.2 |
| Avg lines/file | 46 |
| Type hints | 0% |
| Docstrings | 8% |
| Error handlers | 6 |
| Imports | 28 |
| Decorators | 8 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_ednngz36/code/)
