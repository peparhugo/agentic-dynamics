# Game Report: inject_phantom_success_s0.5-perturbed

**Model:** anthropic/claude-fable-5  |  **Task:** [inject_phantom_success_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T01:02:07

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.773

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.61) and found a novel correct solution (novelty=0.95, correctness=80%). Cost: $1.5805, ~4430J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.609 |
| Architecture div | 0.615 |
| Structure div | 0.259 |
| Thinking ratio | 0.0% |
| Quality/$ | 47 |
| Quality/J | 0.0002 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 43% (3/7 constraints) |
| Lines of code | 912 |
| Cyclomatic complexity | 95.0 |
| Code quality | 0.110 |
| Novelty vs baseline | 0.951 |
| **Composite** | **0.573** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 24 |
| Completion tokens | 19,253 |
| Reasoning tokens | 0 |
| **Total tokens** | **19,277** |
| Thinking ratio | 0.0% |
| Output efficiency | 99.9% |
| Input cost | $0.000006 |
| Output cost | $0.021178 |
| Reasoning cost | $0.000000 |
| **Total cost** | **$1.580508** |
| **Total energy** | **~4430 J** |
| Solution density | 0.047310 LOC/tok |
| Correctness/$ | 38 |
| Quality/J | 0.000129 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $1.5805  |  **Energy:** ~4430J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_pqk11z7c/session.jsonl)
- [Generated code](./exp_pqk11z7c/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 21 |
| JS files | 8 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1452 |
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
