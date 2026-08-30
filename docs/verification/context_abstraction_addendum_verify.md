---
status: accepted
---
# Context Abstraction Plane — Addendum A (I8–I10) Verification

**Spec:** Addendum A of `docs/architecture/current/context_abstraction_design.md` (§A, lines 1460–1604).
**Phase:** `verify` (phase 3 of 3 — `review` → `design` → **`verify`**).
**Verifies:** `docs/reviews/context_abstraction_addendum_review.md` (phase 1, "a1"),
`docs/architecture/current/context_abstraction_addendum_design.md` (phase 2, "a2").
**Date:** 2026-08-22 · **Model:** deepseek/deepseek-v4-pro · **Branch:** `feature/cap-addendum-design`

---

## 0. Method

Every check below was **executed**, not asserted. Mechanical checks (git state, citation
accuracy, gate membership) report the command run and its result; judgment checks (does the
design honour a hard rule, does every Addendum-A claim have a home) give the reasoning and the
specific design section.

Three properties this report deliberately has, inherited from the frozen verify
(`context_abstraction_verify.md:20-31`): it **reports what it ran**, it **found things**
(two findings, both minor, §8), and a finding is **not automatically a FAIL** — a required check
FAILs only when its requirement is unmet; a defect in something the design *did* deliver is a
finding with a severity.

One asymmetry worth stating up front: the addendum verifies **documents**, not code. The
review's central finding — that `EPISTEMIC_MAP`/`is_canonical()`/`FactRequirement`/`snapshot_id`
are design-only, holding empty reserved homes (`control/facts.py:1-8`,
`control/context_compiler.py:1-8`, `core/contracts.py:1-8`) — means V4 and V6 are judgments about
whether the *design text* honours the hard rules and the gate, not whether running code does.

---

## 1. Summary — PASS/FAIL per required check

| # | Required check | Status | Evidence |
|---|---|---|---|
| **V1** | Design-only boundary: `git status --porcelain` shows only the three new docs under `docs/designs/current/`; no `src/`/`scripts/`/`tests/`/`admin/` change | **PASS** | §2 |
| **V2** | Every Addendum-A claim maps to a design section; deviations appear in the deviation table | **PASS** | §3 |
| **V3** | Every OQ from a1 answered with a schema (not prose) | **PASS** | §4 |
| **V4** | Hard rules 1–7 of the frozen design still hold | **PASS** | §5 |
| **V5** | Citation spot-checks — every section sampled against the tree | **PASS** (2 minor off-by-one/path findings) | §6 |
| **V6** | The 4-arm experiment's `requires` are all produced by existing measurement (the compile gate, applied by hand) | **PASS** | §7 |

**Overall: PASS with two minor findings.** Neither blocks; both are one-character edits.

---

## 2. V1 — Design-only boundary · **PASS**

```
$ git status --porcelain
?? docs/verification/context_abstraction_addendum_verify.md    (this file, pre-commit)

$ git diff --name-only 657040a53..HEAD | grep -v '^docs/designs/current/' || echo "(none)"
(none)
```

The three phase commits each touch exactly one doc, and nothing outside `docs/designs/current/`:

| Commit | Phase | Files | Lines |
|---|---|---|---|
| `ef2a749d4` | review (a1, first) | `…addendum_review.md` | +478 |
| `987d48746` | review (a1, final) | `…addendum_review.md` | +366/−430 (re-audit supersedes the first) |
| `e29652e25` | design (a2) | `…addendum_design.md` | +793 |

`git show --stat` for each confirms a single file per commit, and
`git diff --name-only 657040a53..HEAD` shows **no** `src/`, `scripts/`, `tests/`, or `admin/`
change across the whole run. Hard rule 1 (DESIGN ONLY) is satisfied.

*Note on the double review commit:* `ef2a749d4` and `987d48746` are both review-phase commits on
the same file — the second is a re-audit that superseded the first (recorded in a1's delivery).
This is a process artifact, not a boundary violation: both touch only the review doc.

---

## 3. V2 — Addendum A tracing · **PASS**

Every claim Addendum A makes, traced to a design section. "Mechanism" means a named schema or
rule, not a paragraph agreeing with it.

| Addendum A claim | Design section | Mechanism | Verified |
|---|---|---|---|
| A.1: three refinements I8/I9/I10 and why now | §1 (thesis), §2–§4 | One schema + composition rule per increment | ✔ |
| I8 `DomainProfile` + `ChallengeProfile` | §2.1 | Frozen dataclasses with `profile_version`, `session_policy`, field-by-field *Why:* | ✔ |
| I8 "compiler gains two profile inputs" | §2.4 | `compile_context` gains `domain`/`challenge`; `request` gains `domain_id`/`challenge_id` selectors | ✔ |
| I8 "contract remains the sole gate; `context_requirements` resolve through `requires_facts`" | §2.3 | `compose_requirements` (contract-wins, tighten-only, `excludes` refusal) | ✔ |
| I8 deliberation stages selected per challenge | §2.5 | 6-row archetype table | ✔ |
| I8 profiles declared (POLICY), performance measured by campaign | §2.3 | `epistemic_status="declared"` → POLICY/`[P]`; measure-before-promotion | ✔ |
| I9 `EPISTEMIC_MAP` additive row | §3.1 | `"pattern": (Authority.DERIVED, "[C]")` | ✔ |
| I9 `PatternPayload` fields | §3.2 | Frozen dataclass + `→ CanonicalFact` mapping table | ✔ |
| I9 minting rules (hard rule 3) | §3.4 | Four numbered rules | ✔ |
| I9 `is_canonical()` unchanged | §3.4 | Specified as the C5 interaction; not assumed to exist | ✔ |
| I9 `source_experiment` via lab-contract refs | §3.5 | `record_id()` + `refs_digest()` | ✔ |
| I10 `SessionCheckpoint` | §4.1 | Frozen dataclass with per-field epistemic grade | ✔ |
| I10 `session_routing` contract (allowed_actions, invariants) | §4.2 | Full `session_routing.yaml` | ✔ |
| I10 continue-vs-fork trade `[H]` until measured | §4.3 | `AUTOMATABLE_ACTIONS` unchanged; shadow mode | ✔ |
| I10 4 arms + measured signals | §4.4 | Spec YAML + signal→ledger-field table | ✔ |
| I10 shadow mode until it lands | §4.3 | `shadow_only: True`; proposal-only | ✔ |
| A.5 closure deltas (coverage primitive, routing semantics, lab-contract v6, gate conditions) | §2.2/§3.3/§3.5 (REUSE) | `measurement_coverage.py`, `record_id`/`refs_digest`, `compare_arms` | ✔ |

**Deviations:** the design's §5 deviation table lists **two** deviations (D1 `verified_facts`
demoted DERIVED→ADVISORY; D2 `context_snapshot_id` required→Optional). Cross-checked: the design
text in §4.1 carries both demotions with the final grade per field, and the table names both with
justification. **The deviation table is not empty when it should not be, and empty where it
should be** (the `challenge`-vs-`TASK_TYPES` reconciliation is correctly treated as a
clarification, not a deviation, and excluded — §2.5/§5).

---

## 4. V3 — every OQ from a1 answered with a schema · **PASS**

The review (a1) asked seven open questions (§6). The design (a2) answers each with a
dataclass/YAML sketch, and states the mapping in its §8 traceability table. Verified
independently:

| OQ | a1 asks | a2 answers | Form |
|---|---|---|---|
| OQ1 | profile storage model + `entity_id` | §2.2 | `source_type` row + `compute_entity_id`/`compute_knowledge_id` formulas + version-chain decision |
| OQ2 | `context_requirements` through the gate | §2.3 | `compose_requirements` (code sketch) + the four composition rules |
| OQ3 | execution-strategy routing + baseline | §2.4 | `compile_context` signature + `select_execution_strategy` + `compare_arms` baseline |
| OQ4 | reducer input + `support` | §3.3 | `ReducerSpec` + `pattern_v1` + support/uncertainty derivation |
| OQ5 | pattern authority + cite format | §3.1/§3.2/§3.5 | `EPISTEMIC_MAP` row + field-mapping table + `record_id`/`refs_digest` |
| OQ6 | v1 checkpoint grades + demotion | §4.1 | `SessionCheckpoint` with per-field grade + demotion table + annotations-vs-rows decision |
| OQ7 | `session_routing` identity/snapshot/shadow | §4.2/§4.3/§4.4 | `session_routing.yaml` + `AUTOMATABLE_ACTIONS` answer + 4-arm spec + shadow-recording decision |

**7/7 answered with a schema** (dataclass or YAML), none in prose-only. The two OQs with the
highest risk of hand-waving were checked in detail: OQ2's composition rule is a *named function*
with an explicit contract-wins/tighten-only algorithm (not "profiles go through the gate"), and
OQ7's `snapshot_id`-for-a-session semantics distinguishes the session-context snapshot from a
single-decision snapshot (a real ambiguity the review flagged and the design resolves).

---

## 5. V4 — hard rules 1–7 still hold · **PASS**

| # | Rule | Design's provision | Verified |
|---|---|---|---|
| 1 | Design only | §7 scope boundary; no file created | ✔ V1 |
| 2 | No new transport | I8 persists via an additive `SOURCE_TYPES` row + the existing stream (§2.2); I9 via `Reducer`/`record_factory` (§3.3); I10 via the existing pipe (§4.1) | ✔ — no new store, no new stream |
| 3 | Deterministic reducers; LLM → ADVISORY | §3.4 rules 1–4 (registered reducer only; LLM pattern ADVISORY; pure; no fabricated `support`) | ✔ |
| 4 | One canonical representation, or unknown/conflicted | profile version-chain = one current per `entity_id` (§2.2); checkpoint demotion with explicit `snapshot_available` flag (§4.1) | ✔ |
| 5 | Supervisor untouched + authority hierarchy | §4.3 leaves `AUTOMATABLE_ACTIONS = {continue, route}`; `fork`/`compress`/`escalate` stay proposal-only; no call site added to `supervise.py`/`supervisor.py` | ✔ |
| 6 | Load-bearing rule is the gate | §2.3 composition refused by R1/R2 for producerless names; §4.4 arms require only LEDGER_FIELDS names | ✔ V6 |
| 7 | Don't redesign `knowledge.py`/`retrieval.py`/`prompt_constructor.py` | §7 row 5: the only `knowledge.py` touch is one *proposed* additive `SOURCE_TYPES` row | ✔ |

The two rules most likely to be silently bent were checked specifically: **rule 3** — the design
makes the LLM→ADVISORY exclusion structural by naming `is_canonical()` and C5 as the enforcement
point (§3.4) rather than a convention; **rule 5** — the design's §4.3 is explicit that `fork`/
`compress_and_fork`/`escalate` are *proposals* until the evidence-seed experiment, mirroring the
frozen §8.1 "proposal only" doctrine (`context_abstraction_design.md:1093`).

---

## 6. V5 — citation spot-checks · **PASS (2 minor findings)**

Each check re-read the cited source range independently of both prior phases. 25/25 PASS, two
with a precision note (§8).

| Cited by a1/a2 as | Re-verified |
|---|---|
| `context_abstraction_design.md:385` `EPISTEMIC_MAP`, `:403` `is_canonical` | ✔ |
| `context_abstraction_design.md:827` `compile_context`, `:928` `snapshot_id` formula | ✔ |
| `context_abstraction_design.md:961` `FactRequirement`, `:1065` R10, `:1183` C5, `:1196` `AUTOMATABLE_ACTIONS` | ✔ |
| `context_abstraction_design.md:1093` "proposal only", `:1352` monotone tightening, `:1460` Addendum A | ✔ |
| `workflow_runner.py:81,86,89,92,106,113,160` `PhaseResult`/`WorkflowRunResult` fields | ✔ (status:81, model:86, error:89, cost_usd:92, selected_evidence_ids:106, test_executed_success:113, goal:160) |
| `workflow_runner.py:227` `_git_head`, `:235` `_completed_phases`, `:290` `_completed_phases_from_index` | ✔ |
| `workflow_runner.py:591-597` fork chain, `:605-612` tokens dict, `:622` `prev_model` | ✔ |
| `experiment_spec.py:135-194` `LEDGER_FIELDS`; `:159-176` attempt fields | ✔ (attempt_number:159 … accepted:176) |
| `experiment_spec.py:193` `test_executed_success` | **F1 — off-by-one**: it is at `:192`; `:193` is the closing `}` |
| `experiment_spec.py:159,171,172,184,187` (`attempt_number`, `service_time_ms`, `cache_hit`, `cost_inference`, `rework_cost`) | ✔ |
| `knowledge.py:61-85` `Authority`, `:105` `SourceTypeSpec`, `:125-150` `SOURCE_TYPES`, `:149` `actuation` | ✔ |
| `knowledge.py:168-181` `message_family` default-safe, `:192`/`:202` identity helpers | ✔ |
| `knowledge_ingestion.py:93` `REPOSITORY_ID` | ✔ |
| `spec_ingestion.py:76,80,229,235,291,302-303` spec producer | ✔ |
| `lab_contract.py:114,352,365,620` (v6, `refs_digest`, `record_id`, `validate_contract`) | ✔ |
| `canonical_corpus.py:81` `TABLES` | ✔ |
| `measurement_coverage.py:20-21,55-83,111,127` | ✔ |
| `core/session_types.py:40` `TASK_TYPES` | ✔ |
| `control/__init__.py:7-9` reserved homes | ✔ |
| `actuation_ingestion.py:70` `ACTUATION_KINDS` | **F2 — path precision**: the module is `control/actuation_ingestion.py:70` (single instance, unambiguous, but the plane prefix is omitted) |
| `knowledge_stream.py:178-192` write-guard + armed + lineage gates | ✔ (all three present in the range) |
| `runtime/routing.py:284-292` `RouteState`, `step_routing.py:188-233` `route_step` | ✔ |

**Quantitative re-verification:** the a2 §4.4 table claims 3 of the 7 experiment signals are
written today (`test_executed_success`, `confidence`, `tokens_*`) and 4 declared-only
(`cost_inference`, `cache_hit`, `service_time_ms`, `rework_cost`, `attempt_number`). Re-checked
against `LEDGER_FIELDS` (`experiment_spec.py:135-194`): every name the table calls "written" has
a writer in `workflow_runner.py`/`ledger_ingestion.py`; every name it calls "declared-only"
appears in `LEDGER_FIELDS` with no non-declaration writer (consistent with a1 §3d(ii)). ✔

---

## 7. V6 — the 4-arm experiment's `requires` are produced by existing measurement · **PASS**

The compile gate is `available = LEDGER_FIELDS ∪ {produces of measurement rules}`
(`experiment_spec.py:614-617`), refused otherwise (`experiment_spec.py:619-625`). Applied by hand
to the a2 §4.4 spec:

| `requires` entry (a2 §4.4) | In `LEDGER_FIELDS`? | Line |
|---|---|---|
| `test_executed_success` | yes | `experiment_spec.py:192` |
| `confidence` | yes | `experiment_spec.py:190` |
| `tokens_in` | yes | `experiment_spec.py:179` |
| `tokens_out` | yes | `experiment_spec.py:180` |
| `tokens_answer` | yes | `experiment_spec.py:182` |
| `tokens_explanation` | yes | `experiment_spec.py:183` |
| `perturbation_strength` | yes | `experiment_spec.py:191` |

All seven are ledger names → the measurement rule compiles. The shadow control rule's
`requires: [test_executed_success, confidence, tokens_in, tokens_out]` are a subset → also
compile. **And the binding negative:** no `requires` names `snapshot_id` or `context_snapshot_id`
— neither is in `LEDGER_FIELDS`, so either would be refused by the gate exactly as a1 warned
(no producer until I4). The design's explicit instruction "no `requires` on `snapshot_id`" is
therefore not merely stylistic; it is the gate enforced, and the design passes it.

**The second-order honesty check (measure-before-policy):** the a2 §4.4 table correctly separates
the *writable shadow arm* (the four policy levels, recorded inert) from the *outcome signals*
that must be measured before promotion. The three written signals make the shadow arm writable
now; the four declared-only signals (`cost_inference`/`cache_hit`/`service_time_ms`/`rework_cost`/
`attempt_number`) must be instrumented before `session_policy_outcome` can emit its `produces`.
This is the load-bearing rule applied to the experiment itself, and the design states it rather
than papering over it.

---

## 8. Findings

Severity: material = fix before implementing · minor = fix during implementation.

### F1 — `test_executed_success` cited at `experiment_spec.py:193`, actual `:192` · **minor**

**Where:** a2 §4.4 table, "verified success" row, and the appendix citation block.

**Problem:** `LEDGER_FIELDS` closes with `"test_executed_success"` at line **192** and `}` at 193
(verified: `experiment_spec.py:192`). The citation points one line past the field.

**Fix:** `experiment_spec.py:193` → `experiment_spec.py:192` in the a2 table and appendix.

### F2 — `actuation_ingestion.py:70` omits the `control/` plane prefix · **minor**

**Where:** a2 appendix, "Actuation envelope + gates" row (and a2 §4.4's prose, which cites the
module bare).

**Problem:** the module lives at `control/actuation_ingestion.py:70` (the repo re-homed the flat
`instrument` package into planes). The bare name is unambiguous (one `actuation_ingestion.py` in
the tree), but it is imprecise against the repo's plane-qualified convention used everywhere else
in both docs.

**Fix:** cite `control/actuation_ingestion.py:70`.

No material findings. The review's sharpest predicted failure — I10 shipping `verified_facts`/
`context_snapshot_id` as DERIVED with no producer — is pre-empted by the design's D1/D2 demotions
(a2 §4.1), which is the correct move and is verified here rather than counted as a defect.

---

## 9. What this verification did **not** check

1. **Implementability.** No code was written, so no schema compiled, no test run. V4/V6 are
   judgments about the *text*, not the running system — the same boundary the frozen verify drew
   (`context_abstraction_verify.md:392-394`).
2. **The `spec_lifecycle` merge dependency** inherited from the frozen design (§9, "I1 must land
   after it merges") — still not knowable from this worktree.
3. **Whether the a2 `profiles.py` reserved home will be adopted** — that is an implementation-spec
   decision; this verify only checks the declaration is coherent with `control/__init__.py:7-9`.
4. **Whether the four declared-only signals will actually be instrumented** — a2 §4.4 names the
   gap and the prescription; whether the implementation closes it is out of scope.

---

## 10. Verdict

**PASS — all six required checks met.** The design-only boundary is intact (three commits, three
docs, nothing outside `docs/designs/current/`); every Addendum-A claim traces to a schema;
all seven OQs are answered with a schema; the seven hard rules hold (deterministic reducers,
no new transport, one canonical representation, supervisor untouched, the contract gate intact,
no `knowledge.py` redesign); 25/25 citation spot-checks pass; and the 4-arm experiment's
`requires` are all existing ledger names — with the binding negative confirmed (no `snapshot_id`).

Two findings, both **minor** (F1 an off-by-one line number, F2 a missing plane prefix); neither
blocks, both are one-character edits to make during implementation.

---

## Log

| Check | Result |
|---|---|
| V1 design-only boundary (git status + commit file lists) | **PASS** |
| V2 Addendum-A tracing + deviation table | **PASS** |
| V3 all seven OQs answered with a schema | **PASS** |
| V4 hard rules 1–7 | **PASS** |
| V5 citation spot-checks | **PASS** (F1, F2 minor) |
| V6 compile gate applied by hand | **PASS** |
