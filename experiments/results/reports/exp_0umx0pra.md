# Game Report: inject_phantom_success_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_phantom_success_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:41:58

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.744

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.75) and found a novel correct solution (novelty=0.97, correctness=100%). Cost: $0.0340, ~13486J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.747 |
| Architecture div | 0.857 |
| Structure div | 0.380 |
| Thinking ratio | 50.8% |
| Quality/$ | 29 |
| Quality/J | 0.0001 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 14% (1/7 constraints) |
| Lines of code | 960 |
| Cyclomatic complexity | 90.0 |
| Code quality | 0.104 |
| Novelty vs baseline | 0.968 |
| **Composite** | **0.559** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 8,824 |
| Completion tokens | 11,857 |
| Reasoning tokens | 21,390 |
| **Total tokens** | **42,071** |
| Thinking ratio | 50.8% |
| Output efficiency | 28.2% |
| **Total cost** | **$0.033960** |
| **Total energy** | **~13486 J** |
| Solution density | 0.022819 LOC/tok |
| Correctness/$ | 54 |
| Quality/J | 0.000041 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.0340  |  **Energy:** ~13486J  |  **Thinking:** 51%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_0umx0pra/session.jsonl)
- [Generated code](./exp_0umx0pra/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 12 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 950 |
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
