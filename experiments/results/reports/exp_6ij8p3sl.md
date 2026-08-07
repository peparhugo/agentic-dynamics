# Game Report: exp_6ij8p3sl-baseline

**Model:** openai/gpt-5-nano  |  **Task:** [baseline] cd_gpt_5_nano...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:14:43

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.735

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=70%, quality=0.68) with moderate resource use ($0.0037, ~3083J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 14.8% |
| Quality/$ [C] | 271 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 70% (0/0 tests) [H] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 182 |
| Cyclomatic complexity [C] | 31.0 |
| Code quality [H] | 0.500 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.677** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 10,787 |
| Completion tokens [M] | 4,289 |
| Reasoning tokens [M] | 2,624 |
| Cache read tokens [M] | 76,544 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **17,700** |
| Thinking ratio [C] | 14.8% |
| Output efficiency [C] | 24.2% |
| Input cost [M] | $0.000381 |
| Output cost [M] | $0.001212 |
| Reasoning cost [M] | $0.000742 |
| Cache cost [M] | $0.001352 |
| **Total cost** | **$0.003687** |
| **Total energy [X]** | **~3083 J** |
| Solution density [C] | 0.010282 LOC/tok |
| Correctness/$ [C] | 5 |
| Quality/J [C] | 0.000220 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 70%  |  **Cost:** $0.0037  |  **Energy:** ~3083J  |  **Thinking:** 15%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_6ij8p3sl/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines (Py) | 182 |
| Functions | 22 |
| Classes | 1 |
| Functions/file | 11.0 |
| Classes/file | 0.5 |
| Avg lines/file | 91 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 4 |
| Imports | 10 |
| Decorators | 13 |
| Test files | 1 |
| Test file rate | 50% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 4,289 |
| Python files | 2 |
| Non-Python files | 0 |
| Code density | 0.0424 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |

