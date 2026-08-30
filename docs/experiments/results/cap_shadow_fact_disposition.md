---
status: accepted
---
# CAP Shadow-Fact Disposition — merge, marker, fact-flow verification, adversarial review

**Spec:** `workflows/repository/cap_shadow_fact_disposition.yaml`
**Branch:** `feature/cap-shadow-fact-disposition`
**Date:** 2026-08-24 · **Model:** deepseek/deepseek-v4-flash (single-model, `--backend opencode`)
**Question:** Land the two reviewed CAP workstreams (`feature/cap-shadow_campaign`,
`feature/cap-fact_auto_emit`) and close their two known anti-pattern edges — shadow decisions
structurally marked as proposed-not-executed, and end-to-end fact flow proven with
`FINOPS_KB_WRITE=1` — with an adversarial review before release.

---

## 1. Merge summary (p1) — PASS

Two merges, one at a time, into `feature/cap-shadow-fact-disposition`, both clean under the
`ort` strategy. **No conflicts.** No content was dropped from either branch (union check: every
file from both branches' `git diff --name-only` ranges is present on the branch).

| # | Branch merged | Commits brought in | Merge commit |
|---|---|---|---|
| 1 | `feature/cap-shadow_campaign` | `32d757e7f` s1_select_and_run · `90e0e0798` s2_reports_and_validation · `a6cc04a49` s3_measurement_doc · `7e97e526d` s4_adversarial_falsification | `898cde022` |
| 2 | `feature/cap-fact_auto_emit` | `814c94591` f1_hook_design · `5f589de78` f2_implement · `2bdba509d` f3_adversarial_verify | `06cfbdd38` |

**Files changed by the merges: 34** (29 from shadow-campaign + 5 from fact-auto-emit):
`docs/experiments/results/cap_shadow_measurement.md`,
`docs/architecture/current/cap_fact_auto_emit_design.md`, `scripts/kb_produce_facts.py`,
`scripts/run_workflow.py`, `tests/test_fact_auto_emit.py`,
`tests/test_fact_auto_emit_adversarial.py`, the I6 shadow reports
(`experiments/results/cap_shadow/*.json`), 23 content-addressed KB artifacts, the registry
index, and the spec lifecycle index (`experiments/specs/index.json` + `STATUS.md`).

**GUARD — in-flight branches never touched:** the three in-flight branches
(`feature/cap-addendum_implement`, `feature/cap-gate-migration`,
`feature/cap-routing-evidence-specs`) appear **nowhere** in the first-parent history of this
branch's merges, nor as parents of either merge commit. (One *older* pre-existing merge of
`feature/cap-addendum-design` — a distinct, already-merged branch — exists in history before
the CAP workstreams; it is not one of the three in-flight branches and was not touched by this
task.)

**One fix required by the guards:** `cap_shadow_measurement.md` (from the shadow-campaign
branch) lacked the `status: accepted` front matter the doc-lifecycle guard demands for
`docs/designs/current/`. Additive front-matter fix; branch content preserved.

**Test suite after merge — PASS:** 238 (control plane + fact auto-emit + shadow + actuation +
workflow) + 25 (guards: dependency-direction, data-flow, doc-lifecycle, script-classification,
workflow-classification). Final sweep after p4: **264 passed, 0 failed.**

## 2. Marker change (p2) — PASS

**Problem:** shadow decisions were recorded as `source_type="actuation"` artifacts whose only
discriminator from a real actuation was *positional* — artifact-dir-only, never published to the
live stream. The record body itself carried no structural "proposed, never executed" marker.

**Fix (`src/agentic_dynamics/control/rules.py`, `record_shadow_decision`):** the single choke
point through which *both* shadow-producers flow (`make_shadow_router` at `rules.py:344` and
`make_applying_router` at `rules.py:495`) now stamps `applied: False` into the decision's
`parameters` when the caller did not already stamp it. Because `parameters` ride in the record
body's `requested_action`, the marker is structural content — it survives the
`record_to_artifact` round-trip and distinguishes a proposed-not-executed decision by field, not
by location.

- **Additive only:** the applying seam (`make_applying_router`) stamps `applied: True` itself and
  is never overridden (`if "applied" not in decision.parameters`). `derive_actuation_record` and
  the report scripts are unchanged.
- **Report round-trip intact:** `load_shadow_decisions` already read `parameters.get("applied",
  False)`; the three I6 report scripts (`context_snapshot_report`, `shadow_decision_report`,
  `decision_arm_comparison`) and `compile_experiment.decision_calibration` all ran clean over the
  real 11-row shadow corpus after the change.
- **Regression test:** `test_shadow_decision_carries_applied_false_marker`
  (`tests/test_context_plane_seam.py`) — a shadow decision (no caller-stamped `applied`) records
  with `applied: false` in the body and `load_shadow_decisions` surfaces it as a non-applied row.
  The existing `applied: True` path test still passes.

**Accepted limitation (adversarial finding 2-1):** the 11 shadow artifacts already on disk
predate the fix and physically lack the `applied` key. They are not a current code path — the
reader defaults them to `False` — so no backfill was done (out of the minimal-additive guard).
Documented here for the record.

## 3. Fact-flow verification (p3) — PASS (evidence table)

One tiny workflow sub-run, exactly as required: the smallest spec in the index (`code_review`,
2 doc-writing phases) via `scripts/run_workflow.py` in a temp worktree
(`/tmp/wt_flow_verify`), `FINOPS_KB_WRITE=1`, auto-emit default-ON.

| Run id | Spec | Model | Cost | Result | Facts emitted |
|---|---|---|---|---|---|
| `20260824T003155Z` | `code_review` | `deepseek/deepseek-v4-flash` | $0.0342 | ok=True | `emitted=27 skipped=0 total=27` |

**Facts landed in the KB artifact dir + registry (not just derive):**

| Evidence | Count | Detail |
|---|---|---|
| KB artifact files | **27 / 27** on disk | `experiments/results/kb/<knowledge_id>.json`, content-addressed (sha256 filename), readable, `repository_id=self-wf_cap_shadow_fact_disposition_deepseek_deepseek_v4_flash` |
| Registry rows | **27** | `experiments/results/registry_index.jsonl`, `source_type=fact`, `lifecycle_state=current`, unique `knowledge_id`s (all 27 distinct `entity_id`s, none superseded). Job/workflow/policy facts carry run identity `wf_code_review_deepseek_deepseek_v4_flash`; attempt facts are per-phase — 8 rows for `code_review` phase, 8 for `architecture_review` phase (the run has 2 phases) |
| Fact predicates | 19 | attempt (cache_hit_rate, confidence, cost_usd, model, tokens_in/out) · job (accumulated_cost_usd, n_phases, status) · policy (max_attempts, max_spend_usd) · workflow (health, phases_completed/remaining, status, projected_budget_overrun, current_commit, phase_commit, phase_status) |

Flow: `_emit_workflow_facts` → `kb_produce_facts.derive_run_facts` (attempt/job/policy/workflow
reducers) → `emit_records` (writes artifact, publishes pointer event to `kb:v1:changes` on
Redis 6380/db2, checkpoints) → `kb_worker.py --group kb-registry-v1 --once` (verify content hash
→ extract → append registry row). Both layers confirmed.

**Idempotency — RE-DERIVED, not asserted:** re-deriving `derive_run_facts` over the *same* run
artifact with the correct scope returns **0 records** (the derive-level convergence guard
fingerprint-matches every entity's registered head), so re-emit is a byte-identical no-op —
verified: stream `xlen` and registry line count unchanged before/after (693→693, 830→830).
Contrast covered by the existing suite (`test_reemit_same_run_is_a_byte_identical_noop`,
`test_a_genuinely_new_run_of_the_same_cell_supersedes_the_old_one`).

**Ops requirement (the hard part, adversarial finding 3-1 — verified empirically, nuance
recorded):**

- The **auto-emit hook self-arms** `FINOPS_KB_WRITE` internally via
  `_authorized_kb_write()` (design §5) for the duration of its emit. A probe with
  `env -u FINOPS_KB_WRITE` still emitted all 27 facts from a completed run — so a *completed
  run's* facts flow regardless of the ambient flag.
- The **raw transport** (`knowledge_stream.publish_event`) refuses without `FINOPS_KB_WRITE=1`
  (raises `RuntimeError`) — every *other* producer (`kb_produce*.py`, batch jobs, any future
  writer) requires it. Facts derive but never reach the stream unless the write is authorized at
  that layer.

**Operationally:** set `FINOPS_KB_WRITE=1` for the environment/process that runs `run_workflow.py`
if you want the fact plane to be robust to *any* writer, and rely on the hook's internal arming
for the run-completion path itself. Facts do NOT flow through the raw transport without it.

**Probe hygiene:** two exploratory probes (a wrong-scope `self-wt_flow_verify` derivation and the
`env -u` check) transiently emitted duplicate events into the shared stream; all 54 probe events,
their checkpoint entries, and their artifact files were removed, restoring the stream to the
real run's exact state (666 events, 589 checkpoints, 27 run artifacts + 1 spec record). The
registry only ever received the real run's 27 fact rows + 1 spec record.

## 4. Adversarial review (p4) — 4 findings, 0 release-blocking

| # | Attack vector | Result |
|---|---|---|
| 4-1 | Merge: in-flight branch touched? content dropped? | **Clean.** No in-flight branch in any merge parent or first-parent history. Union check: no file from either branch dropped. The only conflict-shaped issue (missing doc front matter) was an additive guard fix. |
| 4-2 | Marker: any path producing a shadow record WITHOUT the marker? report scripts break? round-trip survives? | **Clean.** Both `record_shadow_decision` call sites flow through the single stamped choke point (the only production `derive_actuation_record` caller is `record_shadow_decision` itself, `rules.py:265` — confirmed by the data-flow guard); `load_shadow_decisions`/`decision_calibration`/the 3 report scripts read correctly; the regression test reads the artifact back off disk (round-trip proven). One accepted limitation: 11 pre-existing on-disk shadow artifacts predate the marker (reader-safe default). |
| 4-3 | Fact-flow: did facts reach the *registry* (not just artifact dir)? idempotency re-derived? | **Clean.** 27 registry rows (content-addressed, `lifecycle_state=current`, all distinct `entity_id`s, none superseded), 27/27 artifacts, idempotency re-derived to 0 records on re-derive. |
| 4-4 | Docs: is `FINOPS_KB_WRITE=1` stated as a hard ops requirement? | **Fixed in this document** (§3): yes, with the verified nuance that the hook self-arms while the raw transport refuses. |
| 4-5 | Docs precision: are the run's fact rows characterized correctly? | **Fixed in re-review** (§3, registry row): the 27 rows span TWO phases — 8 attempt facts per phase (`code_review`, `architecture_review`). The original "per-run identity `wf_code_review_deepseek_deepseek_v4_flash`" phrasing was accurate only for the job/workflow-level rows; tightened to name the per-phase attempt identity explicitly. |

## 5. Release verdict — PASS, merge-ready

`feature/cap-shadow-fact-disposition` is **merge-ready to main.** Merge summary clean, marker
landed and tested, fact flow proven end-to-end, adversarial review clean (3 findings, 0
release-blocking; 1 doc fix landed as §3's ops requirement).

**What the operator must do after merge:**

1. Set `FINOPS_KB_WRITE=1` in the deployment environment (robust fact plane for any writer; the
   auto-emit hook self-arms for run-completion, but the raw transport and every batch producer
   require it).
2. Re-run the shadow campaign (`--cap-shadow` on a real workflow, or
   `workflows/repository/cap_shadow_campaign.yaml`) for the real I7 gate test — the shadow
   comparison data needed to flip the `control_route` opt-in still does not exist (§9 I7's own
   gate). The 11 pre-existing shadow artifacts can optionally be re-recorded to carry the
   physical `applied: false` marker.
3. No commit spec sets `workflow.params.control_route`; keep it that way until the shadow
   comparison shows non-inferior loss.

**PASS/FAIL log:**

| Phase | Result |
|---|---|
| p1 merge_branches | PASS (2 clean merges, guards green after front-matter fix) |
| p2 applied_false_marker | PASS (marker + regression test, report scripts intact) |
| p3 fact_flow_verification | PASS (27 facts landed, idempotency re-derived, ops requirement documented) |
| p4 adversarial_review | PASS (3 findings, 0 blocking; release verdict issued) |
