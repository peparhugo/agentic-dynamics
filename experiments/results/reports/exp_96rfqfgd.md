# Game Report: inject_alien_vocab_s0.5-perturbed

**Model:** exp_96rfqfgd  |  **Task:** [inject_alien_vocab_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:47:40

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.656

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=80%, quality=0.43) with moderate resource use ($0.0151, ~4899J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 24.6% |
| Quality/$ | 83 |
| Quality/J | 0.0002 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 14% (1/7 constraints) |
| Lines of code | 713 |
| Cyclomatic complexity | 60.0 |
| Code quality | 0.140 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.426** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 6,588 |
| Completion tokens | 8,760 |
| Reasoning tokens | 5,015 |
| **Total tokens** | **20,363** |
| Thinking ratio | 24.6% |
| Output efficiency | 43.0% |
| Input cost | $0.001779 |
| Output cost | $0.009636 |
| Reasoning cost | $0.000702 |
| **Total cost** | **$0.015082** |
| **Total energy** | **~4899 J** |
| Solution density | 0.035014 LOC/tok |
| Correctness/$ | 66 |
| Quality/J | 0.000087 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 80%  |  **Cost:** $0.0151  |  **Energy:** ~4899J  |  **Thinking:** 25%

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 9 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 690 |
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
