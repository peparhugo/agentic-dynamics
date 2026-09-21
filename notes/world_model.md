# World model — Item 4: the stale next-action state

*Prior phase of the world-model loop. Read-only: no production code touched. Every claim below
is grounded in a file, a KB record, or a command output.*

## 0. The task, verbatim from its source

From `docs/reviews/aio_arc_findings_and_results.md:140-141` (controller-directed 2026-09-20):

> (4) turn one useful finding into a bounded improvement using existing machinery — stale
> next-action state **or** a missing regression check, after verifying the gap exists today

and `docs/reviews/aio_arc_findings_and_results.md:179-180` (Claim classes → Observed):

> Historical observation to re-check before building: a binding still instructing "activate,
> then submit" after both had happened (wave1/c15:20).

The finding itself, `experiments/results/fork_contemplation/wave1/c15.md:20`:

> **Intent as a current unit, not a completed instruction.** Binding `fbca5106` (v2) says *"After
> the controller activates PR #77 … call run_workflow"*. Activation happened; the run went out;
> **nothing rewrote the binding**. The per-request carrier now instructs a finished sequence.

The prior prompt's own framing of the decision: *"implement the smallest fix with existing
machinery (keep the existing task state current after confirmed actions; not a new memory
format) plus tests. If the stale-state gap no longer exists, land the missing regression check
instead."*

## 1. What the problem is believed to be

A durable session binding carries a `next_action` field. The capsule composes it and delivers it
to the model as the CURRENT "one next action" (`scripts/session_open.py:393-406`, rendered in the
protected tail at `scripts/session_open.py:490-492, 521-522`). If nothing rewrites that field
after the action it names has actually happened, the carrier keeps instructing a finished
sequence — the successor re-derives true state from prose. The proposed-but-unbuilt c15 remedy
was a new `handoff` object (`c15.md:51-97`); the review deliberately kept the *smaller* direction
and rejected new structure: "keep the existing task state current after confirmed actions — the
first fix, not another memory format" (`aio_arc_findings_and_results.md:190-191`).

So the question this phase must answer, mechanically: **does a confirmed action today rewrite the
binding's `next_action`, or can a completed instruction survive as the actionable next action?**

## 2. What exists today (the mechanism)

A confirmed AIO action — a durable workflow submit — already records itself into the existing
binding. `scripts/fleet/fleet_manager.py`:

- `_record_submission_in_task(...)` (`scripts/fleet/fleet_manager.py:853`) builds a labeled,
  deterministic `[auto] submitted job <job_id> …` (or `[auto] reconciled to job …`) string and
  writes it as the binding's `next_action` through the EXISTING versioned machinery:
  `si.update_binding_context(..., context={"next_action": action}, expected_version=..., ...)`
  (`scripts/fleet/fleet_manager.py:898-903`).
- It is called on every durable submit immediately after the command is queued
  (`scripts/fleet/fleet_manager.py:1322-1328`), and its result is reported as `task_note` in the
  `fleet-submit/v1` payload (`scripts/fleet/fleet_manager.py:1348`).
- The AIO path reaches it: the `run_workflow` tool passes `--aio-session-id`,
  `--aio-agent`, `--binding-id`, `--binding-context-version` (`.opencode/tools/run_workflow.ts:123-131`);
  the submit branch consumes them and records. The rules require the durable fleet path for spec
  workflows, so this is the ordinary path, not a corner.
- Provenance: commit `246490028` "recording: submissions record their pending job into the
  durable task state" (2026-09-16) is an ancestor of HEAD (verified:
  `git merge-base --is-ancestor 246490028 HEAD`); its follow-up `ceaec532e` (2026-09-17)
  separated the authorization epoch from operational progress so this recording does not
  invalidate queued commands.

The write semantics are REPLACE, not append: `_apply_context_update` does
`merged = dict(payload); merged.update({field: context[field] for field in
BINDING_CONTEXT_FIELDS if field in context})` (`src/agentic_dynamics/knowledge/session_ingestion.py:1517-1520`),
and `next_action` is in `BINDING_CONTEXT_FIELDS`
(`src/agentic_dynamics/knowledge/session_ingestion.py:851-859`). The old value is retained only
in the bounded `context_history` (`:1542-1548`), so replacement loses no auditable fact.

The capsule reads the binding's `next_action` FIRST, ahead of any predecessor open-thread
(`scripts/session_open.py:393-400`). So once the submit records, the capsule's next action is the
`[auto]` job observation and the completed instruction is gone.

Existing tests pin the mechanism but not the carrier property:

- `tests/test_fleet_manager.py:1023` `test_a_submission_records_its_job_into_the_task_state`:
  a submit sets `next_action` to the `[auto]` record, `context_version` 1→2, authorization
  stable.
- `tests/test_fleet_manager.py:1059` `test_a_stale_revision_never_overwrites_the_task_state`:
  the version guard.
- `tests/test_fleet_manager.py:1151` `test_a_recorded_submission_still_passes_delayed_consumption`
  and `test_spawn_wrapper.py:2043` `test_progress_recording_does_not_advance_the_authorization`.
- `tests/test_session_binding.py:300` `test_next_action_precedence` and
  `tests/test_session_binding.py:570` `test_capsule_reflects_the_updated_context` — the latter
  checks acceptance only, never that a superseded `next_action` is gone.

## 3. Verification: does the gap exist today?

**Finding: the gap is CLOSED for the confirmed action wired today — a durable submit.** There is
no code path by which a binding that says "activate PR #77 … call run_workflow" can remain
unrewritten *after the submit it names has happened through the fleet path*, because that submit
overwrites `next_action` with the `[auto]` job record and the capsule renders the new value with
precedence. The c15 scenario's "run went out" step is exactly the trigger.

**What is missing is the regression check, not the fix.** No test asserts the c15 property at the
carrier level: that a stale, already-completed `next_action` cannot survive a confirmed action
into the capsule. `grep` over `tests/` finds the `[auto]` assertion only at the binding layer
(`tests/test_fleet_manager.py:1048-1051`), never composed into a capsule against a *previously
stale* instruction. c15's own §4.6 test was exactly this ("after activation, an update sets
`stage='submitted'`; assert the capsule's next action no longer contains 'activate PR #77' — a
completed gate can never remain the actionable next action"), and it was never landed because the
`handoff` object it assumed was not built.

KB grounds (`kb_read.py`, canonical checkout — the run worktree lacks
`experiments/results/registry_index.jsonl`, so `--contains` there raises `FileNotFoundError`):

- The prior close carrying Item 4 is `70c84cd676ec58bb` (`meta_session`, slug
  `aio-correction-delivery-repair`, 2026-09-20), open-thread text: "item 4: one bounded
  improvement using existing machinery — stale next-action state OR a missing regression check —
  after verifying the gap exists today".
- A ranked read for `next action` on scope `agentic-dynamics` returns only the world-model-loop
  design finding `e6222c1ca0de8ead`. No KB record claims the c15 gap was verified closed, so the
  verification is this phase's own.

## 4. Unknowns (gaps) and what would reduce each

1. **Carrier-level staleness is unproven by test.** The replacement semantics are asserted only
   at the binding layer. *Reduce:* add a capsule-level regression that seeds a completed
   `next_action`, performs the confirmed write, and asserts the capsule's next action is the new
   record and does not contain the completed text.
2. **Residual class: confirmed actions other than submit do not record.** `approve_workflow.py`
   emits a decision record but never touches a binding (`grep` for `update_binding_context` finds
   no call in it), and it carries no native session id with which to address a binding. If the AIO
   ever sets `next_action = "approve gate X"`, an approval leaves that field stale. *Reduce:* do
   not build a new mechanism; document this precisely as a known residual with the reason
   (no session identity at the approval boundary) and leave it for a future bounded item. A
   regression test may pin the *covered* submit case; it must not claim coverage of approvals.
3. **Whether the existing tests actually exercise the replace (not append) semantics for
   `next_action` against a non-empty prior value.** `test_updates_are_versioned_and_preserve_the_request`
   sets `next_action = "review the PR"` on an empty prior value. *Reduce:* add an explicit
   assert that a non-empty prior `next_action` is replaced and that the prior value survives only
   in `context_history`.
4. **The in-process (`orchestrator=false`) path does not record.** Explicitly a separate,
   explicitly-requested mode for trivial deterministic runs; out of scope by the project rules.
   *Reduce:* state it as a non-goal in the plan, no code.

## 5. Conclusion carried into the plan

- No source fix is required for the c15 submit case; Unit 3 already keeps the task state current
  after the confirmed action. The bounded improvement is the **missing regression check** that
  pins the carrier property, plus an explicit replace-not-append assertion.
- If, and only if, the tests reveal a real path where the stale instruction survives (e.g., a
  capsule composed without the recording, or an append instead of a replace), the plan's fallback
  is the minimal existing-machinery fix — never a new record family, never the `handoff` object.

## 6. Probe log (what was read, and why)

| probe | why | result |
|---|---|---|
| `experiments/results/fork_contemplation/wave1/c15.md` | the finding under test | §1 stale-intent item; §4.6 proposed regression |
| `docs/reviews/aio_arc_findings_and_results.md:120-205` | Item 4's exact directive + claim class | bounded improvement, verify first |
| `scripts/fleet/fleet_manager.py:800-910,1280-1360` | does a confirmed action record? | yes — `_record_submission_in_task` |
| `src/agentic_dynamics/knowledge/session_ingestion.py:786-1580` | binding read/write/update semantics | replace + version guard + history |
| `scripts/session_open.py:328-525` | capsule next-action precedence + rendering | binding wins; protected tail |
| `.opencode/plugins/aio-context.ts` | the per-request carrier + updates | attachment cannot clear a field; freshness guard prevents stale replay |
| `.opencode/tools/run_workflow.ts:108-140` | does the AIO path carry binding context? | yes |
| `git log` / `merge-base` | is the fix in HEAD? | `246490028` is an ancestor |
| `tests/test_fleet_manager.py`, `tests/test_session_binding.py`, `tests/test_spawn_wrapper.py` | what is already pinned | mechanism yes; carrier property no |
| `kb_read.py --contains next-action` (canonical checkout) | prior records/decisions | close `70c84cd676ec58bb` carries Item 4; no closure claim |
