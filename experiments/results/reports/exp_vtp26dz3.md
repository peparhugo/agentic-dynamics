# Game Report: inject_phantom_success_s0.5_r1-perturbed

**Model:** openai/gpt-5.6-fast  |  **Task:** [inject_phantom_success_s0.5_r1] gpt_gather_gpt_5_6_fast...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:57:45

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.819

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.55) and found a novel correct solution (novelty=0.85, correctness=100%). Cost: $0.5667, ~1324J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.551 |
| Architecture div | 0.600 |
| Structure div | 0.186 |
| Thinking ratio | 4.3% |
| Quality/$ | 172 |
| Quality/J | 0.0008 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 43% (3/7 constraints) |
| Lines of code | 291 |
| Cyclomatic complexity | 59.0 |
| Code quality | 0.344 |
| Novelty vs baseline | 0.851 |
| **Composite** | **0.675** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 30 |
| Completion tokens | 5,262 |
| Reasoning tokens | 237 |
| **Total tokens** | **5,529** |
| Thinking ratio | 4.3% |
| Output efficiency | 95.2% |
| Input cost | $0.000008 |
| Output cost | $0.005788 |
| Reasoning cost | $0.000033 |
| **Total cost** | **$0.566750** |
| **Total energy** | **~1324 J** |
| Solution density | 0.052632 LOC/tok |
| Correctness/$ | 172 |
| Quality/J | 0.000510 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.5667  |  **Energy:** ~1324J  |  **Thinking:** 4%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 3 |
| Total lines | 291 |
| Functions | 36 |
| Classes | 1 |
| Functions/file | 12.0 |
| Classes/file | 0.3 |
| Avg lines/file | 97 |
| Type hints | 38% |
| Docstrings | 0% |
| Error handlers | 5 |
| Imports | 17 |
| Decorators | 20 |
| Test files | 2 |
| Test file rate | 67% |
| Parse errors | 0 |

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_vtp26dz3/code/)
