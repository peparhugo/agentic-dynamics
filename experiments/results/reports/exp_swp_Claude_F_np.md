# Game Report: perturbed-baseline

**Model:** anthropic/claude-fable-5  |  **Task:** [silent_sweep:perturbed:natural] Claude_Fable_5...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:56:59

---

## Strategy
**Classification:** WASTEFUL
**Score:** 0.310

**Verdict:** WASTEFUL — model burned 846 tokens ($0.2206, ~194J, 0% thinking) achieving only 10% correctness. High reasoning overhead without convergence.

**Recommendation:** Reduce perturbation strength or avoid this operator class.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 0.0% |
| Quality/$ | 1,080 |
| Quality/J | 0.0052 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 10% (0/0 tests) |
| Constraint satisfaction | 0% (0/7 constraints) |
| Lines of code | 21 |
| Cyclomatic complexity | 1.0 |
| Code quality | 0.983 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.350** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 6 |
| Completion tokens | 840 |
| Reasoning tokens | 0 |
| **Total tokens** | **846** |
| Thinking ratio | 0.0% |
| Output efficiency | 99.3% |
| Input cost | $0.000002 |
| Output cost | $0.000924 |
| Reasoning cost | $0.000000 |
| **Total cost** | **$0.220560** |
| **Total energy** | **~194 J** |
| Solution density | 0.024823 LOC/tok |
| Correctness/$ | 108 |
| Quality/J | 0.001805 |

---

## Headline Metric
**Strategy:** WASTEFUL  |  **Correctness:** 10%  |  **Cost:** $0.2206  |  **Energy:** ~194J  |  **Thinking:** 0%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines | 21 |
| Functions | 0 |
| Classes | 2 |
| Functions/file | 0.0 |
| Classes/file | 1.0 |
| Avg lines/file | 10 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 0 |
| Imports | 3 |
| Decorators | 0 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 50%

| Metric | Value |
|--------|-------|
| Output tokens | 840 |
| Python files | 2 |
| Non-Python files | 0 |
| Code density | 0.0250 LOC/tok |
| **Verdict** | **NARRATION FAILURE — 840 tokens burned, zero code output** |


---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_swp_Claude_F_np/code/)
