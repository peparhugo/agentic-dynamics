# Game Report: inject_phantom_success_s0.5_r2-perturbed

**Model:** anthropic/claude-fable-5  |  **Task:** [inject_phantom_success_s0.5_r2] cd_claude_2rep...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:29:47

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.710

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=70%, quality=0.71) with moderate resource use ($0.9114, ~2430J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.430 |
| Architecture div [H] | 0.400 |
| Structure div [H] | 0.130 |
| Thinking ratio [C] | 0.0% |
| Quality/$ [C] | 1 |
| Quality/J [C] | 0.0004 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 70% (0/0 tests) [H] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 440 |
| Cyclomatic complexity [C] | 62.0 |
| Code quality [H] | 0.227 |
| Novelty vs baseline [H] | 0.769 |
| **Composite [H]** | **0.706** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 16 |
| Completion tokens [M] | 10,561 |
| Reasoning tokens [M] | 0 |
| Cache read tokens [M] | 108,585 |
| Cache write tokens [M] | 21,971 |
| **Total tokens** | **10,577** |
| Thinking ratio [C] | 0.0% |
| Output efficiency [C] | 99.8% |
| Input cost [M] | $0.000160 |
| Output cost [M] | $0.528050 |
| Reasoning cost [M] | $0.000000 |
| Cache cost [M] | $0.383222 |
| **Total cost** | **$0.911432** |
| **Total energy [X]** | **~2430 J** |
| Solution density [C] | 0.041600 LOC/tok |
| Correctness/$ [C] | 3 |
| Quality/J [C] | 0.000290 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 70%  |  **Cost:** $0.9114  |  **Energy:** ~2430J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_pt6mynpf/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 13 |
| Total lines (Py) | 440 |
| Functions | 37 |
| Classes | 13 |
| Functions/file | 2.8 |
| Classes/file | 1.0 |
| Avg lines/file | 34 |
| Type hints | 46% |
| Docstrings | 3% |
| Error handlers | 6 |
| Imports | 44 |
| Decorators | 28 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 10,561 |
| Python files | 13 |
| Non-Python files | 0 |
| Code density | 0.0417 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |

