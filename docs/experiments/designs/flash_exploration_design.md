---
status: proposed
---

# flash_exploration — design (p0): closing the KB read loop and measuring flash's design diversity

**Question.** `deepseek/deepseek-v4-flash` is the machine's workhorse and the cheap subject
model, but its *creative range* has never been measured, and the knowledge base it produces
has never been read back into generation. Why not — mechanically — and what is the minimal
build that makes the loop `derive → retrieve → act → re-derive` real and measurable?

This document is the research/design artifact for the `flash_exploration_build` wave. It is
**committed before the wave runs**; the wave's `p0_research_verify` phase must re-verify every
claim below against the pinned files (`git hash-object` same-content) and mark this document
`accepted` only if all claims hold, or correct it. No implementation phase may start before
that gate passes.

## 0. Pins

Base: `feature/flash-exploration` at `bd5c530e2ee05f359eb759695af985a6cc7410ce` (main HEAD
`bd5c530e2`). All findings below were read at these SHAs; a claim whose file hash differs at
verification time is **stale** and must be re-derived.

| Artifact | SHA256 |
|---|---|
| `src/agentic_dynamics/knowledge/retrieval.py` | `116a76efb73f83590c365da8de81063b3c634c23112fb4b8ad4c2889cc3715b0` |
| `src/agentic_dynamics/knowledge/graph.py` | `2de561edfb9aa93ac60dc94c916f518ead698dee17dff5fd5e0501d64279a449` |
| `src/agentic_dynamics/knowledge/augment.py` | `9b4a8bcf7cbb4102c56e9334e4c69b6f8af9638bc86781a94179caa885b6264d` |
| `src/agentic_dynamics/control/reducers/pattern.py` | `cab1ae1e0b3ab4f2918116c528949e9d9436b725d10db87c62aed521477b8a70` |
| `src/agentic_dynamics/control/fact_ingestion.py` | `eeb720eac7a954404287c4d388a7fa79366875c2c7bc82a78a06b9accaae6f8f` |
| `src/agentic_dynamics/measurement/basin.py` | `bc24affdce226c24904892df1e340b6cd6dcad7ac645927f3316c6dcb9092374` |
| `src/agentic_dynamics/runtime/workflow_runner.py` | `6be6d072f660d0ec7152d7208eb2141a9741d48e1550426e65b033bcf2ac3d22` |
| `scripts/run.py` | `ea86f1b9370214bbe8c5ad81ba10e913b6c2cca4e76439b9bd3aac8bd484e9c9` |
| `scripts/kb_produce_facts.py` | `79ee63447eb94ed433ccb19f0d03ffe02dd55dbe55d94dd12f0c7971878055f8` |
| `workflows/repository/retrieval_activation_augment_proof.yaml` | `44dd42a052a9caef8756994a375761d82245587ff346ef68ed61480b69a43139` |

## 1. Findings (the mechanical reason the KB has never paid off)

**F1 — the commit hard-gate excludes every knowledge authority in a fresh worktree.**
`retrieval.freshness_multiplier` returns `None` (exclude) for
`Authority.SOURCE | MEASURED | DERIVED` whose non-empty `commit_sha != current_commit`
(`retrieval.py:548-554`). Every run happens at a fresh commit; phase findings are MEASURED and
stamped at that commit; pattern projections are DERIVED. The same hard gate exists twice more:
`_dense_filter`'s Chroma `where` (`retrieval.py:1726-1735`) and the lexical leg's Cypher
(`graph.py:1388-1392`, `commit=commit_sha` from `retrieval.py:1406-1408`). **Consequence:** in
any new worktree, essentially the entire learned corpus is filtered out *before ranking*. The
one augmentation run that recorded `fallback_mode="full"` injected **zero evidence**
(`selected_evidence_ids: []`, ledger `retrieval_activation_augment_proof/20260901T031548Z.json`).

**F2 — patterns were never projected, and the proof arm never asked for them.**
`scripts/kb_produce_facts.py --reducer pattern/v1` mints pattern *facts*; the projection into
`source_type="pattern"` retrieval records landed a week later (`523c0bac1`, merged `eb2697459`)
than the last mint (`38ba8d49b`, 2026-08-25). Live state: 6 pattern facts, **0 pattern
projection artifacts**, 0 registry `pattern-content=` rows. The only shipped spec with
`rag_augment: true` (`retrieval_activation_augment_proof.yaml:26-33`) does **not** set
`rag.pattern_projection: true`, and the retrieval gate admits patterns only when that flag is
true (`retrieval.py:1297-1313`). Patterns were doubly invisible.

**F3 — pattern minting churns its own facts on every commit.**
`pattern.py:229` sets `validity_window=inp.source_revision or REVISION_FALLBACK`, and
`kb_produce_facts.py:1237` defaults `revision = git_head_sha()`. `fact_fingerprint` excludes
`evidence_ids`/`inputs_digest` but **not** `value.validity_window`
(`fact_ingestion.py:99-115`), so a new HEAD changes the fingerprint with zero real change and
supersedes every pattern fact (dry-run today: 6 supersedes + 6 projections). The review
`docs/reviews/cap_pattern_minting_review.md:39` records this as the mandatory fix.
`fact_payload` (`fact_ingestion.py:62-77`) carries no `source_revision`, so stabilizing
`validity_window` alone fixes the churn.

**F4 — augmentation is workflow-phase-only and its failures were half-observable.**
`rag_augment` exists only in `workflow_runner.py` (enablement `:3022-3031`, seam `:3317-3345`);
`run.py`/`run_story.py` have zero references. Of five proof runs, four fell back to `no_rag`:
empty per-cell scope (fixed by the shared-scope override) and a swallowed constructor
exception (fixed by `f76b9acfc`), but `AugmentationOutcome.error` is still not persisted in the
run ledger (`augment.py:205` set; `PhaseResult.to_dict()` does not carry it).

**F5 — no diversity instrument exists; run.py cannot even preserve k attempts.**
`measure_basin_escape` is baseline-vs-perturbed and pure over code strings
(`basin.py:146-168`); `_architecture_divergence`/`_structure_divergence`/`_compute_novelty`
(`basin.py:274-340`) are private and callable pairwise. No portfolio metric exists. In
`scripts/run.py`, artifact/report slugs collide across `seed_variant`/`repetition`
(`:460`, `:507`), and `_save_results` strips `final_response` (`:404`), so attempts overwrite
each other and the produced code is not recoverable from the result JSON.

**F6 — hygiene risks on the read path (not build blockers, but measurement hazards).**
36,972 dead letters sit behind `lag=0` watermarks (28,613 from the 2026-09-04 corpus-root
incident); `reconcile_missing` is a no-op in v1; the Chroma handler skips `fact` records and
ignores deletes. Any "retrieval works" claim must be a direct probe, never a lag reading.

## 2. Approach (what the wave builds)

**B1 — reachability (retrieval, 3 layers).** The commit gate exists to keep another branch's
**code** from surfacing (`SOURCE`); it must not gate *knowledge*. Change: hard commit exclusion
for `Authority.SOURCE` only; `MEASURED`/`DERIVED` fall through to neutral freshness (1.00), and
`ADVISORY` keeps its 30/90-day windows. Mirror at the two store layers: the Chroma `where`
`$or` gains the knowledge authorities; the lexical Cypher gains an exempt-authority clause.
Tests pin all three layers, both directions (SOURCE mismatch excluded; knowledge mismatch
admitted).

**B2 — pattern stability + projection.** Replace the reducer's `validity_window` with a
deterministic evidence digest (changes only when the evidence set changes). Add a
cross-revision idempotency test. Re-mint + project into the live KB (data-plane act, after the
build wave, with the cross-commit probe as proof).

**B3 — portfolio-diversity instrument.** New `measurement/diversity.py`:
`pairwise_divergence(a, b)` and `portfolio_diversity(samples, threshold=0.5)` over the existing
basin primitives (no third novelty copy). It reports means/max/`distinct_fraction` and
`coverage`; means are `None` below n=2 — never fabricated zeros. `run.py` preserves per-attempt
code and stops colliding variant/rep slugs (only adding suffixes when variant/rep are
non-default). Unit tests for identical/divergent/single/empty portfolios.

**B4 — the ladder (the experiment the instrument feeds).** Flash, one open-ended task,
4 conditions × 3 reps through one workflow harness. Conditions: C0 neutral brief; C1
divergence-framed brief (enumerate ≥3 materially different designs, implement one); C2 high
thinking budget; C3 KB-augmented (`rag_augment: true`, `pattern_projection: true`, shared
scope). Primary metric: portfolio composite diversity per condition, paired with independent
test quality; secondary: novelty, cost, tokens. Full registration (hypotheses, margins, stop,
decision rule) lands in `flash_exploration_preregistration.md` before any cell runs, pinning
the ladder specs by SHA256.

**Rejected alternatives.** (a) New-task brief with no corpus relevance — the KB arm would be
retrieval-irrelevant (the 64-finding corpus is `task_manager`/`process_perturbation_resample`);
the task must be task-manager-family. (b) Retrieval-augment inside `run.py` — a new seam in a
plane that has none; B1 makes the existing workflow seam work. (c) Empty the projection
`commit_sha` instead of changing the gate — hides provenance and leaves the SOURCE rationale
untouched; the gate is the honest place. (d) A new "creativity" score — one construct at a
time; pairwise divergence is the existing, pinned primitive.

## 3. Gates (DONE_WHEN)

- **G-research:** every §1 claim re-verified against the pinned SHAs; discrepancies listed;
  this document marked `accepted` or corrected.
- **G-B1:** three layer tests + a direct probe from a worktree at commit X retrieving a
  MEASURED finding and a DERIVED pattern minted at commit Y (X≠Y); `pattern_projection=False`
  returns no patterns.
- **G-B2:** cross-revision dry-run emits 0 supersedes / 0 projections; live mint emits exactly
  6 projections; a second dry-run converges.
- **G-B3:** `pytest tests/test_diversity.py` green; identical → 0, divergent → >0, single/empty
  → None means; `run.py` rep artifacts unique and code recoverable.
- **G-adversary:** the adversarial phase (different model) falsifies the three builds or
  records a clean sweep with re-verification; a bare PASS is a failed review.
- **G-test:** the independent test phase runs the four suites.

## 4. Risks / known failure points

| # | Risk | Mitigation in the build |
|---|---|---|
| R1 | `pattern_projection` defaults False | ladder spec sets it true; G-B1 probes both ways |
| R2 | projection `commit_sha` mismatch | B1 makes DERIVED reachable regardless; probe at X≠Y |
| R3 | churn survives via another field | cross-revision idempotency test; `fact_payload` has no `source_revision` (F3) |
| R4 | workers down / dead-letter | direct `retrieve()` probe, never lag; report honestly |
| R5 | constructor failure invisible | persisted `AugmentationOutcome.error` is a listed non-blocking gap; ladder KB arm reports `fallback_mode` from the ledger |
| R6 | diversity metric gameable (small n) | prereg restricts the claim: n=3 pilot, effect sizes descriptive, CI via bootstrap reported but not decisive; confirmatory grid only on signal |
| R7 | agent edits the contract tests | scorer checks `git diff <base> -- tests/` is empty; a modified test invalidates the cell |
| R8 | manifest staleness changes the finding corpus | mint + ladder pinned to the manifest identity in the prereg |

## 5. Non-goals

- No policy arm is written in this wave; the ladder produces information, not a control rule.
- No retrieval-semantics change beyond the commit gate; pattern ranking weights are untouched.
- No change to the write side other than the pattern window.
