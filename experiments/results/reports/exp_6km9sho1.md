# Game Report: inject_phantom_success_s0.5-perturbed

**Model:** openai/gpt-5-nano  |  **Task:** [inject_phantom_success_s0.5] cd_gpt_5_nano...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:21:40

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.806

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.68) and found a novel correct solution (novelty=0.97, correctness=70%). Cost: $0.0042, ~3878J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.680 |
| Architecture div [H] | 0.750 |
| Structure div [H] | 0.300 |
| Thinking ratio [C] | 10.6% |
| Quality/$ [C] | 240 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 70% (0/0 tests) [H] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 144 |
| Cyclomatic complexity [C] | 29.0 |
| Code quality [H] | 0.517 |
| Novelty vs baseline [H] | 0.967 |
| **Composite [H]** | **0.793** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 20,443 |
| Completion tokens [M] | 3,866 |
| Reasoning tokens [M] | 2,880 |
| Cache read tokens [M] | 90,496 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **27,189** |
| Thinking ratio [C] | 10.6% |
| Output efficiency [C] | 14.2% |
| Input cost [M] | $0.000713 |
| Output cost [M] | $0.001079 |
| Reasoning cost [M] | $0.000804 |
| Cache cost [M] | $0.001578 |
| **Total cost** | **$0.004173** |
| **Total energy [X]** | **~3878 J** |
| Solution density [C] | 0.005296 LOC/tok |
| Correctness/$ [C] | 5 |
| Quality/J [C] | 0.000205 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 70%  |  **Cost:** $0.0042  |  **Energy:** ~3878J  |  **Thinking:** 11%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_6km9sho1/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 6 |
| Total lines (Py) | 144 |
| Functions | 12 |
| Classes | 3 |
| Functions/file | 2.0 |
| Classes/file | 0.5 |
| Avg lines/file | 24 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 1 |
| Imports | 17 |
| Decorators | 8 |
| Test files | 1 |
| Test file rate | 17% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 3,866 |
| Python files | 6 |
| Non-Python files | 0 |
| Code density | 0.0372 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |

