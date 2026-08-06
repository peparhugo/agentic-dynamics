# Game Report: remove_critical_constraint_s0.5_r1-perturbed

**Model:** anthropic/claude-fable-5  |  **Task:** [remove_critical_constraint_s0.5_r1] cd_claude_2rep...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T01:10:49

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.724

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.60) and found a novel correct solution (novelty=0.86, correctness=70%). Cost: $1.4486, ~3870J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.597 |
| Architecture div | 0.667 |
| Structure div | 0.242 |
| Thinking ratio | 0.0% |
| Quality/$ | 54 |
| Quality/J | 0.0003 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 70% (0/0 tests) |
| Constraint satisfaction | 0% (0/7 constraints) |
| Lines of code | 768 |
| Cyclomatic complexity | 54.0 |
| Code quality | 0.130 |
| Novelty vs baseline | 0.858 |
| **Composite** | **0.700** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 30 |
| Completion tokens | 16,816 |
| Reasoning tokens | 0 |
| **Total tokens** | **16,846** |
| Thinking ratio | 0.0% |
| Output efficiency | 99.8% |
| Input cost | $0.000008 |
| Output cost | $0.018498 |
| Reasoning cost | $0.000000 |
| **Total cost** | **$1.448644** |
| **Total energy** | **~3870 J** |
| Solution density | 0.045589 LOC/tok |
| Correctness/$ | 38 |
| Quality/J | 0.000181 |

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

