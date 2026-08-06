# Game Report: exp_x8g28_k8-baseline

**Model:** openai/gpt-5-mini  |  **Task:** [baseline] cd_openai_GPT_5_mini...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:36:28

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.659

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=70%, quality=0.68) with moderate resource use ($0.0180, ~2629J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.000 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.000 |
| Thinking ratio [C] | 5.5% |
| Quality/$ [C] | 56 |
| Quality/J [C] | 0.0004 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 70% (0/0 tests) [H] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 187 |
| Cyclomatic complexity [C] | 28.0 |
| Code quality [H] | 0.533 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.684** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 14,349 |
| Completion tokens [M] | 4,216 |
| Reasoning tokens [M] | 1,088 |
| Cache read tokens [M] | 152,192 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **19,653** |
| Thinking ratio [C] | 5.5% |
| Output efficiency [C] | 21.5% |
| Input cost [M] | $0.001944 |
| Output cost [M] | $0.004569 |
| Reasoning cost [M] | $0.001179 |
| Cache cost [M] | $0.010308 |
| **Total cost** | **$0.018000** |
| **Total energy [X]** | **~2629 J** |
| Solution density [C] | 0.009515 LOC/tok |
| Correctness/$ [C] | 4 |
| Quality/J [C] | 0.000260 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 70%  |  **Cost:** $0.0180  |  **Energy:** ~2629J  |  **Thinking:** 6%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_x8g28_k8/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines (Py) | 187 |
| Functions | 23 |
| Classes | 4 |
| Functions/file | 11.5 |
| Classes/file | 2.0 |
| Avg lines/file | 94 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 6 |
| Imports | 16 |
| Decorators | 16 |
| Test files | 1 |
| Test file rate | 50% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 4,216 |
| Python files | 2 |
| Non-Python files | 0 |
| Code density | 0.0444 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |

