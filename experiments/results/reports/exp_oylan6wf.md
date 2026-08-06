# Game Report: inject_alien_vocab_s0.5-perturbed

**Model:** anthropic/claude-fable-5  |  **Task:** [inject_alien_vocab_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:51:19

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.843

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.64) and found a novel correct solution (novelty=0.95, correctness=100%). Cost: $1.8753, ~5315J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.643 |
| Architecture div | 0.667 |
| Structure div | 0.302 |
| Thinking ratio | 0.0% |
| Quality/$ | 1 |
| Quality/J | 0.0002 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 43% (3/7 constraints) |
| Lines of code | 1212 |
| Cyclomatic complexity | 136.0 |
| Code quality | 0.083 |
| Novelty vs baseline | 0.953 |
| **Composite** | **0.638** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 28 |
| Completion tokens | 23,099 |
| Reasoning tokens | 0 |
| **Total tokens** | **23,127** |
| Thinking ratio | 0.0% |
| Output efficiency | 99.9% |
| **Total cost** | **$1.875312** |
| **Total energy** | **~5315 J** |
| Solution density | 0.052406 LOC/tok |
| Correctness/$ | 39 |
| Quality/J | 0.000120 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $1.8753  |  **Energy:** ~5315J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_oylan6wf/session.jsonl)
- [Generated code](./exp_oylan6wf/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 24 |
| JS files | 9 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1988 |
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
