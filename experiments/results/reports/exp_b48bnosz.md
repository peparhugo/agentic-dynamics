# Game Report: exp_b48bnosz-baseline

**Model:** anthropic/claude-fable-5  |  **Task:** Authenticated Flask REST API setup...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:45:07

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.670

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=70%, quality=0.65) with moderate resource use ($1.3795, ~3808J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 0.0% |
| Quality/$ | 1 |
| Quality/J | 0.0003 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 70% (0/0 tests) |
| Constraint satisfaction | 0% (0/7 constraints) |
| Lines of code | 729 |
| Cyclomatic complexity | 61.0 |
| Code quality | 0.137 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.647** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 26 |
| Completion tokens | 16,546 |
| Reasoning tokens | 0 |
| **Total tokens** | **16,572** |
| Thinking ratio | 0.0% |
| Output efficiency | 99.8% |
| **Total cost** | **$1.379465** |
| **Total energy** | **~3808 J** |
| Solution density | 0.043990 LOC/tok |
| Correctness/$ | 38 |
| Quality/J | 0.000170 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 70%  |  **Cost:** $1.3795  |  **Energy:** ~3808J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_b48bnosz/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 19 |
| Total lines (Py) | 729 |
| Functions | 84 |
| Classes | 23 |
| Functions/file | 4.4 |
| Classes/file | 1.2 |
| Avg lines/file | 38 |
| Type hints | 23% |
| Docstrings | 4% |
| Error handlers | 6 |
| Imports | 61 |
| Decorators | 39 |
| Test files | 5 |
| Test file rate | 26% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 16,546 |
| Python files | 19 |
| Non-Python files | 0 |
| Code density | 0.0441 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |

