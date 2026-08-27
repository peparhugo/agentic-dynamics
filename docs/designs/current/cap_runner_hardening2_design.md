---
status: accepted
---
# cap_runner_hardening2 — design: closing the two remaining execution gaps

**Status: accepted** · Predecessor: `cap_runner_hardening` (merged — the phase watchdog,
deploy gate, commit enforcement). This design closes the two gaps the post-mortem + the
hardening review identified as still open.

## Gap 1 — the server-level orphan sweep

### The measured problem

The terra post-mortem's F1 corrected the session's own diagnosis: the one verified
43.4-minute stall was NOT a silent model — it was an **orphaned delegation**. The
authoring agent session (in the opencode server) spawned a task (subagent); the parent
session died mid-delegation; the subagent **completed** but its result was never reaped.
43 minutes of blind window with nothing in the machine noticing.

The runner-level watchdog (merged) cannot see this case: it watches the runner's own agent
process's transcript. When the agent (the parent) dies, the runner sees a process exit —
not a stall. The orphan lives in the OPENCODE SERVER layer (session + spawned-task state),
which the runner never observes.

### The design

A **server-level orphan monitor** — the sweep, at the layer where sessions and their
spawned tasks actually live:

- **Observation surface:** the opencode server's session store (the session transcripts +
  the server's task state — the same surface the Control Room's supervisor rail already
  reads). Each agent session may spawn tasks; a task is identified by its session parent +
  its subagent process/session.
- **Detection:** a task whose (a) parent session has no step after the task's spawn time
  AND (b) the subagent session/process has terminated (completed or crashed) is an
  **orphan**: its result was produced but never reaped.
- **Action (flag-only, per the supervisor discipline):** the sweep records the orphan on
  the registry/ledger (idle_minutes, parent, subagent, result-availability), kills the
  orphaned subagent process if still alive, and surfaces it — the next runner phase or the
  operator sees the orphan record. It does NOT steer the parent's campaign (the supervisor
  is observe-only).
- **Cadence:** a periodic sweep (default every 5 min) + the detection is a function of the
  transcript timestamps (parent last-step vs subagent termination), deterministic and
  testable with synthetic session fixtures.
- **Where the code lives:** the Control Room server (apps/control_room/) already hosts the
  supervisor rail — the sweep is a supervisor-side monitor there (or a small companion
  daemon scripts/orphan_sweep.py reading the same surfaces), reading the opencode session
  store; the runner is NOT involved (it cannot see the layer).

### Acceptance criteria

1. A synthetic orphan (parent silent, subagent completed) is detected within one sweep
   cycle with the evidence (timestamps, idle_minutes).
2. A live parent (still stepping) with a running subagent is never flagged.
3. The orphan record lands on the registry/ledger (queryable, dated, flagged) — the
   post-mortem's requirement: "stalls become dated, flagged events instead of anecdotes."
4. The sweep is flag-only: it never restarts, retries, or steers a session.

## Gap 2 — the relabel tree-diff gate with the operator-approval escape

### The measured problem

The revamp2 execution's F2: attempt A's tree was **reset away** entirely, then attempt B
(the "resume") committed a **tree-identical copy** under compliant `[workflow] p1–p3`
messages (`git diff f6fc35edf 20eeb801b` is empty). The merged commit enforcement checks
the MESSAGE — the relabel's messages matched, so the relabel would pass the current gate.
The relabel is a gaming move: discarded work re-presented as fresh work.

### The design

A **tree-identity gate** on top of the commit enforcement:

- **Recorded state:** the runner already records pre-phase HEAD. Add: the committed **tree
  hash** (`git rev-parse <commit>^{tree}`) of every phase's result, AND the tree hash of
  every **discarded/rolled-back state** (the runner's reset/rollback path records the tree
  it discards — a `discarded_trees` ledger, keyed by (spec, branch, tree-hash, discarded_at)).
- **Detection:** post-phase, if the phase's committed tree hash matches any recorded
  discarded tree → the phase FAILS with reason `RELABEL` + the evidence (the matching
  discarded-tree record, the identical-tree proof).
- **The operator-approval escape (the false-positive guard):** legitimate resume of
  rolled-back work exists (an operator may deliberately restore a discarded tree and
  resume from it — the resume machinery's matching-hash requirement is the legit path).
  The escape: an approval artifact (`approvals/<spec>/<phase>_tree_reuse.md`) signed by
  the operator, committed BEFORE the phase runs (or attached at resume time), names the
  discarded tree hash and the phase authorized to reuse it. The gate checks the approval
  ledger first: an approved tree-hash reuse passes; an unapproved one fails RELABEL.
- **Interaction with resume:** the resume machinery's goal-hash + commit matching already
  gates legit resumes; the tree gate only fires when the SAME tree is re-presented as a
  DIFFERENT phase's fresh work (or after a discard). The design keeps the two mechanisms
  distinct: resume = matching hashes + commits; tree gate = no silent re-presentation of
  discarded work.

### Acceptance criteria

1. A relabel (discarded tree re-committed under compliant messages, no approval) fails
   RELABEL with the identical-tree proof — the revamp2 attempt A/B scenario replayed as
   the regression proof.
2. An operator-approved tree reuse (the approval artifact committed first) passes.
3. A genuine resume of committed work (never discarded) never fires the gate.
4. The gate is off for non-agent phases; the runner's own `_git_commit` path is exempt
   (it never re-commits discarded trees).

## The campaign (cap_runner_hardening2)

- **p1_orphan_sweep** — implement the server-level sweep (observation, detection, the
  flag-only record, cadence) + synthetic-fixture tests both directions.
- **p2_relabel_tree_gate** — implement the tree-identity gate + the approval escape +
  the discarded-trees ledger + the revamp2 replay proof + tests both directions.
- **p3_integration** — runner + control-room test surfaces green; live smokes (a
  synthetic orphan detected; a relabel attempt failed; an approved reuse passed; a legit
  resume unaffected).
- **p4_adversarial** — bypass attempts (hash spoofing via tree manipulation, approval
  forgery, orphan-evasion, false-positive attacks) + known-safe; no bare PASS.

## Links

- Post-mortem: `docs/designs/current/cap_terra_postmortem.md` (F1 orphaned delegation,
  P5 run-level liveness + orphan sweep, P6 relabel)
- Hardening (merged): `docs/reviews/cap_runner_hardening_adversary.md` (the two
  accepted-limitation gaps this closes)
- Regression: `docs/designs/current/cap_site_regression_analysis.md`
