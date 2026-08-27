---
status: accepted
---

# cap_runner_hardening2 — adversarial verification

**Role:** adversarial verifier (p5). **Source revision:** the p4 integration tip (`a91e02ab6`).
Attacks in the order the campaign defines: orphan evasion, relabel evasion, checkpoint evasion,
regression, and the usual secrets/hashes suite. Every finding is either **FIXED** (with a
re-test) or recorded as an **accepted limitation** with reasoning + residual risk. One real
defect was found and fixed (F1).

## Findings table

| # | Attack (order) | Result | Disposition |
|---|---|---|---|
| F1 | (1) orphan — a malformed session whose `parent_id` points at ITSELF is flagged as its own orphan | **FALSIFIED** | **FIXED**: `detect_orphans` skips self-referential `parent_id` rows (no session is its own delegation); re-test added (`test_self_referential_parent_id_never_yields_a_self_orphan`) and passes |
| F2 | (1) orphan — a live-looking parent writes a forged MEANINGFUL-type part (`text`/`reasoning`/`tool`) after the spawn, rescuing a dead delegation | accepted limitation | the transcript is the model's own output channel; the sweep (like the p1 watchdog) cannot distinguish genuine progress from a forged-but-valid event. Residual risk: an ALIVE-but-deceptive parent can hide an un-reaped subagent — but a dead parent (the measured orphan) cannot write at all |
| F3 | (1) orphan — a never-terminating subagent (zombie) | accepted limitation | the design's orphan definition requires the subagent to have TERMINATED (completed or crashed-silent). A subagent still producing steps is "running" and is not reaped; the silent-zombie arm (no step-finish, silent past `crash_grace_s`) IS detected as `crashed` and reaped. Residual risk: a pathological subagent that emits steps forever without finishing runs on — that is a runaway-process/phase-watchdog matter, not an un-reaped-result matter |
| F4 | (2) relabel — tree-hash spoofing via a TRIVIAL delta (one file changed) | accepted limitation | the gate is an EXACT-tree identity check (the revamp2 measured case was byte-identical, `git diff f6fc35edf 20eeb801b` empty). A similarity heuristic would false-positive on legitimately divergent work (the campaign rejected it explicitly). Residual risk: a relabeler who also makes a one-line change evades RELABEL — documented, and the approvals-exclusion closes the cheap "bury it under an approval file" variant |
| F5 | (2) relabel — forged operator signature (any non-placeholder line) | accepted limitation | no PKI; the gate verifies the signature is NOT a placeholder (generic word / `<required: …>` template) but cannot verify WHO signed. Its real enforcement is the commit order (`present_at_pre_head` — an approval the phase itself commits never authorizes) and the exact tree+phase naming |
| F6 | (3) checkpoint — forged non-placeholder operator signature | accepted limitation | same no-PKI boundary as F5; the descendant-order check (`absent_at_checkpoint_commit` + `checkpoint_is_ancestor`) is the mechanical guarantee |
| F7 | (4) regression — existing campaigns/specs unaffected; runner + control-room surfaces green; merged gates still fire; (5) secrets/hashes | **PASS** | 128-test surface green (workflow_runner/supervise/control_room/dependency/spec-classification/spec-validation), full suite 2199 passed + 9 pre-existing skips, secrets scan clean |

## F1. Self-referential parent_id → spurious self-orphan — FIXED

- **Attack:** a session row whose `parent_id` equals its own `id` (malformed data — a top-level
  session's parent is NULL). Before the fix, a row with no meaningful part strictly after its own
  creation and a `step-finish` was flagged as an orphan of ITSELF (`parent == subagent == x`), a
  nonsense record poisoning the ledger.
- **Evidence:** the adversarial probe constructed `SessionRecord(id="x", parent_id="x")` with
  `step-start`+`step-finish` at its creation time → `detect_orphans` returned one orphan with
  `parent_session_id == subagent_session_id == "x"`.
- **Fix:** `detect_orphans` skips any subagent whose `parent_id == id` before the parent lookup
  (orphan_sweep.py) — a self-loop can never be a delegation.
- **Re-test:** `tests/test_orphan_sweep.py::test_self_referential_parent_id_never_yields_a_self_orphan`
  passes; the full orphan-sweep family (24 tests) passes.

## F2. Forged meaningful-type parent write rescues — accepted limitation

- **Attack:** a parent that, after delegating, writes a `text`/`reasoning`/`tool` part (types in
  `MEANINGFUL_STEP_TYPES`) — junk that is indistinguishable from genuine progress.
- **Evidence:** the probe appended a `text` part after the spawn of an otherwise-dead delegation
  → `flagged == 0` (the parent "rescued"). The non-meaningful heartbeat variant (`compaction`) is
  NOT rescued (`flagged == 1`).
- **Reasoning / residual risk:** the transcript is the model's own output channel; the sweep (and
  the p1 watchdog, which has the identical boundary) cannot tell genuine work from forged events.
  The measured orphan disease was a DEAD parent — a dead parent cannot write. An alive-but-
  deceptive parent is a different failure mode (a stalled parent), which the watchdog's
  meaningful-step clock bounds. Residual: a live parent that both produces meaningful-looking
  steps AND fails to reap a completed subagent hides the orphan until it stops writing.

## F3. Never-terminating subagent — accepted limitation

- **Attack:** a subagent that never writes `step-finish` and never goes silent (keeps producing
  steps) while its parent is dead — never reaped.
- **Evidence:** the probe: a subagent with continuous `reasoning` steps at `now-20s` →
  `flagged == 0` ("running"); a subagent with no steps for past `crash_grace_s` → `flagged == 1`,
  `terminated_reason == "crashed"` (reaped).
- **Reasoning / residual risk:** the orphan definition (design §Gap 1) requires the subagent to
  have TERMINATED — a produced-but-unreaped result. A still-productive subagent has no result to
  reap; it is "running" by construction. A runaway subagent that never terminates is a
  process-liveness problem (the phase watchdog / a process timeout), not the orphan pattern.
  Residual: a pathological subagent emitting steps forever while its parent is dead consumes
  compute until the operator or the watchdog intervenes.

## F4. Trivial-delta tree-hash spoofing — accepted limitation

- **Attack:** a relabeler re-commits the discarded tree plus ONE trivial change (e.g. a
  `docs/note.md`) — the tree hash differs, so the exact-match gate does not fire.
- **Evidence:** the probe: the revamp2 attempt-A tree recorded as discarded, then re-committed
  with `docs/note.md` added → tree `0477da66…` ≠ discarded `f22dbe99…` → `match == False`.
- **Reasoning / residual risk:** the gate is exact-tree identity because that is the measured
  case (revamp2's attempt A/B were byte-identical — `git diff f6fc35edf 20eeb801b` is empty) and
  because a similarity gate would churn false positives on legitimately divergent work. The cheap
  evasion vectors are closed: an EMPTY commit does not change the tree (F1/K4 below) and an
  approval-shaped commit is excluded from the identity (p2's approvals-exclusion). Residual: a
  deliberate one-line delta evades; the honest boundary is documented in the gate's own module
  docstring.

## F5 / F6. Forged operator signatures — accepted limitation

- **Attack:** any non-placeholder string on the `operator`/`SIGNED-BY-OPERATOR` line.
- **Evidence:** the placeholder set refuses generic words (`operator`, `your name`, `sign here`,
  `TODO`) and angle-bracketed templates (`<required: …>`, `<name>`), but `"gpt-5.6-terra"` /
  `"anyone"` pass the non-placeholder check.
- **Reasoning / residual risk:** no PKI — the gate cannot verify who signed. Its mechanical
  guarantees are the COMMIT ORDER (the checkpoint approval must be authored after the checkpoint
  commit; the tree-reuse approval must be committed before the phase) and the exact naming (tree
  hash + phase + spec path). A forged signature still cannot move the approval into the required
  commit position without a human writing to the repo.

## F7. Regression + usual suite — PASS

- **Evidence:** `pytest tests/test_workflow_runner.py tests/test_supervise.py
  tests/test_control_room_paths.py tests/test_dependency_direction.py
  tests/test_experiment_workflow_classification.py tests/test_experiment_spec.py -q
  --timeout=600` → 128 passed; the merged hardening's gates (watchdog, deploy, commit-prefix,
  tree gate, checkpoint) all still fire in their test families; the spec corpus (129 specs) loads
  with 0 validation errors; full suite 2199 passed, 9 skipped (the 9 pre-existing skips), zero
  new failures; ruff clean. The usual secrets/hashes/credentials scan of the new surface
  (orphan_sweep, orphan_ingestion, workflow_runner, orphan_sweep.py, record_discarded_tree.py,
  and the three new test files) finds no API keys, credentials, private keys, or hashed secrets.
