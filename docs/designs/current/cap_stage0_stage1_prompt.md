---
status: accepted
---
# Stage 0 + Stage 1 — Completion Prompt: unlock + backfill the fact store

> Author: operator. Purpose: the exact work that must be COMPLETE before the
> experience→knowledge→routing pipeline (Stages 2–6) can begin. Stage 0 = prerequisites
> (mostly in flight, with acceptance checks). Stage 1 = the retroactive fact backfill — the
> unlock. All paths relative to the repo root. Work is done on a branch; never on main.

---

## STAGE 0 — PREREQUISITES COMPLETE (acceptance, not work)

### 0.1 `cap_shadow_fact_disposition` branch — MERGED to main

The disposition branch must be merged and its claims verified on main:

- [ ] **Merge complete**: `feature/cap-shadow-campaign` + `feature/cap-fact-auto-emit` content
  on main (git log shows both branches' commits reachable from main).
- [ ] **`applied: false` marker live**: `src/agentic_dynamics/control/rules.py`
  `record_shadow_decision` produces records whose body carries `applied: false`; a regression
  test asserts it (search `test_` files for `applied` — a test must exist).
- [ ] **Fact-flow verification recorded**: `docs/designs/current/cap_shadow_fact_disposition.md`
  exists and contains the p3 evidence (one tiny workflow run with `FINOPS_KB_WRITE=1` produced
  KB artifacts + registry rows; idempotency re-checked).
- [ ] **Ops note present**: the doc states the hard requirement — **facts do not flow without
  `FINOPS_KB_WRITE=1`**.

### 0.2 Ops action — `FINOPS_KB_WRITE=1` set

- [ ] The framework environment has `export FINOPS_KB_WRITE=1` (shell rc or the launcher used
  for workflow runs; document WHERE it is set).
- [ ] Verified with a live smoke test: one minimal workflow run, then
  `ls experiments/results/kb/ | wc -l` grows and `experiments/results/registry_index.jsonl`
  gains rows with `source_type="fact"`.

### 0.3 `cap_gate_migration` branch — MERGED to main

- [ ] Merge complete; `docs/designs/current/cap_gate_migration.md` (or equivalent) lists the
  FIX/RECORD table.
- [ ] **The gate is exercised**: `grep -rn "requires_facts:" workflows/ experiments/definitions/`
  returns matches (specs migrated off the legacy vocabulary); every migrated rule passes
  `validate_fact_contracts` against the real registries; every unmappable requirement has a
  BLOCKED row naming its missing producer.
- [ ] `python3 scripts/spec_status.py` re-run; index consistent (94+ specs, no drift).

### 0.4 `cap_routing_evidence_specs` branch — MERGED to main

- [ ] Merge complete; the four ExperimentSpecs exist in `experiments/definitions/`:
  `cap_shadow_comparison.yaml`, `cap_confidence_cascade.yaml`, `cap_coverage_routing_impact.yaml`,
  `cap_grit_strength_grid.yaml`.
- [ ] Each compiles (`compile_spec` or the gate) with the post-migration vocabulary; each states
  its null hypothesis and carries a coverage pre-check rule; `docs/designs/current/
  cap_routing_evidence_specs.md` exists with the four-spec summary + adversarial findings.

### 0.5 `cap_addendum_implement` branch — MERGED to main

- [ ] Merge complete; I8 (`control/profiles.py`), I9 (pattern reducer + `FACT_PREDICATES`
  pattern entry, NO EPISTEMIC_MAP row per D7), I10 (`SessionCheckpoint` +
  `experiments/contexts/session_routing.yaml`, proposal-only actuation) all present; the CAP +
  guard test suites pass on main.

### 0.6 Gate: if ANY of 0.1–0.5 is incomplete, STOP

Do not start Stage 1 until every box above is checked. The backfill assumes: facts can flow
(0.1/0.2), rules can declare real requirements (0.3), the simulation runners exist (0.4), and
the pattern machinery exists (0.5).

---

## STAGE 1 — `cap_fact_backfill`: the retroactive fact store

### 1.1 Corpus inventory (deliverable: the master artifact table)

- [ ] Enumerate and count, writing the full list to the coverage doc:
  - `experiments/results/workflows/**/*.json` — one entry per run; record per run:
    `spec_name`, `model`, `git_sha`, `started_at/ended_at`, `ok`, `total_cost_usd`,
    `phases[]` (per phase: `phase`, `kind`, `status`, `model`, `tokens{in,out,...}`,
    `cost_usd`, `cache_read_tokens`, `session_id`, `commit_hash`, `confidence` if present).
  - `experiments/results/stories/*.json` — one entry per story cell; record per cell:
    story, condition, model, sessions[], per-session tokens/cost/status/session_id.
  - `experiments/results/_results_summary.json` — the single-task experiment entries; record
    per entry: config/model/operators, `attempts[]` with tokens/cost/status/confidence.
- [ ] **Shape variance report**: which sources have `confidence`? `cache_read_tokens`?
  `test_executed_success`? `perturbation_strength`? flat vs nested tokens? cost present or
  None? (This decides what the reducers can emit — nothing else does.)

### 1.2 Coverage pre-check (deliverable: per-predicate coverage table)

- [ ] For each of the 29 `FACT_PREDICATES` entries, compute `n_available / n_total` over the
  corpus (per source family: workflow / story / summary). Include at minimum:
  `spec_status, phase_status, attempt_cost_usd, attempt_tokens_in, attempt_tokens_out,
  attempt_model, attempt_confidence, attempt_cache_hit_rate, phase_test_verified,
  job_status, job_accumulated_cost_usd, current_commit, phase_commit`.
- [ ] Publish `docs/designs/current/cap_fact_backfill_coverage.md` with: the master artifact
  table (1.1), the coverage table, and a verdict per predicate — PRODUCED / PARTIAL /
  UNOBSERVED. **UNOBSERVED is a finding, never a stretch**: a predicate with zero coverage
  must not be force-derived; it is recorded with the instrumentation gap named.
- [ ] Gate: the doc states explicitly which downstream experiments (E1/E2/E3/E4) are evaluable
  given the coverage, and which are inconclusive-by-design.

### 1.3 Extend derivation to stories + summaries (code, additive only)

- [ ] In `scripts/kb_produce_facts.py` (or the producer module it calls), add evidence
  families for `story_session` and `story_result` (and `summary_attempt` where the summary
  shape aligns), following the existing `workflow_run` evidence pattern: content-addressed
  `run_artifact_id` per artifact, `_run_evidence` dedup, per-run identity.
- [ ] Reuse the EXISTING reducer vocabulary (`attempt_facts_v1`, `job_facts_v1`,
  `workflow_facts_v1` signatures) where the fields align; where a field family is absent from
  the source artifact, the corresponding fact is simply not emitted (null-not-zero). **No
  semantic change to any existing reducer** — additions are adapter/extractor-level only.
- [ ] Tests: hermetic fixtures for one story artifact and one summary artifact — derivation
  succeeds, ids are stable, re-derivation is byte-identical, and absent fields stay absent.
- [ ] Guard: `git diff` of `src/agentic_dynamics/control/reducers/` shows ZERO changes.

### 1.4 Run the backfill

- [ ] Run the derivation over the ENTIRE corpus with `FINOPS_KB_WRITE=1` (set for the run).
- [ ] Facts land in `experiments/results/kb/` (content-addressed artifacts) and
  `experiments/results/registry_index.jsonl` (rows with `source_type="fact"`).

### 1.5 Verification (deliverable: the verification table)

- [ ] **Idempotency**: re-run the backfill; registry row count and artifact set are unchanged
  (byte-for-byte no-op) — run the check twice, show both counts.
- [ ] **Per-run identity**: two distinct run artifacts with identical spec/model/phase names
  produce DISTINCT fact entity ids (spot-check the same cell's two runs if the corpus has one).
- [ ] **Evidence provenance**: every emitted fact's `evidence_ids` resolves against its source
  artifact via the in-memory index (the `verify_chain` contract).
- [ ] **No duplicates**: registry rows for the backfill are unique by `knowledge_id`.
- [ ] Run the CAP suites + guards (context plane, reducers, integration, adversarial,
  classification, CLI, dependency direction) — all green on the branch.

### 1.6 Deliverables & acceptance

| Deliverable | Path | Acceptance |
|---|---|---|
| Coverage doc | `docs/designs/current/cap_fact_backfill_coverage.md` | master artifact table + per-predicate coverage + per-experiment evaluability verdict |
| Backfilled store | `experiments/results/kb/` + `registry_index.jsonl` | grows exactly once; idempotent re-run |
| Adapter code | producer module (additive) | zero reducer diffs; hermetic tests |
| Verification table | in the coverage doc §5 | idempotency, identity, provenance, uniqueness all evidenced with numbers |

### 1.7 Hard rules (non-negotiable)

1. Work on a branch (`feature/cap-fact-backfill`), never main; commit `[workflow] <phase>` per phase.
2. NEVER touch the in-flight worktrees/branches (disposition, addendum, migration,
   routing_evidence) — their runners may resume.
3. No semantic changes to reducers; no fabrication of fields absent from artifacts; no
   force-deriving UNOBSERVED predicates.
4. `FINOPS_KB_WRITE=1` only at the emit step; derivation stays pure.
5. If the model provider returns 402/insufficient-balance: STOP and record — do not switch
   providers silently.
6. PASS/FAIL checkpoint log per phase; resumable via `--resume`.

### 1.8 Definition of done

Stage 1 is COMPLETE when: the coverage doc exists with honest per-predicate verdicts; the
store is populated and idempotent; the verification table shows all four checks with numbers;
the CAP suites pass; and the doc states the evaluability verdict for E1/E2/E3/E4. The operator
reviews the coverage doc before Stage 2 (pattern minting) begins.
