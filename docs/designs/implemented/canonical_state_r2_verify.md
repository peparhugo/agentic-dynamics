---
status: implemented
implemented_by: feature/canonical-state-r2-fable5
---
# Canonical-State Round 2 — Verification

Verify phase of `experiments/specs/canonical_state_round2.yaml`. Checks
`docs/canonical_state_round2_design.md` (refine) and `docs/canonical_state_round2_plan.md`
(plan) against the round-2 spec's requirements and against each other before either is pulled.
Method, inherited from round 1's own verify: re-read the actual document text, not memory of
writing it, and where a claim depends on a specific string, cross-reference it by locating the
exact line in both documents rather than asserting from recall. Six of the nine findings below
were caught exactly that way — by placing the design's §5c/§7b/§12 code samples next to the
plan's step numbers and the live source files, not by re-summarizing either document.

Verdicts use **PASS** / **PARTIAL** / **FAIL**, matching round 1's verify convention.

---

## 1. Operator-delta traceability (design mechanism AND plan step, per delta)

| Δ | Delta | Mechanism in `..._design.md` | Step(s) in `..._plan.md` | Verdict |
|---|---|---|---|---|
| 1 | Write-time registration | §8 — four call sites tabulated (`story.py:945`, `run.py:379`, `finalize_reviews.py:64`, `supervise.py:314/343`), each `FINOPS_KB_WRITE`-gated; §12 step 7 sequences this after backfill | Steps 10, 11, 12, 13 — one plan step per call site, each citing the exact current function body before the edit, each labeled `[STEADY-STATE]` | **PASS** |
| 2 | One typed event stream | §1 (3 additive fields, one envelope), §4 (`message_family()` as a pure function, not a new field), explicit invariant statement that `kb-registry-v1` "subscribes to the same stream as the other three, not a new one" | Step 1 (`message_family`, `OBSERVATION_TYPES`/`ACTUATION_TYPES` in `knowledge.py`), Step 7 (`CONSUMER_GROUPS` extended with `kb-registry-v1`, same `STREAM_KEY` implicitly since it's dispatched through the same `kb_worker.py --group` CLI as the other three groups) | **PASS** — see caveat below |
| 3 | Observation vs. actuation | §5 — full schema (5a), who-may-emit today/future (5b), the two-check gate inside `publish_event()` (5c), explicit scope exclusions (5d) | Step 6 (`actuation_ingestion.py` + the zero-call-sites test), Step 7 (the two `publish_event()` guards), Step 14 (standing test that the gate stays inert) | **PASS** — see caveats below |

**Delta 2 caveat (does not change the PASS verdict):** the design's explicit invariant statement
("the fourth group... subscribes to the same stream as the other three, not a new one") is never
restated as an explicit assertion in the plan — Step 7 adds `"kb-registry-v1"` to the
`CONSUMER_GROUPS` tuple but doesn't call out, the way the design does, that this must not become
a per-type stream. Low-severity: the mechanism (`STREAM_KEY` is a single module constant every
group already shares) makes a divergent stream structurally unlikely, not merely undocumented,
but a future implementer following the plan literally would not see the invariant stated where
they're doing the work.

**Delta 3 caveats — two, both found by cross-referencing design against plan (do not change the
PASS verdict, both are traceability/documentation defects, not functional breaks):**

1. **Design §5c's own pseudocode is internally inconsistent with design §1's own schema.**
   §5c's `publish_event()` code reads `message_family(event.source_type)` — but §1's own
   `KnowledgeEvent` field listing (lines 71-96 of the design doc) does **not** include a
   `source_type` field; only `KnowledgeRecord` has one (confirmed live at `knowledge.py:203`,
   and reproduced correctly in the design's own §1 `KnowledgeRecord` block). The plan (Step 7)
   catches this exact gap and resolves it correctly — "`KnowledgeEvent` itself has no
   `source_type` field... Pick (b) [caller passes `source_type` explicitly]" — but the design
   document itself, as written, contains a code sample that would not run against its own
   preceding schema section. A reader of the design alone (without the plan) would hit this
   contradiction.
2. **Plan step ordering inverts design §12's explicit migration ordering for the gate.** Design
   §12 sequences "wire the two Δ3 gates" as its numbered step **8**, explicitly *after* step 7
   ("wire Delta 1's inline call sites"), i.e., gate-wiring is described as happening after
   steady-state is live. The plan document's own intro states it "mirrors the design doc's §12
   Migration plan," but plan Step 7 (the file edit that actually adds the two guard blocks to
   `publish_event()`) is sequenced *before* plan Step 9 (the one-time migration, corresponding to
   design steps 3–6) and *before* plan Steps 10–13 (steady-state, corresponding to design step
   7) — the opposite order from what design §12 describes. This does not weaken the "actuation
   is inert today" invariant (the gate's *presence*, not its position in the build sequence, is
   what keeps it closed, and none of the steady-state call sites in steps 10–13 emit
   actuation-family events regardless of when the gate code lands), but it is a genuine
   inconsistency between what the plan's intro claims ("mirrors §12") and what the plan's own
   step numbers do.

---

## 2. Base-gap traceability (design mechanism AND plan step, per gap)

| Gap | Finding | Mechanism in `..._design.md` | Step(s) in `..._plan.md` | Verdict |
|---|---|---|---|---|
| (a) | Finding 4 — no-session fallback | §7a — concrete branch reading `story_result["sessions"][i]["agentic"]`, `extractor_version` distinguishes the two paths, table of both paths | Step 4 (`ledger_ingestion.py`, `FALLBACK_EXTRACTOR_VERSION` constant, dedicated fallback test with the exact 15-field fixture) | **PASS** |
| (b) | Finding 5 — `meta_*` pollution | §7b — `classify_session()` runs before emission, new `meta_session` source_type | Step 4 (same function, `SOURCE_TYPE_META` constant, `test_classify_session_routes_meta_batch_star_to_meta_session` — a literal regression test for the documented false-match) | **PASS** — see caveat below |
| (c) | Finding 2 — lost ~83 entries | §7c — `git show` recovery, `reason`-as-caveat on `upsert`, `REPLACED_BY` cross-check | §12 step 5 (one-time), Plan Step 9's `"summary-recovery"` `_SOURCES` key | **PARTIAL** — see finding below, this is the most serious issue in this verify pass |
| (d) | OQ4 — Neo4j `SET`-clause completeness | §6 — full Cypher block extending the existing eleven-property `SET`, plus the `SUPERSEDES` edge write | Step 8 (`kb_worker.py`, both the `SET`-clause extension and the new `kb-registry-v1` handler), with a dedicated new test file (`test_kb_worker.py`) since none exists today | **PASS** |

**Gap (b) caveat (does not change the PASS verdict):** design §7b's own `classify_session()` code
sample has a vacuous branch:
```python
if any(p in session_title.lower() for p in EXPERIMENT_SESSION_PATTERNS):
    return "ledger_attempt"
return "ledger_attempt"
```
Both branches return the identical value — the `EXPERIMENT_SESSION_PATTERNS` check has zero
effect on behavior as written; the function's actual fix (the `meta_` prefix check on the line
above) works correctly independent of this dead branch. This is a code-sample clarity defect the
plan inherits by reference ("mirrors design §7b") rather than reproducing the function body, so it
would carry into the real implementation unless caught during Step 4. Recommend tightening before
implementation: either delete the dead branch (the `meta_` check already the only thing this
function needs to decide) or give the `EXPERIMENT_SESSION_PATTERNS` branch a distinct return value
if there was an intended third classification that never got written.

**Gap (c) — the finding that changes this verify's overall grade:**

`reason` (the field gap (c)'s entire fix depends on — the caveat text "recovered from git
history `<sha>`; manifold/semantic labels and cross-matched baselines are known-stale" that a
future session is supposed to see) lives **only** on `KnowledgeEvent` per both round 1's and
round 2's own schema (§1: the `reason` docstring appears under `KnowledgeEvent`, not under
`KnowledgeRecord` — confirmed by re-reading design §1's two dataclass blocks side by side).
`KnowledgeEvent` instances travel over the Redis Stream (`kb:v1:changes`), which round 1's own
inventory phase classified as **TRANSIENT** (`docs/canonical_state_base_inventory.md` row 14:
"Delivery log over #5... TRANSIENT"). Tracing where `reason` could survive past stream
consumption:

- **Not in the Neo4j `SET` clause** — design §6's own gap-(d) fix (the Cypher block immediately
  preceding this finding in the same document) extends the `SET` clause with `valid_from`,
  `observed_at`, `indexed_at`, `supersedes`, `causes` — **`reason` is not among them**, even
  though this is the exact place round 2 is already extending the clause to close a
  field-dropping gap.
- **Not in the `kb-registry-v1` → `registry_index.jsonl` line schema** — plan Step 8's concrete
  JSON dict (`{"knowledge_id":..., "entity_id":..., "source_type":..., "lifecycle_state":...,
  "observed_at":..., "indexed_at":..., "supersedes":..., "causes":...}`) also omits `reason`.
  This is the file `scripts/registry.py show`/`GET /api/registry` actually read (design §10,
  Plan Steps 15–17) — so even the flat-index surfacing path has no field to read `reason` from.
- **Not on `KnowledgeRecord` at all**, so the newly-written artifact files for record types with
  no pre-existing file (design §9's list: `ledger_job`, `ledger_attempt`, `observation`, `flag`,
  `meta_session`, `actuation`) can't carry it as a fallback either.

**Consequence:** once a gap-(c) recovery event is consumed and acknowledged off the stream, the
caveat that is the entire point of the fix — "this entry is known-stale, treat with reduced
confidence" — is gone. A future session running `scripts/registry.py show <recovered-entry-id>`
would see an ordinary `[M]`-evidence, `current`-lifecycle record with no indication it was a
git-history recovery at all, which is arguably a **worse** outcome than round 1's status quo
(where the 83 entries were at least *absent*, a visible gap, rather than *present-but-silently-
miscategorized-as-fresh*). This same gap also undermines round 1's own OQ3 promise, restated
unchanged by design §10: `scripts/registry.py show <id>` is supposed to print "the full supersede
chain oldest → current with each transition's **reason** (if any)" — as specified today, there is
no durable field for that CLI to read a reason from, for *any* record type, not only gap (c)'s.

**This is not a new problem round 2 introduced — it's a round-1 gap that round 2's added
concreteness (a literal Cypher block, a literal JSON line schema) makes checkable for the first
time.** Round 1's verify never caught it because round 1's design left the `registry_index.jsonl`
schema and the exact Neo4j `SET` clause abstract ("compacts that file's latest-per-entity rows");
round 2's plan is concrete enough to check against, and the check fails. Recommend, before merge:
add `reason` to both the `kb-neo4j-v1` `SET` clause (§6's Cypher block, alongside the four fields
already being added there) and the `kb-registry-v1` handler's JSONL line schema (plan Step 8) —
a one-line addition to each, but a load-bearing one for gap (c) specifically.

---

## 3. Backward compatibility

Design §11 restates round 1's checklist and re-verifies each item against round 2's own
additions (`causes` trailing-default, placed after round 1's `reason`/`supersedes` — confirmed
correct ordering in both the design's §1 code block and plan Step 1's anchor point,
"`knowledge.py:227`" for the pre-round-1 baseline). No existing story/review/result JSON is
rewritten in any step of the plan; every new field is defaulted; the manifest's `files{}` block
is explicitly untouched by plan Step 15.

**Verdict: PASS.** No counter-example found in either document.

---

## 4. Supervisor stays observe-only (flag-only rail as today's default)

Design §10 states the rail is unchanged; §5c's gate plus §5d's scope exclusions (no call site,
no arming UI, no `CAUSED_BY` edge) back this with a concrete mechanism, not just a restated
promise. Plan-side: Step 6 builds `actuation_ingestion.py` with an explicit zero-call-sites test;
Step 13 (the one steady-state step touching the live supervisor loop) only adds
`observation`/`flag` emission — both `OBSERVATION_TYPES`, confirmed against §4's classification
table; Step 14 adds a standing test (`test_finops_actuation_armed_is_unset_by_default`) that
would fail if a future config change silently armed actuation.

**Verdict: PASS.** The delta-3 ordering caveat noted in §1 above (gate code lands at plan Step 7,
before steady-state) does not weaken this: the rail's default state is determined by
`FINOPS_ACTUATION_ARMED` being unset and by zero call sites existing, both of which hold
independent of when the gate's guard code was written relative to the steady-state call sites.

---

## 5. Actuation is POLICY-gated and not authorized to fire

Traced concretely: `authority = Authority.POLICY` (design §2 table row, §5a), the two independent
closed-by-default checks inside `publish_event()` (design §5c, plan Step 7), the `causes`
lineage requirement enforced both at construction (`derive_actuation_record`, plan Step 6 test)
and at transport (`publish_event`'s lineage gate, plan Step 7), and the explicit "who may emit
today: nobody" statement (design §5b) backed by plan Step 6's
`test_no_call_sites_construct_actuation_records`.

One cross-reference defect found, does not change the verdict: plan Step 6's own test
description — "`test_derive_actuation_record_requires_causes`... construction-time check, ahead
of the transport-level gate in **step 8**" — cites the wrong step. The transport-level `causes`
gate is implemented in **Step 7** (`knowledge_stream.py`'s `publish_event()`), not Step 8
(`kb_worker.py`'s consumer handler and Neo4j `SET`-clause fix, which is about gap (d) and has
nothing to do with the actuation gate). A minor, easily-fixed citation error, but worth
correcting before the plan is used as an execution checklist, since a reader following Step 6's
text would look for the causes-resolution check in the wrong file.

**Verdict: PASS**, with the citation fix above recommended before merge.

---

## Summary

| Check | Verdict |
|---|---|
| Δ1 — write-time registration | PASS |
| Δ2 — one typed event stream | PASS (undocumented-but-structurally-sound stream-uniqueness assertion in plan) |
| Δ3 — observation vs. actuation | PASS (two traceability defects: design's own §1/§5c self-inconsistency; plan-vs-design step-ordering inversion — neither breaks the "inert today" invariant) |
| Gap (a) — Finding 4 no-session fallback | PASS |
| Gap (b) — Finding 5 meta_* pollution | PASS (vacuous conditional in the design's own code sample — cosmetic) |
| Gap (c) — Finding 2 lost-83 remediation | **PARTIAL — `reason` is not persisted anywhere durable; the recovered entries' caveat does not survive past the transient stream** |
| Gap (d) — OQ4 Neo4j `SET`-clause | PASS |
| Backward compatibility | PASS |
| Flag-only rail as today's default | PASS |
| Actuation POLICY-gated, not authorized to fire | PASS (one wrong step-number citation in the plan) |

**Overall: not clean — one finding (gap c) is serious enough to block merge as written**, because
it is load-bearing for the one requirement it exists to satisfy (a future session must be able to
see *why* a recovered record is caveated, not just that it exists) and the fix is well-understood
and small. Everything else — both operator deltas 1/2, the core Δ3 gate mechanism, gaps a/b/d,
backward compatibility, and the flag-only-rail/actuation-POLICY-gate invariants the round-2 spec
most cares about — holds up under a skeptical, cross-referenced re-read.

### Before this design + plan is pulled, recommend closing:

1. **Gap (c)'s `reason` durability (the one blocking issue).** Add `reason` to the Neo4j
   `SET`-clause extension (design §6's Cypher block, plan Step 8) and to the `kb-registry-v1`
   handler's JSONL line schema (plan Step 8's JSON dict) — both already being edited in the same
   step for the other four fields (`valid_from`/`observed_at`/`indexed_at`/`supersedes`/
   `causes`), so this is a same-step, one-line addition to each, not a new step.
2. **Migration pass 2 (design §12 step 4, finding 3 — un-folded single-task results) has no
   entry in plan Step 9's `_SOURCES` dict.** Only the steady-state wiring for *future* `run.py`
   writes exists (Step 11); the 2026-08-17 results already on disk have no one-time backfill
   path as the plan is currently written. Add a `"single-task-backfill"` (or similarly named)
   key to Step 9's `_SOURCES` dict before this ships, or this design regresses round 1's
   already-passing coverage of finding 3.
3. **Plan Step 6's cross-reference** ("transport-level gate in step 8") should read "step 7."
4. **Design §5c vs. §1 self-consistency** — either add `source_type` to the design's own
   `KnowledgeEvent` listing in §1 (and then reconcile that against Delta 2's "three additive
   fields total" framing) or rewrite §5c's pseudocode to match the plan's already-correct
   resolution (caller passes `source_type` explicitly to `publish_event()`), so the design
   document is internally consistent standing alone, not only correct once read together with
   the plan's fix.
5. **Design §7b's vacuous `EXPERIMENT_SESSION_PATTERNS` branch** — cosmetic, but worth tightening
   before an implementer copies the dead branch verbatim into `ledger_ingestion.py`.
6. **Plan's stated ordering principle vs. its actual step numbers for the Δ3 gate** — either
   move the `publish_event()` guard edit (currently Step 7) later in the step sequence to
   actually match "gate wired after steady-state" (design §12 step 8's ordering), or update the
   plan's intro paragraph to stop claiming it mirrors §12 for this specific piece. Either fix is
   acceptable; leaving the contradiction as-is is not.
