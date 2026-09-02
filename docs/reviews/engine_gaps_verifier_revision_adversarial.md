---
status: accepted
kind: adversarial-review
spec: engine_gaps_verifier_revision
phase: w3_adversarial
run: run-85f33d68de3b
reviewer: deepseek/deepseek-v4-pro (independent — different model + session from the flash author)
generated_at: 2026-09-02T16:20:00Z
---

# Adversarial review — `engine_gaps_verifier_revision` (w3_adversarial)

**Role.** This is the INDEPENDENT adversarial pass over the wave. I am a different model
and session from the flash author, per the house independence convention. I falsify, I do
not certify. Every claim below was re-derived against the actual code at the wave tip
(`b4a7e6486`), never asserted from the preregistration or the author's prose.

**Method.** The three attack axes of the phase mandate, in order, each re-verified with a
command or a live probe rather than a doc read:

1. **w1** — can a `kind:test` phase still be skipped in any path? does a failing suite
   block the run in both the in-process and verifier paths (parity *measured*, not
   claimed)? does the verifier container really carry no credentials and no writable state?
2. **w2** — does authored status STILL win anywhere (every derive path grepped)? does
   editing a spec really invalidate completion from earlier revisions (append-a-gate
   probe + regeneration)? is the digest stable across cosmetic edits?
3. **cross** — did either change break the control-db evidence or the parity suite?

Every finding is **FIX** on the branch or **RECORD** (accepted limitation with reasoning).
This review records four accepted limitations and otherwise a clean sweep with
re-verification evidence (never a bare PASS).

---

## 1. Attack w1 — the `DockerVerifierExecutor` and the dispatch

### 1a. Can a `kind:test` phase still be skipped in ANY path? — **NO (clean)**

The engine's `kind == "test"` branch (`workflow_runner.py:3059-3118`) is a closed
three-way dispatch; there is no fourth branch and no fall-through that drops the phase:

| Path | Condition | Outcome for a `kind:test` phase |
|---|---|---|
| verifier dispatch | `verifier_executor is not None` (`:3079`) | `verifier_executor.execute(...)` → `_apply_verifier_verdict` (`:954`) |
| containerized refusal | `containerized_path` (`:2897`, = `step_executor is not None`) | `pr.status="failed"`, `pr.error=VERIFIER_REFUSED…` (`:3099-3105`) |
| in-process | otherwise | `run_suite(...)` → verdict (`:3106-3118`) |

The refusal marker is a failed *phase*, not a skip: it lands on the ledger (`status:
failed`, `error: VERIFIER_REFUSED…`) and blocks the run exactly like a failing suite.
Verified two ways:

- `test_container_path_without_verifier_refuses_loudly` asserts `len(result.phases)==1`
  (the phase is *on* the ledger), `test_executed_success is None` (the passing suite did
  NOT secretly pass), and the agent executor was never handed the step.
- A `DockerVerifierExecutor.execute` handed a non-`kind:test` step returns
  `StepResult(ok=False, state="refused", exit_code=20)` (`docker_verifier_executor.py:118-127`)
  — a loud refusal, never a pass and never a skip.

The only way a test phase does not run is operator scope (`--only-phase` selecting a
different phase, or `stop_on_error` after an earlier failure) — not a silent engine skip.

### 1b. Does a failing suite block the run in BOTH paths? — **YES, parity measured**

`test_failing_suite_fails_phase_and_blocks_run_in_both_paths` runs the *same* failing
`pytest` target through the default (in-process `run_suite`) path and through a
`FakeDockerVerifier` (a `DockerVerifier`-shaped executor that runs the same `run_suite`
with the same `tests` target and returns the verdict on the same `StepResult` fields),
and asserts the parent sees an **identical phase outline** in both shapes:

```python
assert [_phase_outline(p) for p in local.phases] == [_phase_outline(p) for p in docker.phases]
# (phase, kind, status, test_executed_success, tests_passed, tests_total)
```

with `local.ok is False`, `docker.ok is False`, both `state == "failed"`, both
`phases[0].test_executed_success is False`. The passing-suite counterpart
(`test_passing_suite_records_success_in_both_paths`) asserts the same equality with
`test_executed_success is True`, `tests_passed==1`, `tests_total==1`. This is parity
*measured* over the two execution shapes, not asserted. The empty-suite corner is also
parity-tested (`test_success_parity_local_vs_executor`): both shapes record
`test_executed_success=False` with the phase not failed — the in-process "failed/errors==0
is not a phase failure" rule and the executor's `ok`/`test_executed_success` split agree.

**RECORD F2 (below)** is the one honest caveat: the *true* container round-trip (real
`docker` spawn → child envelope → `_classify` → `_phase_from_envelope`) is not exercised
end-to-end; the parity above is measured at the engine dispatch + verdict-application seam
with a verifier-shaped executor, because `docker` is unavailable in the test environment.

### 1c. Does the verifier container really carry no credentials and no writable state? — **YES for credentials and CLI-state; PARTIAL for writable mounts (F1)**

`build_verifier_request` (`spawn_wrapper.py:864-930`) starts from `build_phase_request`
and removes, by construction:

- the D-2 auth directory mounts and the `/auth/opencode_auth.json` credential file mount
  (`forbidden_mount_targets = {STATE_TARGET, AUTH_CRED_FILE, *AUTH_DIRS}`);
- the per-attempt CLI-state namespace (`/state`) and the `XDG_*` /
  `FINOPS_OPENCODE_STATE_DIR` redirect env;
- the `/app/experiments/results` results mount; and
- every write-flag env (`FINOPS_KB_WRITE` / `FINOPS_ACTUATION_ARMED`).

`test_verifier_request_carries_no_credentials_and_no_writable_state` asserts all of the
above, plus that `/repo` mounts `ro`, the child command carries `--only-phase <name>` and
`--no-commit`, and no `FINOPS_ADMISSION_*` block is present. The remaining write surfaces
are the contract-fixed `/tmp` worktree namespace and the `repo-git` dirs — see **F1**.

---

## 2. Attack w2 — revision identity and the authored-status demotion

### 2a. Does authored status STILL win anywhere? — **NO over run evidence**

Grepped every consumer of the derived status and every path in `derive_status`. The only
places an authored `status:` surfaces as the *effective* status are three, all deliberate
and all documented in the `derive_status` docstring:

- `derive_status` returns `spec.status` **only** for `draft`/`tombstoned`
  (`spec_status.py:507-508`) — human-only lifecycle claims, by design;
- a **repeatable** spec returns `spec.status or "runnable"` (`:517`) — repeatable specs
  never derive from runs, so authored status is the only signal (unchanged semantics);
- a non-repeatable workflow with **no run ledgers at all** returns `spec.status or
  "runnable"` (`:542`) — the authored claim is the only record, and `build_entry` carries
  it as the explicit `authored_status` marker (`:592`) rather than silently overriding
  evidence.

For a non-repeatable workflow **with** run evidence, the derived status comes exclusively
from `_runs_of_current_revision` (`:422`), which filters runs to those whose recorded
`workflow_revision_id` equals the current digest — authored `status:` is never consulted.
The fact-plane reducer (`control/reducers/spec_status.py:174`) and the KB spec ingestion
(`knowledge/spec_ingestion.py:294`) both read `entry.status` (derived), not the authored
value. The live proof: the regenerated index reports `fleet_job_submission`
`status: runnable`, `authored_status: completed`, `latest_ok: null`, `n_runs: 3` — the
deep review's "completed with a never-run gate" failure mode is dead.

### 2b. Does editing a spec really invalidate completion from earlier revisions? — **YES for post-w2 runs; PROSPECTIVE-ONLY for the legacy corpus (F3, F4)**

Live probes (append-a-gate on `fleet_job_submission` + a synthetic corpus):

- append a `p99_neverrun_gate` → digest changes (`True`);
- a legacy green run (no digest) recording `p1..p5` of the pre-gate spec → the edited
  spec derives `runnable` (never-run-of-this-revision), with `authored_status=completed`
  still visible as a marker.
- A post-w2 run carrying the older digest does **not** certify the edited spec; only a
  run of the new digest does (`test_edited_spec_shows_its_own_revision_run_state`,
  `test_gate_added_after_completed_shows_never_run_of_this_revision`).

The exact guarantee holds only where a digest was recorded. See **F3**/**F4** for the
legacy boundary.

### 2c. Is the digest stable across cosmetic edits? — **YES (verified both directions)**

Live probe on the real corpus spec `engine_gaps_verifier_revision.yaml`:

| Edit | Digest changes? | Expected |
|---|---|---|
| cosmetic comment/whitespace | `False` | no |
| append a gate (structural) | `True` | yes |
| rename a phase (structural) | `True` | yes |
| edit a `kind:test` phase's `tests:` target | `True` | yes |
| edit a phase `prompt` | `True` | yes |
| bump `version` | `True` | yes |
| edit `status:` (volatile) | `False` | no |

`compute_workflow_revision_id` (`experiment_spec.py:266`) hashes a sorted, compact JSON of
`to_dict()` minus `REVISION_VOLATILE_KEYS` (`status`, `supersedes`, `superseded_by`,
`completed_at`, `last_run_at`, `results_pointer`, `git_sha`, `pricing_version`,
`generated_at`) — so comments/whitespace/key-order vanish at parse/sort, and lifecycle
prose never re-keys a revision. `workflow_revision_id` is also recorded on the run ledger
(`WorkflowRunResult.to_dict`, `workflow_runner.py:442`) and on the control-db run
(`scripts/run_workflow.py:839-843` → `control_db.create_run`'s `workflow_revision_id`
column, `control_db.py:1433`/`:1467`).

---

## 3. Attack cross — control-db evidence and the parity suite

- **Control-db evidence intact.** `create_run` already declared `workflow_revision_id`
  (`control_db.py:1433`) and the wave now populates it (`scripts/run_workflow.py:839-843`);
  the `runs` INSERT (`:1467/1471`) and the control packet echo (`control_status.py:350`)
  were already wired. `test_control_status.py` and `test_control_db.py` pass.
- **Parity suite intact and extended.** `test_workflow_executor_parity.py` grew from 18 to
  22 tests, all passing; the pre-existing parity cases were updated to inject a verifier
  and still assert the same phase outlines.
- **The full w4_test_gate set is green** (re-run here):
  `test_workflow_executor_parity` (22), `test_workflow_runner` (with the control families,
  213), `test_spec_status` + `test_experiment_spec` (108), `test_compile_experiment` +
  `test_spawn_wrapper` + `test_doc_lifecycle` + `test_script_classification` +
  `test_agent_config_render` + `test_cli_resolution` (215). `ruff check` on every changed
  source file: clean.

No cross-breakage found.

---

## 4. Finding table

| # | Axis | Finding | Disposition | Severity |
|---|---|---|---|---|
| F1 | w1 | The verifier container is **not literally read-only**: `build_verifier_request` removes credentials, the CLI-state namespace, the results mount, and write flags, but retains the contract-fixed `/tmp` worktree namespace (`rw`) and the `repo-git` dirs (`/repo/.git`, repo-alias `.git`, both `rw`). Write protection on the candidate/git is **behavioral** (`--no-commit`), not enforced by the mount contract. | **RECORD** (accepted) | low |
| F2 | w1 | True container round-trip parity is **not end-to-end measured**: the parity tests use a `FakeDockerVerifier` (local `run_suite`); only `build_request` is asserted on the real `DockerVerifierExecutor`. `execute → spawn_sibling → child envelope → _classify → _phase_from_envelope` is unexercised (`docker` unavailable in CI). | **RECORD** (accepted) | medium |
| F3 | w2 | Revision invalidation is **prospective-only** for the legacy corpus. Pre-w2 ledgers carry no digest; `_is_definition_changed_after_runs` (`spec_status.py:390`) detects only the trailing-append shape. Verified: a legacy green run still certifies `completed` after a **mid-list** structural edit (phase renamed, same count). | **RECORD** (accepted) | medium |
| F4 | w2 | `_is_definition_changed_after_runs` can **false-positive** when the only legacy ledgers are partial runs whose executed-phase union equals a strict prefix of the current phase list (e.g. a corpus of `--only-phase p1` runs over `p1..p5`), marking the spec "never-run-of-this-revision" with no actual edit. | **RECORD** (accepted) | low |

**F1 reasoning.** The retained `rw` mounts are required for a git-worktree test run (the
`/tmp` namespace holds the candidate worktree; the `.git` dirs must be writable for the
worktree's `gitdir:` pointer to resolve — the same D-16 fix documented in
`spawn_wrapper.py`). The verifier is strictly *less* privileged than the agent cell (no
credentials, no CLI state, no results write, no write flags) and no more privileged than
the in-process path, which by definition writes the same surface. The `--no-commit` flag
makes the contract-fixed rw git dirs read-only in practice. The imprecision is in the
word "READ-ONLY": it is exact for the credential/state/results surface, not for every
mount mode. No fix is warranted without a mount-contract change that would break the
git-worktree invocation the verifier must run.

**F2 reasoning.** The parent-state parity that matters (does a failing suite fail the
phase and block the run identically in both shapes) *is* measured — at the engine's
dispatch + `_apply_verifier_verdict` seam. The one untested link is the docker
spawn/envelope classification, which is byte-identical to `DockerAgentExecutor`'s already
proven `_classify`/`_phase_from_envelope` (`docker_executor.py:136-173`) and the P0-1
exit-code contract. A CI runner with docker would close this; none is available here, and
fabricating one would violate "never assert".

**F3/F4 reasoning.** The legacy corpus never recorded a revision digest, so exact
invalidation is impossible for it by definition. `_is_definition_changed_after_runs` is a
conservative phase-coverage heuristic: it catches the one shape the deep review actually
found (`fleet_job_submission`'s appended `p6_test_gate`), and its trailing-append
restriction deliberately avoids misreading a resumed/failed run as an edit. F3 is the
false-negative side of that conservatism (a mid-list edit evades it for legacy runs
only); F4 is the false-positive side (a partial-run-only legacy corpus reads as edited).
Both are bounded to pre-w2 ledgers and both are documented in the docstrings; post-w2
runs carry the digest and are exact in both directions.

**Clean sweep otherwise (with re-verification evidence).** w1: no skip path exists
(three-way dispatch, `:3059-3118`); failing/passing suite parity measured and equal
(`test_workflow_executor_parity.py`); credentials + CLI-state + results + write flags all
absent from the verifier request (`test_...no_credentials...`). w2: authored `status:`
no longer overrides run evidence (`derive_status` grep + live `fleet_job_submission`
`runnable`/`authored_status=completed`); digest stable across cosmetic edits and moved by
structural edits (live probe, both directions). cross: control-db column populated, all
w4-gate suites green, ruff clean.

---

## 5. Release verdict

**MERGE-READY — PASS.** Both engine gaps are closed as specified: the reference
containerized path gains a real `kind:test` verification (fail-closed dispatch, no skip,
parity with in-process), and completion follows the revision digest while authored
`status:` is demoted to an explicit `authored_status` marker. The four recorded items are
accepted limitations with reasoning — none is a defect that blocks the merge, and none
silently violates a hard rule. The load-bearing guarantees (no skip; parity measured;
authored status dead over evidence; digest stable/structural) each re-verified with code
or live-probe evidence above.

### P0 actions after merge (named, NOT done — the controller alone)

1. **Merge the `wt_wave1` worktree branch into `main`** — the permanence gate; every
   `wt_*` branch is an ephemeral proposal until the controller signs it.
2. **Regenerate the spec-lifecycle index at the MAIN checkout** (`python
   scripts/spec_status.py`) before relying on `experiments/specs/index.json`/`STATUS.md`.
   The committed index was derived from the worktree, whose `experiments/results/` view is
   partial (it shows `engine_gaps_verifier_revision` at `n_runs: 0` because this wave's own
   run ledgers live in main's untracked results dir). The authoritative counts only exist
   after regenerating where the ledgers are.
3. **Deploy the website to BOTH Firebase projects** (`ai-finops-rulebook` canonical and
   `agentic-dynamics` mirror — from `apps/website/`, `firebase deploy --only hosting` then
   `--project agentic-dynamics`), since `apps/website/data.js` changed with the regenerated
   lifecycle counts. Never let the two hosts drift.

Post-merge P1 (any actor, within lease — not a P0 gate): regenerate any other derived
surfaces via `agentic-dynamics surfaces sync` if the branch touched their sources (this
wave did not touch `agent_config/`).

---

## 6. Verdict log

| Axis | Verdict |
|---|---|
| w1 — no skip in any path | PASS (three-way dispatch, refusal is a failed phase not a skip) |
| w1 — failing suite blocks both paths | PASS (parity measured, identical phase outlines) |
| w1 — verifier carries no credentials / no writable CLI-state | PASS for credentials+state; PARTIAL for mounts → F1 |
| w2 — authored status no longer wins | PASS (grep + live `fleet_job_submission`) |
| w2 — editing invalidates completion | PASS for post-w2; PROSPECTIVE-ONLY for legacy → F3/F4 |
| w2 — digest stable across cosmetic edits | PASS (both directions verified) |
| cross — control-db evidence + parity suite | PASS (column populated; suites green; ruff clean) |
| **Overall** | **PASS — merge-ready** (4 accepted limitations recorded) |
