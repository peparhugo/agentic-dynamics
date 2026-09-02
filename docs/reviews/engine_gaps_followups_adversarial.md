---
status: accepted
kind: adversarial-review
spec: engine_gaps_followups
phase: g2_adversarial
run: run-2d9c9c53be34
reviewer: deepseek/deepseek-v4-pro (independent — different model + session from the flash author)
generated_at: 2026-09-02T20:32:04Z
---

# Adversarial review — `engine_gaps_followups` (g2_adversarial)

**Role.** This is the INDEPENDENT adversarial pass over the Wave-1 followup wave. I am a
different model and session from the flash author. I falsify, I do not certify. Every claim
below was re-derived against the actual code at the wave tip (`040ac562e`) and the live
control db, never asserted from the preregistration or the author's commit prose. Where a
live state was probed, the command that produced it is recorded.

**Method.** The four attack axes of the phase mandate, in order, each re-verified with a
command or a live probe rather than a doc read:

1. **g1_split_run_evidence** — does the `engine_gaps_verifier_revision` live shape now read
   NOT-completed? does an unlinked second run stay a separate family?
2. **g1_verifier_mount** — can the verifier write its candidate through ANY mount (probe the
   request)?
3. **g1_revision_invalidation** — does a mid-list rename invalidate? does the partial-run
   corpus still false-positive (the f4 shape)?
4. **g1_parity_roundtrip** — is the envelope-classify contract actually exercised against the
   real executor (not a fake)?

Every finding is **FIX** on the branch or **RECORD** (accepted limitation with reasoning).
This review records **five findings** (A1-A5): four conservative-direction limitations and one
cross-cutting stale-derived-surface finding. None fabricates a false `completed`, none re-opens
an F1-F4 defect, none permits the verifier to write its candidate. Otherwise a clean sweep with
re-verification evidence. Never a bare PASS.

---

## 1. Attack g1_split_run_evidence — the family UNION, never the latest run alone

### 1a. Does the live `engine_gaps_verifier_revision` shape now read NOT-completed? — **YES**

The live control db + the two live ledgers are unchanged from the pin (schema `3`, epoch `51`;
`run-85f33d68de3b` failed with `w1_pin_spec`+`w1_verifier_executor`+`w2_revision_identity`,
`run-45c2c18f97c8` promotable with `w3_adversarial`+`w4_test_gate` — two UNLINKED ledgers, no
`run_id`/`family_id` keys on either). Re-derive the index with the current code (worktree `src`
via `_bootstrap`, never the editable install):

```bash
PYTHONPATH=/tmp/wt_followups2/src python3 scripts/spec_status.py \
    --spec engine_gaps_verifier_revision --json
# engine_gaps_verifier_revision: status=failed  n_runs=2  latest_ok=True
```

`latest_ok=True` while `status=failed` is the whole point of F5: the latest (promotable, `ok`)
run no longer certifies completion, because it is an unlinked family whose union `{w3,w4}` does
not cover the 5-phase revision, and the older failed family is decisive. The split-run lie is
closed for the live shape. I also re-derived the shape with in-process `RunSummary` probes
(§1c) to confirm the mechanism, not just the committed artifact.

### 1b. Does an unlinked second run stay a separate family? — **YES**

`_certifying_families` (`spec_status.py:495-524`) keys each run by `run.family_id` and falls
back to a per-index sentinel `\x00self:{i}` when `family_id` is empty, so two unlinked runs
NEVER merge. Probed directly against the current code:

```
unlinked partial (parent failed w1+w2, child ok w3+w4)  -> failed
unlinked fresh full-coverage run AFTER a failed family  -> completed
```

The second line is the unlinked-second-run invariant the blunt any-failed-member guard could
not see: a genuinely new attempt (its own `family_id`) that executes the whole revision certifies
`completed` even though an earlier, separate family failed. `_newest_decisive_family_status`
(`spec_status.py:563-586`) scans families newest-first and returns the newest DECISIVE verdict.

### 1c. The linked (resume) shapes — **PASS with one gap (A4)**

Both directions of the synthetic family were probed against `derive_status`:

| Shape | `derive_status` | expected |
|---|---|---|
| linked parent(w1+w2 **failed**) + child(w3+w4 ok) | `failed` | failed (any failed member → never completed) |
| linked parent(w1+w2 ok) + child(w2+w3+w4 ok), union covers | `completed` | completed |
| legacy parent (`family_id=""`) + post-g1 child (`family_id=parent.run_id`) | **`blocked`** | should be `completed` (clean split across the legacy boundary) |

The third row is finding **A4**: the FIRST `--resume` of a pre-g1 (legacy) failed/timed-out run
does not union. `create_run` (`control_db.py:1530-1538`) resolves the child's family to
`parent.family_id or parent.run_id` but never backfills the legacy parent's own empty
`family_id`; `_certifying_families` groups by `family_id` equality ONLY and ignores
`parent_run_id` entirely. So the child points at the parent, the parent does not point at
itself, and the union never forms. This is conservative (it under-certifies — it can never
fabricate a false `completed`), and the `engine_gaps_verifier_revision` live shape is
unaffected (its parent is already `failed`, which is the correct verdict). See the table in §5.

### 1d. Cross-cutting: the family-union derivation re-derives the WHOLE index — **RECORD (A5)**

The `derive_status` change is not scoped to split-run specs; it re-derives every non-repeatable
workflow in the corpus. Regenerating the derived index with the g1 code
(`PYTHONPATH=/tmp/wt_followups2/src python3 scripts/spec_status.py`) shifts **17 of 182 specs'**
statuses, while the committed `experiments/specs/index.json`/`STATUS.md` at the wave tip are
**STALE** — `generated_at` `2026-09-02T17:03:06Z`, i.e. the pre-g1 derivation (before
`g1_split_run_evidence` changed `spec_status.py`), never regenerated after the derivation
landed. The two directions, each re-verified against the ledgers:

* **11 `failed → completed`** — every one has an EARLIER failed run (separate, unlinked family)
  plus a LATER full-coverage `ok` run whose `family_union` covers the full current phase list.
  Probed per spec (`_certifying_families` + `_family_status`): the newest family is
  `union_covers_full=True`. This is the unlinked-second-run fix working as designed — the old
  blunt any-failed-member guard was over-blocking them.
* **6 `completed → blocked`** — every one is a legacy split/partial whose phases were executed
  across UNLINKED runs (e.g. `admission_leases`: five runs, each a single phase `p1`…`p5`;
  `fleet_ladder_implementation`: `p0`+`p1` in awaiting runs, `p2`…`p7` in the final `ok` run).
  No single family's union covers the full list, so the old `any(ok is True) → completed`
  lie is now honestly `blocked`. Correct (conservative), and it is the SAME split-run class as
  F5, now surfaced on other specs.

Neither direction fabricates a false `completed` (each `failed → completed` has a genuine
full-coverage run; each `completed → blocked` is an honest downgrade). The finding is that the
shift is **broad, unregistered, and the derived surface is stale** — the wave's hard rule
"REGENERATE, NEVER HAND-EDIT" was not applied to its own derivation change. Regenerating the
index is a mechanical pre-merge action; the 17-spec shift should be reviewed by the controller
before it is published. See A5.

---

## 2. Attack g1_verifier_mount — can the verifier write its candidate through ANY mount?

### 2a. The candidate surface is mounted read-only — **YES, enforced at validation**

`build_verifier_request` (`spawn_wrapper.py:965-972`) flips EVERY surviving mount (exactly the
candidate surface after the forbidden-surface drops) to `ro` and stamps
`VERIFIER_REQUEST_MARKER`. `validate_spawn` step 3 (`spawn_wrapper.py:357-381`) then enforces the
contract at validation time: a verifier request may carry ONLY
`VERIFIER_READONLY_CATEGORIES` (`worktree`/`repo`/`repo-git`/`repo-alias`/`repo-alias-git`),
each `ro`; a `rw` candidate mount, or any `results`/`state`/`auth` category, is refused before
the socket call. Probed with the test family (`tests/test_spawn_wrapper.py`): a `rw` tamper of
`/tmp`, `/repo/.git`, or the host `.git` each yields a step-3 refusal; a forbidden-surface mount
is refused; the agent-phase request (no marker) keeps its `rw` candidate and validates clean.
The suite-target list is unchanged (`--only-phase <name>` + the phase's own `tests`).

### 2b. Is there a writable scratch surface? — **NO (finding A3)**

The request drops `STATE_TARGET` (`/state`), the results mount, and the auth mounts, and flips
everything else `ro`. The verifier child runs
`python3 scripts/run_workflow.py --only-phase <gate> --no-commit`, which for a `kind:test`
phase calls `test_runner._run_pytest` — `python3 -m pytest -q --tb=short <target>`
(`test_runner.py:57-61`), with **no `-p no:cacheprovider`** and `cwd=workdir` under the `ro`
`/tmp` mount. pytest's `.pytest_cache`, `tmp_path` fixtures, and `__pycache__` therefore have no
writable destination. The F1 mandate is satisfied (the candidate is genuinely read-only), but
the mandate's own escape hatch — "if the verifier genuinely needs a writable scratch area, it is
a separate, empty, non-candidate volume" — is **unimplemented**, and the `--run-docker` test
(`test_verifier_docker_roundtrip`) uses a no-write suite (`assert True`), so it cannot surface
the failure. Any real suite that writes a temp file will fail under the `ro` mount, and that is
unmeasured in CI. See A3.

---

## 3. Attack g1_revision_invalidation — mid-list edits vs the f4 false-positive

### 3a. Does a mid-list RENAME invalidate? — **YES**

`_is_definition_changed_after_runs` (`spec_status.py:410-463`) now fires shape (1) — name
evidence — `if executed - set(spec_phases): return True`. A legacy green run that executed
`w2_revision_identity` over a definition now naming it `w2_revision_invalidation` (same count)
invalidates: `derive_status` → `runnable` (never-run-of-this-revision), not `completed`.
Confirmed by `test_g1_midlist_rename_invalidates_a_legacy_green_run` and my own probe.

### 3b. Does a phase REMOVED after the runs invalidate? — **YES**

Same name-evidence branch: a legacy full run of `[p1..p4]` over a definition that removed `p4`
(or `p2` mid-list) leaves an executed name absent from the current list → `changed` → `runnable`.
Confirmed by `test_g1_removed_phase_invalidates_legacy_runs`.

### 3c. Does the partial-run corpus still false-positive (f4 shape)? — **NO for the recorded shape; residual at one depth (A2)**

The f4 shape the Wave-1 review recorded — a `p1`-only legacy run over a `p1..p5` definition —
no longer fires: `executed == set(spec_phases[:-1])` is False for `{p1}`, so
`_is_definition_changed_after_runs` → False and `derive_status` → `blocked` (its own honest
partial state). Confirmed by `test_g1_partial_run_corpus_without_an_edit_is_not_edited` and my
own probe.

### 3d. The SHAPE's "reordered / altered" clauses are NOT delivered — **RECORD (A1)**

The g1_revision_invalidation SHAPE mandates catching "a phase renamed, reordered, removed, or
altered (kind/scope/tests changed)". The delivery catches only what name-evidence can see
(rename + removal) plus the one-gate-deep trailing append (`executed == set(spec_phases[:-1])`).
Probed against the current code:

```
REORDER (same 5 names, new order)        _is_definition_changed = False -> completed
KIND/tests change (names unchanged)      _is_definition_changed = False -> completed
MID-LIST insertion (p_new between p1,p2) _is_definition_changed = False -> completed
```

A pure reorder, a kind/scope/tests-only alteration, and a mid-list insertion all leave a legacy
green run certifying `completed`. This is a *structural* limitation, not an oversight: legacy
ledgers record `executed_phases` as a `frozenset` of names (`spec_status.py:166,
summarize_run:239-243`), so order and per-phase metadata are irrecoverable; the digest catches
all three once a post-w2 run exists. The docstring records it (`spec_status.py:442-444`), but
hard rule (3) ("catches mid-list structural edits") and the SHAPE's "reordered"/"altered" prose
over-promise relative to what names-only legacy evidence can support. See A1.

### 3e. Residual partial-append false-positive — **RECORD (A2)**

Narrowing shape (2) to `executed == set(spec_phases[:-1])` fixes the recorded f4 shape (small
strict prefixes) but leaves one ambiguous depth: a corpus whose union is exactly
`spec_phases[:-1]` (all-but-the-last) is indistinguishable from a genuine trailing append, so it
still reads "edited" (`runnable`) even when it is a partial corpus with no edit. VERIFY (c)
tests only `{p1}` and `{p1,p2}`; the `{p1..p4}`-over-`p1..p5` depth is untested and still
false-positives under hard rule (3)'s "genuine subset" clause. This is a narrowing, not a
regression (the pre-g1 detector fired on EVERY strict prefix); the residual is inherent to
names-only evidence. See A2.

---

## 4. Attack g1_parity_roundtrip — envelope→classify exercised against the real executor?

### 4a. Is the classify contract exercised against the REAL executor (not a fake)? — **YES**

The round-trip harness (`tests/test_workflow_executor_parity.py`, §"g1 ... the round-trip
harness") drives the real `DockerVerifierExecutor.execute()` (`docker_verifier_executor.py:113-162`)
with `spawn_wrapper.spawn_sibling` as the ONLY injected seam (monkeypatched to return a canned
outcome in the exact `{"ok","argv","returncode","stdout","stderr"}` shape). Everything the
executor owns runs for real: `build_request` → `spawn_wrapper.build_verifier_request`,
`_classify(outcome)` (imported from `docker_executor`, the real envelope-first code at
`docker_executor.py:136-156`), `_phase_from_envelope`, and the `StepResult` construction. The
canned envelope is emitted INDENTED so the real `_parse_envelope` scans it — the classify path
is exercised, not stubbed. I verified the classify code itself is envelope-first (rc-0 +
`ok:false` envelope → `failed`; rc-10 → `awaiting`; rc-0 + no envelope → `ok`, see the minor
note in A4's tail), and that the harness covers: failed-suite envelope (rc-0 and rc-20),
passed-suite, awaiting (rc-10 and pre-contract rc-0), absent/garbage/spawn-refusal fail-closed,
and the full engine round trip (`phase.status == "failed"` on the ledger). 32 passed + 1 skipped
(the `--run-docker` opt-in marker; the module docstring documents the operator invocation).

### 4b. The docker marker is a true opt-in, never a silent pass — **YES**

`conftest.py` registers the `docker` marker and `pytest_collection_modifyitems` skips it unless
`--run-docker` is given, so the docker test is *visible* as skipped in every default run rather
than silently absent. The default gate run above shows exactly `1 skipped`.

### 4c. Minor (out of scope, pre-existing): rc-0 silent child → `ok`

`_classify` (`docker_executor.py:156`) returns `ok` for a child that exits `0` with NO envelope
(and no `awaiting`/`ok:false` to read). A real `run_workflow.py --only-phase` child always
prints its envelope before `SystemExit`, so this only fires for a broken/pre-contract wrapper
that swallows stdout and exits `0`; it is pre-existing `docker_executor` behavior, untouched by
this wave (scope fence held), and is not part of any F1-F5 mandate. Recorded here for
completeness, not as a wave finding.

---

## 5. Finding table

| # | Axis | Finding | Verdict | Severity |
|---|---|---|---|---|
| **A1** | g1_revision_invalidation | The SHAPE mandates catching a phase "renamed, reordered, removed, or altered (kind/scope/tests changed)", and hard rule (3) says "mid-list structural edits". Delivery catches only rename + removal (name evidence) + the one-gate-deep trailing append. A pure **reorder**, a **kind/scope/tests alteration**, and a **mid-list insertion** all still certify a legacy green run `completed`. Structural: `executed_phases` is a `frozenset` of names (`spec_status.py:166`), so order + phase metadata are irrecoverable; the digest catches all three for post-w2 runs. Documented at `spec_status.py:442-444` but over-promised by the SHAPE/hard-rule prose. | **RECORD** (accepted) | medium |
| **A2** | g1_revision_invalidation | Residual partial-append false-positive: `executed == set(spec_phases[:-1])` is indistinguishable from a genuine trailing append, so a partial corpus whose union is exactly `spec_phases[:-1]` still reads "edited"/`runnable` with no edit. VERIFY (c) tests only `{p1}` and `{p1,p2}`; the all-but-last depth is untested. Narrowing, not a regression (pre-g1 fired on every strict prefix). | **RECORD** (accepted) | low |
| **A3** | g1_verifier_mount | The read-only contract is complete for the candidate, but the verifier has **no writable scratch**: `run_suite` runs `python -m pytest` with no `-p no:cacheprovider` and `cwd` under the `ro` `/tmp`, so `.pytest_cache`/`tmp_path`/`__pycache__` writes fail. The mandate's "separate, empty, non-candidate volume" escape hatch is unimplemented, and the `--run-docker` test uses a no-write suite (`assert True`) so it cannot surface the failure. Candidate-write protection (F1) is unaffected. | **RECORD** (accepted) | medium |
| **A4** | g1_split_run_evidence | The FIRST `--resume` of a pre-g1 (legacy) failed/timed-out run does **not** union in `derive_status`: `create_run` (`control_db.py:1530-1538`) sets the child's `family_id = parent.run_id` but never backfills the legacy parent's empty `family_id`, and `_certifying_families` (`spec_status.py:518`) groups by `family_id` equality only — `parent_run_id` is recorded but never consulted. A clean split spanning the legacy boundary reads `blocked` instead of `completed`. Conservative (under-certifies; cannot fabricate a false `completed`); the live `engine_gaps_verifier_revision` shape is unaffected (its parent is already `failed`, the correct verdict). | **RECORD** (accepted) | medium |
| **A5** | cross (index) | The family-union `derive_status` re-derives the WHOLE corpus: regenerating the index shifts **17/182 specs** (11 `failed → completed`, 6 `completed → blocked`), while the committed `experiments/specs/index.json` + `STATUS.md` at the wave tip are **STALE** (`generated_at` 17:03, pre-g1 derivation, never regenerated). Each shift is correct and conservative (verified per spec — every `failed → completed` has a later full-coverage `ok` run; every `completed → blocked` is a legacy split/partial), but the shift is broad, unregistered, and the derived surface violates "regenerate, never hand-edit" for its own derivation change. | **RECORD** — regenerate the index before merge (17-spec shift for controller review) | medium |

No finding is a **FIX**-blocking re-open: none re-introduces the F5 split-run lie (a false
`completed`), none lets the verifier write its candidate, none re-opens the F1/F3/F4 recorded
defects. All five are conservative-direction, functional-completeness, or derived-surface gaps,
each recorded with the reasoning above and a forward-looking catch (the digest for A1/A2; a
separate scratch volume for A3; `parent_run_id`-chain grouping or parent backfill for A4; a
mechanical index regeneration for A5).

---

## 6. Re-verification evidence (the clean sweep, per axis)

| Axis | Mandate question | Verdict | Evidence |
|---|---|---|---|
| g1_split_run_evidence | live shape reads NOT-completed | PASS | `spec_status.py --spec engine_gaps_verifier_revision` → `failed`, `n_runs 2`, `latest_ok True`; live ledgers unlinked; in-process `derive_status` probes |
| g1_split_run_evidence | unlinked second run stays a separate family | PASS | `_certifying_families` `\x00self:` fallback; probe: unlinked fresh full run → `completed`, unlinked partials → `blocked`/`failed` |
| g1_split_run_evidence | linked family union + any-failed-member | PASS (A4 at legacy boundary) | probe: linked failed-parent+child → `failed`; clean linked split → `completed` |
| g1_split_run_evidence | ledger family link round-trips | PASS (post-g1 parents) | `test_g1_ledger_family_link_round_trips` (both carry `family_id`); `test_control_db` family suite |
| g1_verifier_mount | candidate worktree + `.git` ro | PASS | `test_verifier_request_mounts_the_candidate_read_only` (all five targets `ro`) |
| g1_verifier_mount | rw-candidate / forbidden surface refused before spawn | PASS | `test_verifier_request_that_would_mount_candidate_rw_fails_validation` + `..._refused_before_any_spawn` |
| g1_verifier_mount | agent-phase mounts unchanged | PASS | `test_agent_phase_request_keeps_rw_candidate_mounts` (no marker, rw) |
| g1_verifier_mount | suite-target semantics unchanged | PASS | `test_verifier_request_keeps_the_in_process_suite_target` |
| g1_revision_invalidation | mid-list rename invalidates | PASS | `test_g1_midlist_rename_invalidates_a_legacy_green_run` + probe |
| g1_revision_invalidation | phase removed invalidates | PASS | `test_g1_removed_phase_invalidates_legacy_runs` |
| g1_revision_invalidation | partial corpus no false-positive (f4 shape) | PASS (residual A2) | `test_g1_partial_run_corpus_without_an_edit_is_not_edited` + probe |
| g1_revision_invalidation | trailing append still invalidates | PASS | `test_g1_trailing_append_still_invalidates` |
| g1_revision_invalidation | full-coverage still certifies | PASS | `test_g1_full_coverage_legacy_run_still_certifies_completed` |
| g1_parity_roundtrip | envelope-classify vs real executor | PASS | round-trip harness drives real `execute()`/`_classify`/`_phase_from_envelope`; 32 passed + 1 docker-skipped |
| gate | g3_test_gate files | PASS | `test_workflow_executor_parity` + `test_spec_status` + `test_workflow_runner` + `test_experiment_spec` + `test_spawn_wrapper` + `test_doc_lifecycle` + `test_script_classification` + `test_agent_config_render` + `test_cli_resolution` (+ `test_control_db`, `test_fact_auto_emit`) → **533 passed, 1 skipped** |
| pin | spec not edited mid-run | PASS | `sha256sum` unchanged `9c45a76f…` = the pin |

---

## 7. Release verdict

**MERGE-READY — PASS, with five findings recorded (A1-A5).**

All five Wave-1 defects are closed as specified: F5 (the split-run lie) is closed for the live
shape and the family-union derivation is in place with the unlinked-family invariant; F1 (the
writable candidate) is closed by the read-only mount contract enforced at validation, never
behaviorally; F3 (mid-list rename) and F4 (partial-run false-positive) are closed by name
evidence + the narrowed append detector; F2 (unmeasured parity) is closed by a round-trip
harness that drives the real executor with the docker boundary as the only injected seam.

The five recorded findings are all conservative-direction, functional-completeness, or
derived-surface gaps: A1/A2 are inherent to names-only legacy evidence (digest-caught forward);
A3 is a missing writable scratch volume (candidate remains read-only, so F1 holds); A4 is a
legacy-boundary family-merge gap that under-certifies and cannot fabricate a false `completed`;
A5 is the stale derived index — a mechanical `python scripts/spec_status.py` regeneration shifts
17 specs (11 `failed → completed`, 6 `completed → blocked`), each direction verified correct,
and this regeneration should be run (and the shift reviewed) as the pre-merge action. None
re-opens a defect, none manufactures completion from a split, none lets the verifier write its
candidate. The controller may elect to close A3 and A4 in a followup (each has a one-line fix
path: pin `-p no:cacheprovider` + a scratch volume; group by `parent_run_id` chain or backfill
the parent `family_id`); A5 is a required pre-merge regeneration, not a code change.
