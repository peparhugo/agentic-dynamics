# Game Report: inject_alien_vocab_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_alien_vocab_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:47:24

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.831

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.75) and found a novel correct solution (novelty=0.97, correctness=100%). Cost: $0.0146, ~3599J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.748 |
| Architecture div | 0.875 |
| Structure div | 0.357 |
| Thinking ratio | 7.2% |
| Quality/$ | 68 |
| Quality/J | 0.0003 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 14% (1/7 constraints) |
| Lines of code | 799 |
| Cyclomatic complexity | 87.0 |
| Code quality | 0.125 |
| Novelty vs baseline | 0.969 |
| **Composite** | **0.563** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 7,838 |
| Completion tokens | 10,073 |
| Reasoning tokens | 1,394 |
| **Total tokens** | **19,305** |
| Thinking ratio | 7.2% |
| Output efficiency | 52.2% |
| **Total cost** | **$0.014644** |
| **Total energy** | **~3599 J** |
| Solution density | 0.041388 LOC/tok |
| Correctness/$ | 75 |
| Quality/J | 0.000157 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.0146  |  **Energy:** ~3599J  |  **Thinking:** 7%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_e6nmmhtb/session.jsonl)
- [Generated code](./exp_e6nmmhtb/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 18 |
| JS files | 7 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1260 |
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
