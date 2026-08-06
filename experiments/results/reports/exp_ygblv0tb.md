# Game Report: remove_critical_constraint_s0.5_r1-perturbed

**Model:** anthropic/claude-fable-5  |  **Task:** [remove_critical_constraint_s0.5_r1] cd_claude_2rep...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:36:41

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.724

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.60) and found a novel correct solution (novelty=0.86, correctness=70%). Cost: $1.4486, ~3870J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.597 |
| Architecture div [H] | 0.667 |
| Structure div [H] | 0.242 |
| Thinking ratio [C] | 0.0% |
| Quality/$ [C] | 1 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 70% (0/0 tests) [H] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 768 |
| Cyclomatic complexity [C] | 54.0 |
| Code quality [H] | 0.130 |
| Novelty vs baseline [H] | 0.858 |
| **Composite [H]** | **0.700** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 30 |
| Completion tokens [M] | 16,816 |
| Reasoning tokens [M] | 0 |
| Cache read tokens [M] | 256,031 |
| Cache write tokens [M] | 28,121 |
| **Total tokens** | **16,846** |
| Thinking ratio [C] | 0.0% |
| Output efficiency [C] | 99.8% |
| Input cost [M] | $0.000300 |
| Output cost [M] | $0.840800 |
| Reasoning cost [M] | $0.000000 |
| Cache cost [M] | $0.607544 |
| **Total cost** | **$1.448644** |
| **Total energy [X]** | **~3870 J** |
| Solution density [C] | 0.045589 LOC/tok |
| Correctness/$ [C] | 2 |
| Quality/J [C] | 0.000181 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 70%  |  **Cost:** $1.4486  |  **Energy:** ~3870J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_ygblv0tb/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 21 |
| Total lines (Py) | 768 |
| Functions | 100 |
| Classes | 24 |
| Functions/file | 4.8 |
| Classes/file | 1.1 |
| Avg lines/file | 37 |
| Type hints | 2% |
| Docstrings | 4% |
| Error handlers | 5 |
| Imports | 57 |
| Decorators | 39 |
| Test files | 7 |
| Test file rate | 33% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 16,816 |
| Python files | 21 |
| Non-Python files | 0 |
| Code density | 0.0457 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |

