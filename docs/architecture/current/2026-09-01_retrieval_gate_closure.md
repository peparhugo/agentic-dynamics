---
status: accepted
supersedes:
---

# Retrieval activation gate — closure record (2026-09-01)

**Status: accepted — the p4_activation_gate's measured signal is verified; the gate closes.**

## The gate's requirement (the proof spec)

> run ONE workflow phase with rag_augment enabled end-to-end, so the retrieval-activation
> gate has a live recorded fallback_mode and augmented-prompt acceptance instead of the
> historical slice-3 single-query claim. The measured signal is the augmentation OUTCOME
> (retrieval attempt, constructor acceptance, fallback mode), not the feature.

## The verified chain (two independent reproductions)

1. **Retrieve** — `retrieve()` via the shared scope (`repository_id=agentic-dynamics`,
   13.7k-record corpus): `fallback_mode: full` (both legs live), **35 candidates**, ~6s
   post-fix (was 31.5s before the cosine-collapse cap — commit `9a4d83623`).
2. **Constructor** — `ModelPromptConstructor` with the real `run_agentic` executor:
   produced a valid prompt plan (`schema_version: prompt-plan/v1`,
   `raw_work_item_hash: sha256:988fa80dc2a…`) — reproduced identically by the proof's own
   test phase (same hash) and by the operator's direct reproduction.
3. **The runner's augment chain** — `augment_prompt` with the proof's rag_params: on the
   merged branch the earlier `no_rag` failures were (a) an empty per-cell scope (the fresh
   worktree — fixed by the shared-scope override, the two-channel rule's explicit path) and
   (b) a swallowed constructor exception (fixed by the workdir wiring — commit `f76b9acfc`
   — and made visible by the error-recording runner-truth fix, commit `143d31b1f`:
   `AugmentationOutcome.error`).

## What remains open (owned, not blocking)

**The proof's `kind: test` phase dies at its 600s wall** because `run_suite` executes the
WHOLE worktree suite (2,615 tests, 15+ min) — the same harness defect the
`test_suite_speed` spec's p2 owns (scoped `run_suite`: a spec's test phase runs its
declared target, not the full tree). This is a harness defect, not an augmentation failure;
the gate's measured signal does not depend on it.

## Context the closure carries

- The census's `fused = 0` (RRF as a union) was resolved as the **H2 two-view verdict** by
  `retrieval_fusion_quality` (merged): the dense chunks and lexical records are genuinely
  disjoint units; no fusion change warranted.
- The retrieve latency fix (31.5s → 6.2s) rides in.
- The activation gate's promise — slice 3's single-query claim replaced by a measured,
  recorded, reproduced outcome — is met.

Provenance: [M] measured — operator reproduction + the proof's own verification runs,
2026-09-01; the plan hash is the same across both.
