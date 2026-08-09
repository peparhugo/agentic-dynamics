# Game Report: inject_phantom_success_s0.5_r2-perturbed

**Model:** openai/gpt-5-nano  |  **Task:** [inject_phantom_success_s0.5_r2] gpt_final_gpt_5_nano...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:35:57

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.777

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=70%, quality=0.80) with moderate resource use ($0.0044, ~3547J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.477 |
| Architecture div [H] | 0.400 |
| Structure div [H] | 0.182 |
| Thinking ratio [C] | 16.9% |
| Quality/$ [C] | 229 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 70% (0/0 tests) [H] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 165 |
| Cyclomatic complexity [C] | 23.0 |
| Code quality [H] | 0.617 |
| Novelty vs baseline [H] | 0.875 |
| **Composite [H]** | **0.800** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 11,831 |
| Completion tokens [M] | 4,506 |
| Reasoning tokens [M] | 3,328 |
| Cache read tokens [M] | 129,664 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **19,665** |
| Thinking ratio [C] | 16.9% |
| Output efficiency [C] | 22.9% |
| Input cost [M] | $0.000371 |
| Output cost [M] | $0.001131 |
| Reasoning cost [M] | $0.000836 |
| Cache cost [M] | $0.002035 |
| **Total cost** | **$0.004373** |
| **Total energy [X]** | **~3547 J** |
| Solution density [C] | 0.008391 LOC/tok |
| Correctness/$ [C] | 4 |
| Quality/J [C] | 0.000225 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 70%  |  **Cost:** $0.0044  |  **Energy:** ~3547J  |  **Thinking:** 17%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_l05r7o3a/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines (Py) | 165 |
| Functions | 18 |
| Classes | 3 |
| Functions/file | 9.0 |
| Classes/file | 1.5 |
| Avg lines/file | 82 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 4 |
| Imports | 10 |
| Decorators | 11 |
| Test files | 1 |
| Test file rate | 50% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 4,506 |
| Python files | 2 |
| Non-Python files | 0 |
| Code density | 0.0366 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |

