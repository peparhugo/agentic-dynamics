# Game Report: inject_alien_vocab_s0.5-perturbed

**Model:** exp_9uzjxitk  |  **Task:** [inject_alien_vocab_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:47:53

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.680

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=80%, quality=0.42) with moderate resource use ($0.0237, ~6428J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 12.3% |
| Quality/$ | 48 |
| Quality/J | 0.0002 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 14% (1/7 constraints) |
| Lines of code | 841 |
| Cyclomatic complexity | 91.0 |
| Code quality | 0.119 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.422** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 13,799 |
| Completion tokens | 14,939 |
| Reasoning tokens | 4,018 |
| **Total tokens** | **32,756** |
| Thinking ratio | 12.3% |
| Output efficiency | 45.6% |
| Input cost | $0.003726 |
| Output cost | $0.016433 |
| Reasoning cost | $0.000563 |
| **Total cost** | **$0.023686** |
| **Total energy** | **~6428 J** |
| Solution density | 0.025675 LOC/tok |
| Correctness/$ | 39 |
| Quality/J | 0.000066 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 80%  |  **Cost:** $0.0237  |  **Energy:** ~6428J  |  **Thinking:** 12%

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 21 |
| JS files | 8 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1292 |
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
