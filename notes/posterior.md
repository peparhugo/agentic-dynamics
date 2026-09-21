# Posterior — Item 4: the stale next-action state

*Final phase of the world-model loop. Read-only with respect to production code. Every claim is
grounded in a file, a commit, a KB record, or a command output. The diff is against
`notes/world_model.md` (the prior) and `notes/plan.md`; the deviations record is
`notes/deviations.md`.*

## Verdict

The plan's central prediction held: **the c15 gap is closed at the capsule-composer layer for the
one confirmed action that records — a durable submit — and the execute phase landed the missing
carrier-level regression check, not a source change.** The three named tests exist and pass
(`242 passed` across the three suites, `ruff check` clean). Two things the model did not carry are
now visible: the *delivery* layer still has a bounded staleness window the regression does not
cover, and the execute phase performed a large, unrecorded whole-file reformat that contradicts
the plan's "smallest fix" scope.

---

## 1. VIOLATIONS — where reality differed from the world model

### V1. The world model claims the *carrier* is fixed; the regression actually pins the *composer*

`notes/world_model.md:73-75` states the property unconditionally: "once the submit records, the
capsule's next action is the `[auto]` job observation and the completed instruction is gone." The
tests prove that for `compose_capsule`, but the per-request carrier is the TypeScript plugin, which
**caches the composed capsule for 30 s and reuses it**.

- `.opencode/plugins/aio-context.ts:86` — `const CAPSULE_TTL_MS = 30_000`.
- `.opencode/plugins/aio-context.ts:839-842` — `deliverSnapshot` returns
  `cached?.text` whenever `Date.now() - cached.at < ttlMs`.
- The cache is invalidated **only** by the plugin's own update path
  (`.opencode/plugins/aio-context.ts:796` — `capsules.delete(sessionID)`). A durable write made by
  another process — `fleet_manager.py submit`, the ordinary AIO path — does **not** invalidate it.

So for up to 30 s after an out-of-process submit, the live carrier can still render the completed
`next_action`. The regression (`tests/test_fleet_manager.py:1599`,
`tests/test_session_binding.py:782`) composes fresh from the read-back binding and therefore never
exercises this window. The world model named the mechanism correctly but over-claimed the closure
class. The plan itself flagged the risk (`notes/plan.md:124-126`) and instructed "STOP and record
the deviation"; the tests avoided the plugin, so the risk never fired and the residual was never
recorded.

### V2. Unrecorded scope expansion: a whole-file reformat in the execute commit

The execute commit is `3689fb233`. Its diff is **851 insertions / 241 deletions** across two test
files — overwhelmingly `ruff format` reflowing pre-existing code, not the three tests the plan
authorized (`notes/plan.md:27-28`).

```
$ git show --stat 3689fb233
 notes/deviations.md           |   30 ++
 tests/test_fleet_manager.py   |  775 ++++++++++++++++++++++++++++++++++------
 tests/test_session_binding.py |  287 ++++++++++++----
```

The files were unformatted **before** the commit:

```
$ git show f2d939783:tests/test_fleet_manager.py > /tmp/tfm_before.py
$ git show f2d939783:tests/test_session_binding.py > /tmp/tsb_before.py
$ ruff format --check /tmp/tfm_before.py /tmp/tsb_before.py
2 files would be reformatted          # but:
$ ruff check /tmp/tfm_before.py /tmp/tsb_before.py
All checks passed!
```

CI runs `ruff check .` and **not** `ruff format --check`
(`.github/workflows/pytest.yml:44`), so the reformat was neither required nor caught. The plan's
§1 file table says "ADD tests"; it names no formatting work, and `notes/deviations.md` records no
delta for it — a violation of the plan's own acceptance criterion §4.5 ("records any delta") and of
the loop's "smallest fix" instruction. It is semantically inert, but it inflates the permanence-gate
diff and broke the prior's navigation (V3).

### V3. The reformat invalidated the prior's line references

The world model navigated by line number. The reformat moved every referenced test:

| prior reference | reality at prior time (`f2d939783`) | after execute (`3689fb233`) |
|---|---|---|
| `tests/test_fleet_manager.py:1023` | `test_a_submission_records_its_job_into_the_task_state` | `:1247` |
| `tests/test_fleet_manager.py:1059` | `test_a_stale_revision_never_overwrites_the_task_state` | `:1303` |
| `tests/test_session_binding.py:300` | `test_next_action_precedence` | moved |
| `tests/test_session_binding.py:570` | `test_capsule_reflects_the_updated_context` | moved |

The world model's references were accurate when written; the drift is a *consequence* of V2, not a
prior error. It is recorded here because the next model reads `world_model.md` and will navigtate
by those stale numbers.

### V4. The deviations record's KB claim contradicts the world model's own probe

`notes/deviations.md:15` records: "`python3 scripts/kb_read.py --query ... --scope
agentic-dynamics` returned `hits=0` (ranked)". But the world model's own §3 (lines 114-116) reports
the same ranked mode returning the design finding `e6222c1ca0de8ead`. Re-run today:

```
$ python3 scripts/kb_read.py --query "stale next action binding capsule regression" --scope agentic-dynamics
[kb-read] ... mode=ranked hits=2
  51e507a9cc25a296 | finding | audit:retrieval
  e6222c1ca0de8ead | finding | design:world-model-loop
```

Ranked retrieval never depended on `experiments/results/registry_index.jsonl`; only `--contains`
does (`scripts/kb_read.py:94` raises `FileNotFoundError` — reproduced in this worktree). The
deviations record conflated the two modes. The world model's §5 risk correctly named the
`--contains` failure; `deviations.md` restated it as a ranked failure. Minor, but it is a
reconstruction that a later reader could trust as the KB being empty.

### V5. The loop's own outputs are git-only — no KB finding was emitted

The spec declares the emit intent (`workflows/repository/world_model_loop.yaml:26-31`:
`rag_augment: false`, `rag.emit_self: true`, `rag.emit_report: true`,
`emit_scope: agentic-dynamics`) and the design's stated purpose is "the loop's world-model/plan/
posterior notes must be knowledge, not only git files"
(`src/agentic_dynamics/runtime/workflow_runner.py:5331-5334`). Reality at posterior time:

```
$ ls experiments/results/kb                -> No such file or directory
$ ls experiments/results/workflows         -> contemplation_synthesis_rerun (only)
$ python3 scripts/kb_read.py --query "world model loop item 4 ..." --scope agentic-dynamics
  -> hits=2 (the design + the retrieval audit; no record from this run)
```

Neither the prior nor the execute produced a retrievable finding or a report artifact. Either emit
was disarmed (`FINOPS_EMIT_SELF=0`, the unit-suite flag) or it failed silently — `_emit_self_finding`
swallows every exception by construction (`workflow_runner.py:1768-1770`). A silent emit failure is
indistinguishable from success, so the run cannot demonstrate the property it exists to test.

---

## 2. UNKNOWNS DISCOVERED — what the next model must carry

1. **The delivery cache is a real, bounded staleness channel not covered by the regression.**
   Composer-level correctness (proven) ≠ carrier-level absence of staleness (unproven). Any future
   claim of the form "a completed instruction can never remain the actionable next action" must
   state the layer and the window. Reduce: either a plugin-level test (hard — TS/opencode runtime)
   or a documented, named residual with the 30 s bound. Do not widen a bounded item to close it.
2. **Silent emit means "no finding" is not evidence of "no emission."** `_emit_self_finding` and
   `_emit_research_report` both `except Exception: pass`. The runner has no observable ack that a
   KB record landed. Reduce: a `notes/` run with emit armed should assert its own artifact exists
   (`experiments/results/kb/<id>.json` or `experiments/results/workflows/<spec>/reports/`), and the
   posterior should check it — which this posterior did.
3. **`emit_scope` is honored only by the report variant.** `_emit_self_finding` is called with
   `scope=cell_scope(wd)` (`workflow_runner.py:5326`), producing `self-<worktree>` (for this tree,
   `self-wml_run2`); only `_emit_research_report` reads `rag_params["emit_scope"]`
   (`workflow_runner.py:1854`). The spec's `emit_scope: agentic-dynamics` therefore does **not**
   place the metadata findings in the shared scope. Not known at prior time; it matters for the
   loop's stated goal of writing its notes into `agentic-dynamics`.
4. **Confirmed actions other than submit still do not record** (world model §4.2; `deviations.md`
   §"Out of scope"). `approve_workflow.py` carries no session identity and never calls
   `update_binding_context`; if the AIO sets `next_action = "approve gate X"`, approval leaves the
   field stale. Bounded, named, unfixed — carry it, do not silently treat the c15 class as closed.
5. **The plan's stated acceptance criterion is unenforced by the tooling.** §4.5 requires
   `deviations.md` to record "any delta", but nothing checks that a delta (here: formatting) was
   recorded. The execute phase passed every command in `notes/plan.md` §3 while still violating §1
   scope. Reduce: a prior-phase convention, not a new gate (see UPDATES C1).

---

## 3. UPDATES — the concrete update set

### A. KB findings to emit (scope `agentic-dynamics`, existing producer path)

**A1 — the verification outcome (authority MEASURED; the loop's own result).** Text: *"c15
stale-next-action: the gap is CLOSED at the composer layer for the durable-submit path.
`_record_submission_in_task` (`scripts/fleet/fleet_manager.py:853`) REPLACES the binding's
`next_action` under a context-version guard (recorded at `:1326`, note `:1348`); the capsule
renders the binding value with precedence (`scripts/session_open.py:393-400`). Pinned by three new
regressions: `tests/test_session_binding.py:610, 782` and `tests/test_fleet_manager.py:1599`
(242 passed)."* Cite the commit `3689fb233` and the c15 source
(`experiments/results/fork_contemplation/wave1/c15.md:20`).

**A2 — the named residual (authority ADVISORY [H]).** Text: *"Two residual staleness channels the
submit-path fix does not close: (i) the per-request carrier's 30 s capsule cache
(`.opencode/plugins/aio-context.ts:86,839-842`) is not invalidated by out-of-process durable
writes, so a completed `next_action` may render for ≤30 s; (ii) confirmed actions without a
binding address (e.g. `approve_workflow.py`) do not record at all."* This is the honest boundary of
the bounded improvement; it must be retrievable so the next loop does not re-litigate closure.

**A3 — the process correction (authority ADVISORY [H]).** Text: *"A bounded regression change must
not carry a whole-file `ruff format` sweep: CI gates on `ruff check .`, not `ruff format --check`
(`.github/workflows/pytest.yml:44`); an unformatted file passes. Reformatting inflates the
permanence diff and invalidates prior line references."* Evidence: `git show --stat 3689fb233`.

Emit these through `emit_phase_finding`/`derive_phase_record` (the existing producer path), not a
new family. Note the run did **not** auto-emit V5; this is a manual update step until the emit is
verified.

### B. Conventions to record

- **C1 (recording completeness):** *A mechanical change is still a delta.* A whole-file formatter
  run, a line-ending normalization, or any edit outside `notes/plan.md`'s file table belongs in
  `notes/deviations.md` even when it passes lint. "The tests pass" is not "no deviation."
- **C2 (layer discipline):** *Name the layer a property is proven at.* A regression against a pure
  function (`compose_capsule`) proves the function, not the delivery path (the plugin). When a
  finding says "the carrier", the test must say which carrier. Prefer a named residual over silently
  narrowing the claim.
- **C3 (emit observability):** *A silent emit is unverified emit.* When a spec opts into
  `rag.emit_self`/`emit_report`, the phase's exit check should confirm its artifact exists; the
  posterior should verify it (as §V5 does).

### C. Skills / knowledge to create or amend

- **`run-workflow` skill:** add the scope gotcha — `rag.emit_self` metadata findings land in
  `cell_scope(wd)` = `self-<worktree>`, while `rag.emit_report` honors `rag.emit_scope`
  (`workflow_runner.py:5326` vs `:1854`). A spec that asks for shared-scope knowledge needs
  `emit_report: true`; `emit_self` alone will not put findings in `agentic-dynamics`.
- **`run-workflow` skill / workflow-runner docs:** note the best-effort `except Exception: pass`
  in both emit paths, with the observable artifacts to check
  (`experiments/results/kb/`, `experiments/results/workflows/<spec>/reports/`).
- **`notes/` loop template (the design doc `docs/designs/proposed/world_model_loop.md`):** state
  that the posterior's deliverable includes an emitted finding, and that the loop is not complete
  until A1/A2 land in the registry.

### D. What should change in the next loop's prior phase

1. **Baseline the formatter.** Run `ruff format --check` on the files the plan intends to touch and
   record the result. If a file is unformatted, decide once — leave it (CI does not require it) or
   do the reformat as a separate, explicitly-scoped change — and write that decision into
   `notes/plan.md` §1. This is the direct fix for V2/V3.
2. **Prove the layer, don't assume it.** For any finding whose subject is a "carrier" / "delivery",
   trace the actual delivery path in the prior (here: `.opencode/plugins/aio-context.ts`) and list
   its caches/windows as explicit unknowns. The prior read the composer and the binding but treated
   the plugin's TTL as a risk footnote, not a fact to carry.
3. **Check whether the loop can emit at all.** Before writing, verify the workflow's emit is armed
   and that prior runs' artifacts exist; otherwise the loop's stated purpose is unmet and the
   posterior must say so (V5).
4. **Enumerate the residual set in the acceptance criteria**, not only in `deviations.md`'s
   "out of scope" tail — so the posterior can measure against a declared boundary rather than a
   post-hoc one.

---

## 4. Probe log (what was read, and why)

| probe | why | result |
|---|---|---|
| `notes/world_model.md`, `notes/plan.md`, `notes/deviations.md` | the model and plan under test | mechanism claims accurate; carrier claim over-broad; format delta unrecorded |
| `git show 3689fb233` / `--stat` | what execute actually did | 851+/241-, overwhelmingly `ruff format`; 3 tests + 1 helper added |
| `ruff format --check` on `f2d939783:` test files | was the reformat necessary? | "2 files would be reformatted"; `ruff check` passed before |
| `.github/workflows/pytest.yml:44` | is format gated in CI? | no — `ruff check .` only |
| `.opencode/plugins/aio-context.ts:86,796,839-842` | the real per-request carrier | 30 s TTL cache; invalidated only by the plugin's own update |
| `scripts/fleet/fleet_manager.py:853,1326,1348` | the confirmed action's recording | `_record_submission_in_task` replaces `next_action` |
| `scripts/session_open.py:393-400,521` | capsule precedence/rendering | binding value wins; rendered in the protected tail |
| `tests/test_session_binding.py`, `tests/test_fleet_manager.py` (run) | do the regressions pass? | 242 passed; `ruff check` clean |
| `workflow_runner.py:5326,1854,1768-1770` | where do emitted findings land? | `emit_self` → `cell_scope`; `emit_report` → `emit_scope`; both swallow errors |
| `experiments/results/kb`, `.../workflows` (ls) | did the loop emit? | absent/empty — the loop's notes are git-only (V5) |
| `kb_read.py --query ... --scope agentic-dynamics` (ranked and `--contains`) | prior records / closure claims | ranked hits=2; `--contains` raises (`registry_index.jsonl` absent) |
| `experiments/results/fork_contemplation/wave1/c15.md:20` | the finding under test | stale-intent item; §4.6 proposed regression |
| `docs/reviews/aio_arc_findings_and_results.md:140-141,179-180,190-191` | Item 4's directive + claim class | bounded improvement; verify first; no new memory format |
