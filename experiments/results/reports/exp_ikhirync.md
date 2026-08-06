# Game Report: inject_alien_vocab_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_alien_vocab_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:58:10

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.760

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.73) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0159, ~4083J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.735 |
| Architecture div | 0.857 |
| Structure div | 0.336 |
| Thinking ratio | 7.8% |
| Quality/$ | 68 |
| Quality/J | 0.0002 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 14% (1/7 constraints) |
| Lines of code | 700 |
| Cyclomatic complexity | 52.0 |
| Code quality | 0.143 |
| Novelty vs baseline | 0.970 |
| **Composite** | **0.497** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 10,037 |
| Completion tokens | 10,679 |
| Reasoning tokens | 1,753 |
| **Total tokens** | **22,469** |
| Thinking ratio | 7.8% |
| Output efficiency | 47.5% |
| Input cost | $0.002710 |
| Output cost | $0.011747 |
| Reasoning cost | $0.000245 |
| **Total cost** | **$0.015927** |
| **Total energy** | **~4083 J** |
| Solution density | 0.031154 LOC/tok |
| Correctness/$ | 54 |
| Quality/J | 0.000122 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0159  |  **Energy:** ~4083J  |  **Thinking:** 8%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_ikhirync/session.jsonl)
- [Generated code](./exp_ikhirync/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 19 |
| JS files | 8 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1040 |
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
