# Game Report: inject_phantom_success_s0.5_r2-perturbed

**Model:** openai/gpt-5-nano  |  **Task:** [inject_phantom_success_s0.5_r2] gpt_final_gpt_5_nano...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:54:14

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.777

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=70%, quality=0.67) with moderate resource use ($0.0044, ~3547J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.477 |
| Architecture div | 0.400 |
| Structure div | 0.182 |
| Thinking ratio | 16.9% |
| Quality/$ | 116 |
| Quality/J | 0.0003 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 70% (0/0 tests) |
| Constraint satisfaction | 0% (0/7 constraints) |
| Lines of code | 165 |
| Cyclomatic complexity | 23.0 |
| Code quality | 0.617 |
| Novelty vs baseline | 0.875 |
| **Composite** | **0.671** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 11,831 |
| Completion tokens | 4,506 |
| Reasoning tokens | 3,328 |
| **Total tokens** | **19,665** |
| Thinking ratio | 16.9% |
| Output efficiency | 22.9% |
| Input cost | $0.003194 |
| Output cost | $0.004957 |
| Reasoning cost | $0.000466 |
| **Total cost** | **$0.004373** |
| **Total energy** | **~3547 J** |
| Solution density | 0.008391 LOC/tok |
| Correctness/$ | 81 |
| Quality/J | 0.000189 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 70%  |  **Cost:** $0.0044  |  **Energy:** ~3547J  |  **Thinking:** 17%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines | 165 |
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


---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_l05r7o3a/code/)
