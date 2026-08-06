# Game Report: inject_phantom_success_s0.5-perturbed

**Model:** openai/gpt-5  |  **Task:** [inject_phantom_success_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:47:06

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.757

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.70) and found a novel correct solution (novelty=0.98, correctness=80%). Cost: $0.1477, ~4399J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.703 |
| Architecture div | 0.667 |
| Structure div | 0.469 |
| Thinking ratio | 10.2% |
| Quality/$ | 7 |
| Quality/J | 0.0002 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 29% (2/7 constraints) |
| Lines of code | 475 |
| Cyclomatic complexity | 72.0 |
| Code quality | 0.211 |
| Novelty vs baseline | 0.983 |
| **Composite** | **0.555** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 15,390 |
| Completion tokens | 8,280 |
| Reasoning tokens | 2,688 |
| **Total tokens** | **26,358** |
| Thinking ratio | 10.2% |
| Output efficiency | 31.4% |
| **Total cost** | **$0.147749** |
| **Total energy** | **~4399 J** |
| Solution density | 0.018021 LOC/tok |
| Correctness/$ | 59 |
| Quality/J | 0.000126 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.1477  |  **Energy:** ~4399J  |  **Thinking:** 10%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_bh23zs7r/session.jsonl)
- [Generated code](./exp_bh23zs7r/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 7 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 447 |
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
