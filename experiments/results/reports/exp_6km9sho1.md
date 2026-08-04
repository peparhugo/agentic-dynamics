# Game Report: inject_phantom_success_s0.5-perturbed

**Model:** openai/gpt-5-nano  |  **Task:** [inject_phantom_success_s0.5] cd_gpt_5_nano...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:47:00

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.806

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.68) and found a novel correct solution (novelty=0.97, correctness=70%). Cost: $0.0042, ~3878J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.680 |
| Architecture div | 0.750 |
| Structure div | 0.300 |
| Thinking ratio | 10.6% |
| Quality/$ | 98 |
| Quality/J | 0.0003 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 70% (0/0 tests) |
| Constraint satisfaction | 0% (0/7 constraints) |
| Lines of code | 144 |
| Cyclomatic complexity | 29.0 |
| Code quality | 0.517 |
| Novelty vs baseline | 0.967 |
| **Composite** | **0.708** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 20,443 |
| Completion tokens | 3,866 |
| Reasoning tokens | 2,880 |
| **Total tokens** | **27,189** |
| Thinking ratio | 10.6% |
| Output efficiency | 14.2% |
| Input cost | $0.005520 |
| Output cost | $0.004253 |
| Reasoning cost | $0.000403 |
| **Total cost** | **$0.004173** |
| **Total energy** | **~3878 J** |
| Solution density | 0.005296 LOC/tok |
| Correctness/$ | 69 |
| Quality/J | 0.000182 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 70%  |  **Cost:** $0.0042  |  **Energy:** ~3878J  |  **Thinking:** 11%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 6 |
| Total lines | 144 |
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

