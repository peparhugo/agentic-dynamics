---
status: accepted
---

# CAP Pattern Minting — Sonnet-5 Adversarial Review (a2_review_patterns)

**Reviewer:** claude-sonnet-5, `feature/cap-sonnet-adversary` phase `a2_review_patterns`
**Target:** `feature/cap-pattern_minting` (spec names it `feature/cap-pattern-minting`; same
underscore/dash cosmetic mismatch as the E2/E3 branch — confirmed not a missing branch).
**Target commits:** `eceee4bba` (p1_inventory_labs), `38ba8d49b` (p2_mint_patterns), `0e79c155a`
(p3_writeup), on top of shared base `6cdefa102`.
**Method:** re-derived every headline number independently in the branch's own worktree
(`/tmp/wt_pattern_minting`, checked out at `0e79c155a`) — recomputed the `pattern/v1` reducer's
grouping and Wilson-interval widths from raw `canonical_corpus.load_canonical_tables("finding")`
data without going through the reducer; resolved all 64 evidence refs against
`registry_index.jsonl` directly; re-ran the actual producer (`kb_produce_facts.py --reducer
pattern/v1 --dry-run`) live to test the idempotency claim, rather than trusting the doc's
narrative; diffed the reducer (`pattern.py`) and epistemic map (`facts.py`) against the base
commit to confirm neither was touched by this branch.

## Verdict: **PASS, with one mandatory fix**

The branch exists, has committed all three expected `[workflow]` phases, and its core
"reducer-mints-only" claim is structurally true: `src/agentic_dynamics/control/reducers/pattern.py`
and `src/agentic_dynamics/control/facts.py` (the `EPISTEMIC_MAP`) both have a byte-identical,
zero-diff history across the whole branch — the flash agent could not have hand-written a fact or
added a D7-violating epistemic row even if it had wanted to, because neither file was touched. The
6 minted facts' support/uncertainty numbers are independently reproducible from raw finding data,
every evidence ref resolves current in the registry, and the writeup is unusually honest about
what the reducer's fixed claim shape can and cannot produce (see finding #1 below, which is a
**non**-finding — a known-safe item). The one real problem is that the writeup's own "idempotent
re-derivation" verification claim does not survive the branch's own subsequent commits, and I
reproduced the exact falsifying counter-example.

## Findings (re-verified)

| # | Finding | Severity | Evidence |
|---|---|---|---|
| 1 | **The "idempotent re-derivation ... 0 new records ... emits 0" claim in §2 (and the p2 commit message) does not hold at the branch's own current tip.** Re-running the exact command the doc cites (`python3 scripts/kb_produce_facts.py --reducer pattern/v1 --dry-run`, no `--revision` override — i.e. the default, ambient invocation) at the branch HEAD (`0e79c155a257`) reports **"would emit 6 fact record(s)"**, all tagged `[fact/supersede]` — not 0. Root cause, isolated precisely: `pattern/v1`'s evidence (canonical `finding` rows) carries no per-row `git_sha`, unlike `attempt_facts/v1`/`job_facts/v1` (which read git_sha-stamped workflow-run JSONs and so "prefer" a stable input-carried revision, per `derive_facts`'s own docstring). With no such input-carried value, `pattern/v1` falls back to the CLI's ambient `revision` argument, which defaults to `git_head_sha()` — the CALLER's current HEAD at invocation time. That value is embedded as `validity_window` inside the fact's `value` JSON, which is **not** one of the two keys `fact_fingerprint()` strips before hashing (`_PROVENANCE_KEYS = {"evidence_ids", "inputs_digest"}` — `value` is not in that set). So every commit that lands after a pattern fact is minted changes its content fingerprint — with **zero change to task, perturbation_class, support, uncertainty, or evidence_ids** — and the next default `kb_produce_facts.py --reducer pattern/v1` run will supersede all 6 facts, forever, on every future commit. This is exactly the instability `pattern_v1`'s own docstring calls load-bearing ("the re-derivation stability the design's citability claim depends on"). | **Mandatory fix** (doc claim is stated too broadly; the underlying wiring gap is real but pre-existing-framework-shaped, not a one-line branch bug) | Live reproduction: `kb_produce_facts.py --reducer pattern/v1 --dry-run` at HEAD `0e79c155a257` → "would emit 6 fact record(s)", all `[fact/supersede]`. Isolated the diff to `validity_window` only (re-ran `derive_facts` in-process and printed each candidate's `support`/`total_evidence` — identical to the registered facts; only `validity_window` changed from `eceee4bba9c5…` (the p1 commit, i.e. mint time) to `0e79c155a257` (branch tip, i.e. after p2/p3 landed)). Confirmed the fix path exists but is unstated: pinning `--revision eceee4bba9c5e9ff5fe966296905cbd72785e563` (the exact mint-time commit) reproduces **"would emit 0 fact record(s)"** — true convergence, but only under a non-default invocation the doc never mentions. `_PROVENANCE_KEYS` read directly from `src/agentic_dynamics/control/fact_ingestion.py:96`; `revision = args.revision or git_head_sha()` from `scripts/kb_produce_facts.py`'s `main()`. |
| 2 | The workflow spec's `p2_mint_patterns` phase prompt asked flash to "mint the first 4-6 patterns: task_routing, escalation_premium, cache_economics, grit_recovery, correctness_premium" — five distinct named pattern *types*. What the reducer can actually produce (and what was minted) is 6 facts of **one single claim shape** (`recovers_under_<perturbation_class>`, sliced by `(task, perturbation_class)`) — only the `grit_recovery` family exists; the other four names in the spec's aspiration are not mintable by the current `pattern/v1` reducer at all (it has exactly one input door and one claim function). This is **not a defect in the branch's work** — see known-safe #2 below, it is disclosed thoroughly and honestly (§1.5, §3.3) — but it is worth surfacing explicitly here since a reader skimming only the spec's `question` field, not the delivered doc, would expect five pattern families and get one. | Informational, not a defect | `docs/architecture/current/cap_pattern_minting.md` §1.5, §3.3 vs. `workflows/repository/cap_pattern_minting.yaml`'s `p2_mint_patterns` phase prompt. |

## Known-safe list (attacked, did not falsify)

| # | Attack attempted | Result |
|---|---|---|
| 1 | **Reducer-mints-only is violated somewhere — a hand-written pattern fact smuggled in via the producer wiring** | **Not falsified.** `git diff 6cdefa102 0e79c155a -- src/agentic_dynamics/control/reducers/pattern.py` and `-- src/agentic_dynamics/control/facts.py` are both **empty** — neither file was touched by any of the three phase commits. The only code change is `scripts/kb_produce_facts.py`'s new `_pattern_finding_evidence()` helper (34 lines), which does nothing but assemble `EvidenceItem` tuples from `canonical_corpus.load_canonical_tables("finding")` and hand them to the existing, unmodified `pattern_v1` reducer via the existing `derive_facts()` dispatcher — no fact construction happens outside the reducer. |
| 2 | **D7 is violated — a new `EPISTEMIC_MAP` row was added for patterns** | **Not falsified.** Same empty-diff evidence as #1: `facts.py` (which holds `EPISTEMIC_MAP`) is untouched. All 6 minted facts carry `epistemic_status="derived"` / `authority=DERIVED` / `evidence_class="[C]"` — the pre-existing row, reused verbatim, confirmed by direct inspection of all 6 `experiments/results/kb/<knowledge_id>.json` artifacts. |
| 3 | **Support/uncertainty numbers are fabricated or estimated rather than counted from real records** | **Not falsified.** Independently recomputed the `(task, perturbation_class)` grouping and success counts directly from `canonical_corpus.load_canonical_tables("finding")` (64 rows, all with a real `bool` `test_executed_success` — 0 excluded) without going through the reducer at all: `(process_perturbation_resample, baseline)`→3/2, `(…, process_perturbation)`→12/7, `(task_manager, baseline)`→7/5, `(…, objective_mutation)`→14/11, `(…, process_perturbation)`→14/8, `(…, specification_corruption)`→14/12 — byte-identical to the doc's §1.3/§2 table. Independently recomputed all six 95%-Wilson-interval widths from the same `(successes, total)` pairs using the textbook formula — all six match the doc/JSON to 4 decimal places (0.7308, 0.4872, 0.5588, 0.4002, 0.4603, 0.3593). |
| 4 | **Entity identity is wrong — two different slices collide on the same `fact_entity_id`, or the same slice produces different ids across runs** | **Not falsified.** `compute_fact_entity_id` keys on `(repository_id, scope_type, scope_id, predicate, subject_type, subject_id)` — none of which include time/revision — confirmed by direct code read (`facts.py:919`). All 6 registered `entity_id`s are distinct (verified via `registry_index.jsonl`), and re-deriving the same 6 slices in-process (at any revision) reproduces the identical 6 `entity_id`s every time — only `validity_window`/content fingerprint move with revision (see finding #1), never identity. |
| 5 | **Skipped labs are not honestly recorded — a lab is silently dropped, or its "not mintable" reason is wrong** | **Not falsified.** Independently re-counted the contract-bearing lab corpus by scanning every `experiments/results/*.json` for a `lab_contract` key: exactly **8** files (`lab_cache_economics`, `lab_condition_effects`, `lab_grit`, `lab_quality_frontier`, `lab_story_arc`, `lab_story_review`, `lab_verification_frontier`, `lab_verification_value`) — matching the doc's table exactly, including its own correction of the workflow spec's stale "7" claim. For each of the 7 non-`lab_grit` labs, the doc's stated reason (story/review/analysis-shaped, not `finding`-shaped — `pattern/v1`'s one input door) is verifiable directly from `pattern.py`'s own `consumes=("finding", "review", "analysis")` + its docstring's explicit statement that only `finding` evidence is actually mined. The two quarantined labs (`lab_task_routing`, `lab_correctness_premium`) are absent from the on-disk 8-file count (confirmed) and are independently corroborated as quarantined by `experiments/results/legacy_labs/`'s existence (not re-verified line-by-line here, but consistent with the CLAUDE.md/AGENTS.md-documented quarantine convention). |
| 6 | **`source_experiment` refs are fabricated, or point to non-existent/superseded registry rows** | **Not falsified.** Programmatically decoded all 6 facts' full `evidence_ids` lists (64 refs total, summing exactly to the 64-row finding corpus — 3+12+7+14+14+14) and resolved every one against `registry_index.jsonl` by extracting the trailing `knowledge_id` segment from each `finding:<entity_id>:<knowledge_id>` ref (per `lab_contract.record_id`'s documented format): **all 64/64 resolve to `lifecycle_state="current"`**. `source_experiment` itself is, per the reducer's own code, always the lexicographically smallest of these same real refs — verified for all 6 facts. |
| 7 | **The new integration test is a rubber stamp — it doesn't actually exercise the real producer path, or it's hermetic in a way that would hide the idempotency gap found above** | **Partially not falsified, partially explains finding #1.** `test_pattern_v1_producer_branch` (`tests/test_kb_produce_facts_integration.py`) does run through the real `derive_facts()` entrypoint (not a hand-built `ReducerInput`) and does assert idempotency — but critically, it calls `derive_facts("pattern/v1", REPO, REVISION, NOW)` with the **same fixed `REVISION` constant both times**, which is exactly the narrower (and true) claim: same-revision re-derivation converges. The test is honest about what it checks; it simply doesn't (and wasn't asked to) cover the cross-revision case finding #1 exercises. Ran it directly: 9/9 tests in the file pass. |
| 8 | **Existing tests regressed** | **Not falsified.** `tests/test_context_plane_pattern.py`, `tests/test_kb_produce_facts_integration.py`, `tests/test_dependency_direction.py`, `tests/test_data_flow.py`, `tests/test_script_classification.py` — 44/44 pass at the branch tip. |

## Mandatory fix

Correct the operational framing of §2's "Idempotent re-derivation" bullet in
`docs/architecture/current/cap_pattern_minting.md` (and note the same gap against the p2 commit
message's "idempotent re-derivation converges to 0 would-emit" claim, which is accurate only as a
same-revision/same-instant statement): state explicitly that convergence holds **only when
`kb_produce_facts.py --reducer pattern/v1` is invoked at the SAME `source_revision` the facts were
minted at** (either the same commit, or an explicit `--revision <mint-sha>` pin) — the *default*,
undecorated invocation the doc's own §2 shows will supersede all 6 facts on every commit that lands
afterward, because `pattern/v1`'s `validity_window` has no evidence-carried revision to prefer
(unlike `attempt_facts/v1`/`job_facts/v1`) and falls back to the CLI's ambient current-HEAD
default. This is a real gap worth flagging upstream to whoever owns the fact plane's reducer
framework — `pattern/v1`'s citability promise (a fact's `knowledge_id` staying stable so a decision
can cite it durably) is undermined by this churn-on-every-commit behavior — but fixing the
*wiring* (e.g. deriving `validity_window` from something evidence-stable, or excluding it from
`fact_fingerprint`'s comparison) is a design decision beyond what this review should apply directly
to a reviewed branch; the mandatory fix here is the doc's honesty about what was actually verified.
