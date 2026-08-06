# Game Report: standardized_build-perturbed

**Model:** anthropic/claude-fable-5  |  **Task:** [standardized_build] claude...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:51:16

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.698

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=70%, quality=0.51) with moderate resource use ($1.1104, ~2910J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.444 |
| Architecture div | 0.455 |
| Structure div | 0.189 |
| Thinking ratio | 0.0% |
| Quality/$ | 1 |
| Quality/J | 0.0003 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 70% (0/0 tests) |
| Constraint satisfaction | 0% (0/7 constraints) |
| Lines of code | 600 |
| Cyclomatic complexity | 86.0 |
| Code quality | 0.167 |
| Novelty vs baseline | 0.685 |
| **Composite** | **0.510** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 18 |
| Completion tokens | 12,648 |
| Reasoning tokens | 0 |
| **Total tokens** | **12,666** |
| Thinking ratio | 0.0% |
| Output efficiency | 99.9% |
| **Total cost** | **$1.110397** |
| **Total energy** | **~2910 J** |
| Solution density | 0.047371 LOC/tok |
| Correctness/$ | 50 |
| Quality/J | 0.000175 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 70%  |  **Cost:** $1.1104  |  **Energy:** ~2910J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_ovy9g9b5/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 10 |
| Total lines (Py) | 600 |
| Functions | 89 |
| Classes | 14 |
| Functions/file | 8.9 |
| Classes/file | 1.4 |
| Avg lines/file | 60 |
| Type hints | 33% |
| Docstrings | 6% |
| Error handlers | 2 |
| Imports | 32 |
| Decorators | 10 |
| Test files | 5 |
| Test file rate | 50% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 12,648 |
| Python files | 10 |
| Non-Python files | 0 |
| Code density | 0.0474 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |

