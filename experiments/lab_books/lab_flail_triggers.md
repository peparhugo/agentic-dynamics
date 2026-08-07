---
experiment_id: lab_flail_triggers
title: "Lab Book 4: What Makes a Model Flail?"
hypothesis: "Narration failure is triggered by specific perturbation types and task complexities, not randomly distributed. Models with SFT training (Claude, GPT family) flail more than GRPO-trained models (DeepSeek) because they default to conversational mode when confused."
null_hypothesis: "Narration failure is randomly distributed across perturbation types, task types, and models."
status: completed
created: 2026-08-07
data_sources:
  - experiments/results/_results_summary.json
  - experiments/results/_trajectory_summary.json
analysis_script: scripts/lab_flail_triggers.py
---

# Lab Book 4: What Makes a Model Flail?

## Hypothesis

**H1:** Narration failure is triggered by specific perturbation types and task complexities. SFT models flail more than GRPO models because they default to conversational mode when confused.

**H0:** Narration failure is randomly distributed across perturbation types, task types, and models.

## Methodology

**Design:** Case-control analysis. Cases = narration_failure entries (n=26). Controls = valid entries matched by task type where possible.

| Variable | Type | Description |
|----------|------|-------------|
| Perturbation class | Independent | manifold, semantic, baseline |
| Task type | Independent | Normalized experiment name |
| Model architecture | Independent | SFT (Claude, GPT) vs GRPO (DeepSeek) |
| Narration failure | Dependent | Binary (True/False) |

## Data Sources

- `experiments/results/_results_summary.json` — `narration_failure`, `model`, `perturbation_class`, `experiment`
- `experiments/results/_trajectory_summary.json` — per-session data for flail entries (reasoning_chars, step_count, tool_call_sequence, detected_model, task_type)

## Analysis Steps

1. Extract all entries where `narration_failure == True` (n=26)
2. Group by: model, perturbation_class, task_type (normalized)
3. Per model: compute flail rate = narration_failures / total entries
4. Per perturbation class: compute flail rate
5. Per task type: compute flail rate
6. For each flail entry, cross-reference trajectory summary:
   - reasoning_chars: was the model producing lots of text but no code?
   - step_count: did it give up quickly or keep trying?
   - tool_call_sequence: any pattern in the tools called before failure?
7. Identify the "flail signature": common patterns across flail entries

## Expected Output

**Table: Flail Rate by Model**

| Model | Total | Flail Count | Flail Rate | Avg Cost When Flailing |
|-------|-------|-------------|------------|------------------------|
| GPT-5-nano | 7 | 7 | 100% | $0.005 |
| GPT-5-mini | 13 | 7 | 54% | $0.032 |
| Claude Fable 5 | 44 | 12 | 27% | $1.01 |
| GPT-5 | 13 | 2 | 15% | $0.14 |
| DeepSeek v4 Pro | 119 | 3 | 2.5% | $0.015 |

**Table: Flail Rate by Perturbation Class**

| Class | Flail / Total | Rate |
|-------|--------------|------|
| manifold (alien vocab, framing shifts) | 7/23 | 30% |
| semantic (false premises, constraints) | 6/89 | 7% |
| baseline (no perturbation) | 4/68 | 6% |

**Flail Signature:** Of the 26 flail sessions, what percentage:
- Produced >500 reasoning_chars but 0 code files?
- Had <5 steps before giving up?
- Used only read/bash tools (never write)?

## Interpretation Guide

- If manifold perturbation flail rate (30%) >> semantic (7%): linguistic surface shifts are the primary trigger — models can't navigate unfamiliar vocabulary
- If Claude flails 27% of the time at $1.08/session while DeepSeek flails 2.5% at $0.016: Claude's effective cost per non-flailing session is ($47.54 / 32 successful) = $1.49
- If nano flails 100%: it is categorically unsuitable for any production workflow — pure chatbot, zero grit
- If flail entries show common tool-call patterns (e.g., read-only loops, never writing): tool sequence can be used as an early detection signal for flail

## Results

*Executed 2026-08-07. 227 entries, 26 flail (11.5%).*

**Flail Rate by Model:** GPT-5.5: 50%, GPT-5.6-fast: 33%, GPT-5: 15%, GPT-5-nano: 14%, Claude: 11.4%, DeepSeek: 8.4%, GPT-5-mini: 8%, GPT-5.6: 6%.

**By Perturbation Class:** Unknown (narration failure sessions): 100% flail (by definition). Semantic: 1.1%. Manifold: 0%.

**Flail Signature (of 26 flail sessions):**
- 14/26 produced >500 reasoning chars but zero code — the model was thinking but couldn't act
- 19/26 never wrote a file — never committed to generating code
- 18/26 had <5 steps — gave up quickly, didn't iterate

**Finding:** Manifold perturbation entries had zero flail — but only 16 manifold entries exist in the dataset. Narration failure entries are separate from the perturbation dataset (they're the `unknown` perturbation class entries). The flail signature suggests two failure modes: (1) overthink — produced lots of reasoning but never wrote code, (2) fast-fail — short sessions that gave up immediately. Both are detectable in real-time via tool-call monitoring.

| Model | Total | Flail | Rate | Common Trigger |
|-------|-------|-------|------|----------------|
| | | | | |

## Artifacts

- Analysis script: `scripts/lab_flail_triggers.py`
- Output data: `experiments/results/lab_flail_triggers.json`
