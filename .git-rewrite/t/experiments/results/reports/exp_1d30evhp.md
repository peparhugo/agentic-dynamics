# Game Report: inject_phantom_success_s0.5_r1-perturbed

**Model:** openai/gpt-5.6  |  **Task:** [inject_phantom_success_s0.5_r1] gpt_gather_gpt_5_6...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:12:50

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.812

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.82) with moderate resource use ($0.3341, ~1672J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.252 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.015 |
| Thinking ratio [C] | 6.0% |
| Quality/$ [C] | 3 |
| Quality/J [C] | 0.0006 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 100% (7/7 constraints) |
| Lines of code [M] | 407 |
| Cyclomatic complexity [C] | 70.0 |
| Code quality [H] | 0.246 |
| Novelty vs baseline [H] | 0.825 |
| **Composite [H]** | **0.823** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 30 |
| Completion tokens [M] | 6,419 |
| Reasoning tokens [M] | 412 |
| Cache read tokens [M] | 83,084 |
| Cache write tokens [M] | 14,000 |
| **Total tokens** | **6,861** |
| Thinking ratio [C] | 6.0% |
| Output efficiency [C] | 93.6% |
| Input cost [M] | $0.000081 |
| Output cost [M] | $0.138125 |
| Reasoning cost [M] | $0.008865 |
| Cache cost [M] | $0.187051 |
| **Total cost** | **$0.334122** |
| **Total energy [X]** | **~1672 J** |
| Solution density [C] | 0.059321 LOC/tok |
| Correctness/$ [C] | 6 |
| Quality/J [C] | 0.000492 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.3341  |  **Energy:** ~1672J  |  **Thinking:** 6%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_1d30evhp/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 3 |
| Total lines (Py) | 407 |
| Functions | 34 |
| Classes | 0 |
| Functions/file | 11.3 |
| Classes/file | 0.0 |
| Avg lines/file | 136 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 5 |
| Imports | 12 |
| Decorators | 22 |
| Test files | 1 |
| Test file rate | 33% |
| Parse errors | 0 |
