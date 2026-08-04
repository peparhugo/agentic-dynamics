# Game Report: data_table-baseline

**Model:** openai/gpt-5.6  |  **Task:** [batch:data_table:baseline] gpt_5_6...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:49:20

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.691

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=80%, quality=0.61) with moderate resource use ($0.7978, ~4255J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 7.2% |
| Quality/$ | 56 |
| Quality/J | 0.0002 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 25% (1/4 constraints) |
| Lines of code | 52 |
| Cyclomatic complexity | 7.0 |
| Code quality | 0.883 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.607** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 45 |
| Completion tokens | 15,959 |
| Reasoning tokens | 1,235 |
| **Total tokens** | **17,239** |
| Thinking ratio | 7.2% |
| Output efficiency | 92.6% |
| Input cost | $0.000012 |
| Output cost | $0.017555 |
| Reasoning cost | $0.000173 |
| **Total cost** | **$0.797777** |
| **Total energy** | **~4255 J** |
| Solution density | 0.003016 LOC/tok |
| Correctness/$ | 45 |
| Quality/J | 0.000143 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 80%  |  **Cost:** $0.7978  |  **Energy:** ~4255J  |  **Thinking:** 7%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 1 |
| Total lines | 52 |
| Functions | 7 |
| Classes | 0 |
| Functions/file | 7.0 |
| Classes/file | 0.0 |
| Avg lines/file | 52 |
| Type hints | 14% |
| Docstrings | 0% |
| Error handlers | 0 |
| Imports | 2 |
| Decorators | 0 |
| Test files | 1 |
| Test file rate | 100% |
| Parse errors | 0 |

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_batch_batch_data_table_baseline gpt_5_6/session.jsonl)

*No code output — this session was narration-only.*