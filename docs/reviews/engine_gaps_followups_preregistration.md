---
status: accepted
kind: preregistration
spec: engine_gaps_followups
phase: g1_pin_spec
run: run-2d9c9c53be34
generated_at: 2026-09-02T17:10:38Z
---

# Preregistration — `engine_gaps_followups` (g1_pin_spec)

**The house pin convention.** This document is written BEFORE any implementation phase of the
wave executes (`g1_split_run_evidence`, `g1_verifier_mount`, `g1_revision_invalidation`,
`g1_parity_roundtrip`). Its purpose is twofold, and both halves are load-bearing:

1. **Anchor the run to exact bytes.** A workflow spec is a mutable file. Recording the spec's
   SHA256 makes the mandate immutable *by reference*: any divergence is detectable by re-running
   one command.
2. **Verify the defects, do not assert them.** The five defects this wave exists to close are
   stated as current-state claims in the spec's question/current_state (authored 2026-09-02),
   inherited from the Wave-1 adversarial review (`engine_gaps_verifier_revision_adversarial.md`
   F1-F4) plus the split-run evidence gap found at the merge (F5). This phase re-derives each
   claim against the ACTUAL code + the live control db at the pin and records the command that
   produced the evidence, so a reader can reproduce every finding without trusting this document.
   An edge that does not hold is a FAILED finding — recorded as a deviation below, never smoothed
   over.

The five defects are verified below against the state at launch.

---

## 1. The pin

| Field | Value |
|---|---|
| Spec path | `workflows/repository/engine_gaps_followups.yaml` |
| Spec **SHA256** | `9c45a76f81715f9e0214867ca8d1402dfd11a2cab1fd2ff409f2d110fa6fa940` |
| Spec size | 19,626 bytes |
| Worktree HEAD (git sha) | `ea9ca6a9a1d4f7bb9245238b0dd42a8c3aa885f5` |
| HEAD subject | `spec: engine_gaps_followups — close the Wave-1 adversarial limitations F1-F4 + the split-run defect F5` |
| Worktree | `/tmp/wt_followups2` — detached `HEAD` at the spec-commit tip |
| Main checkout | `/home/drseuss/ai-finops-framework` — branch `main`, SAME tree (`ea9ca6a9a`) |
| Working tree | clean except modified `run.log` (a runner artifact, not a source file) |
| Control run | `run-2d9c9c53be34` — `engine_gaps_followups`, `state: running`, started `2026-09-02T17:03:43Z` (this run) |
| Control db | `/home/drseuss/ai-finops-framework/experiments/results/control/control.db` (machine-local, gitignored), `schema_version: 3`, `control_epoch: 41` |
| Pinned at | 2026-09-02T17:10:38Z |

Reproduce the pin — these are the EXACT bytes the wave executes:

```bash
sha256sum workflows/repository/engine_gaps_followups.yaml
# 9c45a76f81715f9e0214867ca8d1402dfd11a2cab1fd2ff409f2d110fa6fa940
git rev-parse HEAD          # (in the worktree)
# ea9ca6a9a1d4f7bb9245238b0dd42a8c3aa885f5
```

If either value differs when `g2_adversarial` (or `g3_test_gate`) runs, the spec was edited
mid-run and the mandate this document pins is no longer the mandate being executed — a
reportable finding in itself.

**Spec shape at the pin** — seven phases (six `kind: agent` + one `kind: test`); no authored
`status:` (completion is derived from run evidence):

| # | Phase | kind | scope | notes |
|---|---|---|---|---|
| 0 | `g1_pin_spec` | agent | `implementation` | **this phase** — the preregistration |
| 1 | `g1_split_run_evidence` | agent | `implementation` | F5 — resume family link + union derivation |
| 2 | `g1_verifier_mount` | agent | `implementation` | F1 — the read-only verifier mount contract |
| 3 | `g1_revision_invalidation` | agent | `implementation` | F3/F4 — mid-list invalidation + no false-positive |
| 4 | `g1_parity_roundtrip` | agent | `implementation` | F2 — the container round-trip harness |
| 5 | `g2_adversarial` | agent | `adversarial_readonly` | independent pro reviewer (requires_deliverable) |
| 6 | `g3_test_gate` | test | `implementation` | the harness gate suite |

---

## 2. Verified current-state defects (the five edges)

Each edge is stated as the followups mandate states it, then **independently derived** against
the code at `ea9ca6a9a…` + the live control db. No finding was accepted on the spec's authority.

**Verdict legend.** **PASS** — the claimed edge holds at the pin, with code/command evidence.
**FAILED (deviation)** — the claimed edge does not hold as stated; the deviation is recorded and
the true state proven. In a pin phase, a FAILED sub-edge is not a wave failure — it is the
correction that makes the implementation phases target the real state.

### Defect 1 (f5) — the split-run evidence gap: `engine_gaps_verifier_revision` has n_runs 2, neither covering the full revision. **PASS**

The live shape, from the control db (read-only SELECT) + the two run ledgers:

```bash
# control db runs for engine_gaps_verifier_revision
SELECT run_id, spec_name, workflow_revision_id, candidate_sha, state,
       started_at, ended_at, ledger_path
FROM runs WHERE spec_name = 'engine_gaps_verifier_revision';
# run-85f33d68de3b  engine_gaps_verifier_revision  ''  ad7b73e63  failed      2026-09-02T14:10:16Z  2026-09-02T16:34:39Z
# run-45c2c18f97c8  engine_gaps_verifier_revision  ''  3c34c5bf4  promotable  2026-09-02T16:36:51Z  2026-09-02T16:50:56Z

# per-run step_attempts (the executed phases)
run-85f33d68de3b:  w1_pin_spec ok | w1_verifier_executor ok | w2_revision_identity failed
run-45c2c18f97c8:  w3_adversarial ok | w4_test_gate ok
```

The two ledgers (the resumed split the run in two):

```
experiments/results/workflows/engine_gaps_verifier_revision/20260902T163439Z.json
  spec_name=engine_gaps_verifier_revision  git_sha=ad7b73e63  state=failed    ok=false
  phases: w1_pin_spec ok, w1_verifier_executor ok, w2_revision_identity failed (timeout)
  keys with parent/family/run_id: []          # no family link field
experiments/results/workflows/engine_gaps_verifier_revision/20260902T165056Z.json
  spec_name=engine_gaps_verifier_revision  git_sha=3c34c5bf4  state=succeeded ok=true
  phases: w3_adversarial ok, w4_test_gate ok
  keys with parent/family/run_id: []          # no family link field
```

Neither run covers the full revision. The spec declares FIVE phases
(`w1_pin_spec`, `w1_verifier_executor`, `w2_revision_identity`, `w3_adversarial`,
`w4_test_gate` — `engine_gaps_verifier_revision.yaml:93-217`); run-85f33d68de3b executed three
(the last failed), run-45c2c18f97c8 executed two. No single run executed all five, yet the two
runs together did — and the spec index carries `n_runs: 2` (`experiments/specs/index.json`).
They are also two DIFFERENT candidates (`ad7b73e63` vs `3c34c5bf4`).

The machinery the followup (`g1_split_run_evidence`) is to build is entirely ABSENT at the pin:

```bash
# control db: no parent/family link column on runs
PRAGMA table_info(runs);
# run_id, spec_name, workflow_revision_id, candidate_sha, state, model,
# started_at, ended_at, ledger_path, cost_usd          -- NO parent_run_id / family_id
grep -n "parent_run_id\|family_id" src/agentic_dynamics/control/control_db.py   # zero hits
grep -n "def create_run" src/agentic_dynamics/control/control_db.py             # :1428 — no parent param
grep -n "parent_run\|family" src/agentic_dynamics/runtime/workflow_runner.py    # only checkpoint/fork prose
```

`create_run` (`control_db.py:1428-1483`) accepts no parent/family argument and the `runs` table
has no such column — a `--resume` continuation is recorded as a brand-new, UNLINKED run (that is
precisely what produced the two rows above). `derive_status` (`spec_status.py:451-552`) consumes
a flat `certifying` list with no family-union concept.

*Nuance (not a deviation of this claim):* the F5 guard-half landed immediately in `5a2aeb2ee`
("a failed certifying run blocks completion") — a certifying FAILED member now forces
`derive_status` to `failed` (the live index reads `engine_gaps_verifier_revision: failed`,
`n_runs 2`), so the index no longer lies *completed* for THIS live shape. But that guard is a
partial mitigation, not the defect's closure: a resume is still an unlinked second run, the
family-union derivation does not exist, and the guard cannot tell a genuine fresh full-coverage
run from a split — it merely blocks on any-failed-member. The preregistered defect — two runs,
neither covering the full revision, no family link anywhere in the control db or the ledgers —
holds exactly as stated. (D-1 records the guard's landing so the split-run phase targets the
right residual.)

### Defect 2 (f1) — `build_verifier_request` keeps `/tmp` and `.git` rw: the verifier container is not literally read-only. **PASS**

Read the mount contract, then the verifier request builder, then dump a REAL verifier request:

```bash
# the contract-fixed mount map
sed -n '124,149p' scripts/fleet/spawn_wrapper.py     # CONTRACT_TARGETS
# /tmp:            ("worktree",   "rw")    -- the shared worktree namespace
# /repo:           ("repo",       "ro")
# /repo/.git:      ("repo-git",   "rw")
# <repo-home>:     ("repo-alias", "ro")    -- repo at its HOST path (D-16)
# <repo-home>/.git:("repo-alias-git", "rw")
```

`build_verifier_request` (`spawn_wrapper.py:864-930`) starts from `build_phase_request` — whose
mount list (`:784-798`) hard-codes `/tmp` rw, `/repo/.git` rw, and the host-path `.git` rw — then
filters ONLY the forbidden surface (`:914-930`): the CLI-state namespace, the credential
file/dirs, the results mount, and the write-flag env. **It never flips a mount mode to `ro`.** So
the verifier request retains `/tmp` (the candidate worktree namespace) and the `.git` dirs rw.

Empirical confirmation — dump the mount list a real `DockerVerifierExecutor.build_request`
produces (no docker, no model — a pure function call):

```
=== VERIFIER REQUEST MOUNTS (real DockerVerifierExecutor.build_request) ===
  target=/tmp                     mode=rw        # <-- candidate worktree namespace, RW
  target=/repo                    mode=ro
  target=/repo/.git               mode=rw        # <-- git dir, RW
  target=/tmp/wt_followups2       mode=ro        # repo-alias
  target=/tmp/wt_followups2/.git  mode=rw        # <-- host-path git dir, RW
child cmd: python3 scripts/run_workflow.py --spec ... --only-phase gate_run
           --timeout 180 --no-commit
```

The candidate's writable surfaces are the `/tmp` worktree namespace (where the suite's workdir
`/tmp/wt_x` lives) and the git dirs. Write protection on the candidate is **behavioral** — the
child runs with `--no-commit` (`docker_verifier_executor.py:92-94`; the parity test asserts the
flag at `test_workflow_executor_parity.py:581`) — never enforced by the mount contract at
validation time. That is exactly the F1 defect: a verifier that can write the candidate it
verifies can be coerced, and today the mount allows it.

### Defect 3 (f2) — the parity tests use a fake verifier; the real `execute → spawn → envelope → classify` round-trip is unexercised. **PASS**

```bash
grep -n "FakeDockerVerifier\|DockerVerifierExecutor\|\.execute(\|run-docker" \
  tests/test_workflow_executor_parity.py
```

Evidence:

```
:187  class FakeDockerVerifier(StepExecutor):   # "NO docker: it runs the suite locally"
:201  def execute(self, request): ... run_suite(...)   # local run_suite, no container
:287/:462/:492   verifier = FakeDockerVerifier()       # injected into run_workflow(...)
:421/:429        verifier_executor=FakeDockerVerifier()
:538  executor = DockerVerifierExecutor(...)            # the ONLY real-executor test
:557  req = executor.build_request(request)             # ... and it calls build_request ONLY
```

The parity suite injects `FakeDockerVerifier` (a local `run_suite` shape, `:187-218`) into the
engine for the parent-state parity cases. The one test that constructs the REAL
`DockerVerifierExecutor` (`test_verifier_request_carries_no_credentials_and_no_writable_state`,
`:533-582`) asserts `build_request` only — the request's mount/env/command surface. Nobody calls
the real executor's `execute()` (`docker_verifier_executor.py:111-160`), so the genuine container
contract — `execute → spawn_sibling → child envelope → _classify → _phase_from_envelope →
StepResult` — is never exercised. There is no `--run-docker` marker anywhere in the test file
(grep: zero hits). `docker` is unavailable in CI, so the round-trip is unmeasured — F2 exactly.

### Defect 4 (f3) — a mid-list structural edit (phase renamed, same count) still certifies `completed` for a legacy green run. **PASS**

Read `_is_definition_changed_after_runs` (`spec_status.py:390-419`), then reproduce with the
real function:

```python
spec_phases = _spec_phase_names(spec)          # current definition, workflow order
has_green  = any(run.ok is True for run in runs)
executed   = union of run.executed_phases      # names the runs actually executed
n = len(executed)
if n <= 0 or n >= len(spec_phases):            # <-- SAME-COUNT renames never reach the check
    return False
return executed == set(spec_phases[:n])        # only the trailing-append shape fires
```

The `n >= len(spec_phases)` early return means any run (or corpus) whose executed-phase count
equals the current spec's count — regardless of whether the NAMES still match by position —
short-circuits to "not changed". A mid-list rename with the same count is therefore invisible.
Reproduction against the real function (spec `[w1_pin_spec, w2_new_name, w3_adversarial]`;
legacy green run — no digest — that executed `[w1_pin_spec, w2_revision_identity,
w3_adversarial]`, i.e. w2 was renamed mid-list):

```
=== f3: mid-list rename, legacy green run (same count, no digest) ===
  spec phases: ['w1_pin_spec', 'w2_new_name', 'w3_adversarial']
  run executed: ['w1_pin_spec', 'w2_revision_identity', 'w3_adversarial'] ok: True wid: ''
  _is_definition_changed_after_runs: False
  certifying: 1 changed: False
  derive_status: completed          # <-- the f3 failure mode: a renamed definition reads completed
```

`derive_status` → `completed` for a definition whose w2 phase no longer exists under the name the
run executed. F3 confirmed. The full parity suite passes at the pin
(`pytest tests/test_workflow_executor_parity.py tests/test_spec_status.py -q` → 81 passed), i.e.
the current tests *encode* this blind spot, not catch it.

### Defect 5 (f4) — the partial-run false-positive: `_is_definition_changed_after_runs` over-fires on a partial-run corpus with no actual edit. **PASS**

Same function, the false-positive side. A legacy corpus of partial runs whose executed-phase
union is a strict prefix of the current list (e.g. a `--only-phase p1` run over a `p1..p5`
definition) satisfies `executed == set(spec_phases[:n])` with `n < len(spec_phases)` — the
trailing-append detector fires even though NO phase was ever added or edited; the runs are simply
partial. Reproduction against the real function (spec `[p1,p2,p3,p4,p5]`; one green legacy run
that executed only `{p1}`):

```
=== f4: partial-run corpus, NO edit (p1-only run over p1..p5) ===
  spec phases: ['p1', 'p2', 'p3', 'p4', 'p5']
  run executed: {p1}, ok: True, no digest
  _is_definition_changed_after_runs: True        # <-- false positive: "edited"
  certifying: 0 changed: True
  derive_status: runnable          # "never-run-of-this-revision" -- no edit actually occurred
```

A partial-run corpus with no edit reads as `runnable`/definition-changed (`changed=True`,
`certifying=[]`) instead of its own honest partial state — the F4 failure mode. The spec's
`g1_revision_invalidation` phase must distinguish "these runs executed phases that exist in the
current definition, in order — just not all of them" (partial, not edited) from a genuine
mid-list structural edit (the F3 side). F4 confirmed.

---

## 3. Verdict summary

| # | Mandate edge (as stated) | Status at the pin |
|---|---|---|
| 1 | f5 — `engine_gaps_verifier_revision` has n_runs 2, neither covering the full revision | **PASS** — control db: `run-85f33d68de3b` (failed; executed w1_pin_spec + w1_verifier_executor + w2_revision_identity, the last failed) + `run-45c2c18f97c8` (promotable; executed w3_adversarial + w4_test_gate) — disjoint phase sets over the 5-phase spec, two candidates, no family link field in either ledger; `runs` table has no parent/family column; `create_run` takes no parent param |
| 2 | f1 — `build_verifier_request` keeps `/tmp` and `.git` rw | **PASS** — real-request dump: `/tmp` rw, `/repo/.git` rw, host-path `.git` rw; protection is behavioral (`--no-commit`), never the mount contract |
| 3 | f2 — parity tests use a fake verifier | **PASS** — `FakeDockerVerifier` injected at `:287/:462/:492`; the real executor is only `build_request`-asserted (`:557`); no `execute()` call, no `--run-docker` marker |
| 4 | f3 — a mid-list rename still certifies completed | **PASS** — reproduced: `_is_definition_changed_after_runs` → False for a same-count rename, `derive_status` → completed; the `n >= len(spec_phases)` early return (`:417`) is the blind spot |
| 5 | f4 — the partial-run false-positive shape | **PASS** — reproduced: a `{p1}`-only corpus over `p1..p5` fires the detector (`changed=True`, `derive_status` → runnable) with no edit; `executed == set(spec_phases[:n])` cannot tell partial from appended |

**Pin verdict: all five defects are CONFIRMED against the actual code and the live control db —
each with code + command + (where live) db evidence, none asserted.** The live split-run shape
(`engine_gaps_verifier_revision`: n_runs 2, two candidates, neither full-coverage, no family
link) is the F5 mandate's ground truth; the `/tmp`+`.git` rw mounts and the `--no-commit`
behavioral guard are the F1 mandate's; the fake-verifier parity suite is the F2 mandate's; and
the two sides of `_is_definition_changed_after_runs` (`:417` early-return blindness + the
prefix-shape over-fire) are the F3 and F4 mandates'. The five findings above are the baseline
the implementation phases (`g1_split_run_evidence`, `g1_verifier_mount`,
`g1_revision_invalidation`, `g1_parity_roundtrip`) and the adversarial review (`g2_adversarial`)
will be measured against.

---

## 4. Deviations recorded against the pinned bytes / mandate

Recorded per the D-series convention. Each deviation is a correction to the spec's stated
baseline that the implementation phases should consume; none changes the wave's work items.

**D-1 — the F5 guard-half already landed in `5a2aeb2ee`, so the live index reads `failed`, not
`completed`, for `engine_gaps_verifier_revision`.** The spec's `current_state`/question prose
describes the pre-guard lie ("n_runs 2, status completed"). Between the adversarial review and
this pin, commit `5a2aeb2ee` ("a failed certifying run blocks completion") added
`spec_status.py:534-535` — `if any(run.ok is False and not run.awaiting for run in certifying):
return "failed"` — so the CURRENT live index honestly reads `failed`. The preregistered f5
DEFECT still holds (two runs, neither covering the full revision, no family link, no union
derivation — verified above); what changed is the index's immediate verdict on the one live
shape the guard happens to cover. `g1_split_run_evidence` should treat the guard as the partial
mitigation it is: its union/family machinery must replace the blunt any-failed-member block, and
the guard's own tests (`tests/test_spec_status.py`'s updated "later failed re-run must not
un-complete" cases) are the shape the family derivation must preserve while fixing the unlinked-
second-run blind spot.

**D-2 — the spec's code anchors are `spawn_wrapper.py` / `spec_status.py`, not
`docker_executor.py` for the f1 mount.** The spec's `domain_context` names
`scripts/fleet/docker_executor.py` as holding `DockerVerifierExecutor + build_verifier_request`.
`build_verifier_request` actually lives in `scripts/fleet/spawn_wrapper.py:864` (with the
`CONTRACT_TARGETS` mount map at `:127-149`); `docker_verifier_executor.py` is the executor that
calls it (`:102`). The f1 verification above was performed at the real sites
(`spawn_wrapper.py` + the executor's `build_request`). `g1_verifier_mount` should edit
`spawn_wrapper.py`'s builder + contract map (or add the validation alongside them), not
`docker_executor.py`.

---

## 5. Scope compliance

The phase mandate (g1_pin_spec prompt): write this preregistration carrying the pin + the five
defects verified against the actual code + the live control db, then commit with the
`[workflow] g1_pin_spec — <goal prefix>` subject.

- **Created:** `docs/reviews/engine_gaps_followups_preregistration.md` (this file) — the wave's
  pin, in the `/tmp/wt_followups2` worktree at the spec-commit tip.
- **Edited:** nothing else. Every verification above is read-only — `sha256sum`, `git rev-parse`,
  `grep`/`sed` reads, read-only `sqlite3` SELECTs against the live control db, a pure-function
  mount dump of the real `DockerVerifierExecutor.build_request` (no docker daemon, no model
  call, no credentials), and in-process reproductions of `_is_definition_changed_after_runs` /
  `derive_status` against real `load_spec` + `RunSummary` objects in a throwaway temp dir
  (nothing written under the repo).
- **Not done, deliberately:** the spec's prose was left as authored — repairing its current_state
  would edit the very spec whose SHA256 this document pins. The `run.log` modification in the
  working tree is a runner artifact, untouched and unstaged.

---

## 6. Verdict

All five preregistered defects are **PASS — verified against the actual code and the live control
db**, each with reproducible evidence (the f5 shape from the control db + both ledgers; the f1
mounts from a real request dump; the f2 fake from the parity suite; the f3/f4 derivations from
the real `_is_definition_changed_after_runs`). No claim required more than one reproduction
attempt; none deviated from its stated edge (D-1 is a partial mitigation that landed after the
review and narrows — but does not close — the f5 defect; D-2 is an anchor correction). The five
findings are the measured baseline for `g1_split_run_evidence`, `g1_verifier_mount`,
`g1_revision_invalidation`, and `g1_parity_roundtrip`, and for the independent pro adversarial
review (`g2_adversarial`) that falsifies this wave rather than certifying it.

The mandate is anchored: spec SHA256
`9c45a76f81715f9e0214867ca8d1402dfd11a2cab1fd2ff409f2d110fa6fa940` at git
`ea9ca6a9a1d4f7bb9245238b0dd42a8c3aa885f5`, run `run-2d9c9c53be34`. `g1_split_run_evidence`
(implementation) may proceed.
