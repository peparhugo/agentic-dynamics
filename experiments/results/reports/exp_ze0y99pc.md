# Game Report: inject_alien_vocab_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_alien_vocab_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T01:11:42

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.763

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.73) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0200, ~4860J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.734 |
| Architecture div | 0.875 |
| Structure div | 0.311 |
| Thinking ratio | 6.1% |
| Quality/$ | 54 |
| Quality/J | 0.0002 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 14% (1/7 constraints) |
| Lines of code | 742 |
| Cyclomatic complexity | 54.0 |
| Code quality | 0.135 |
| Novelty vs baseline | 0.967 |
| **Composite** | **0.495** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 10,865 |
| Completion tokens | 14,049 |
| Reasoning tokens | 1,616 |
| **Total tokens** | **26,530** |
| Thinking ratio | 6.1% |
| Output efficiency | 53.0% |
| Input cost | $0.002934 |
| Output cost | $0.015454 |
| Reasoning cost | $0.000226 |
| **Total cost** | **$0.020026** |
| **Total energy** | **~4860 J** |
| Solution density | 0.027968 LOC/tok |
| Correctness/$ | 43 |
| Quality/J | 0.000102 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0200  |  **Energy:** ~4860J  |  **Thinking:** 6%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_ze0y99pc/session.jsonl)
- [Generated code](./exp_ze0y99pc/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 10 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 733 |
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
