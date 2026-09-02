---
status: accepted
kind: preregistration
spec: engine_gaps_verifier_revision
phase: w1_pin_spec
run: run-85f33d68de3b
generated_at: 2026-09-02T14:18:35Z
---

# Preregistration — `engine_gaps_verifier_revision` (w1_pin_spec)

**The house pin convention.** This document is written BEFORE any implementation phase
(`w1_verifier_executor`, `w2_revision_identity`) of the wave executes. Its purpose is twofold,
and both halves are load-bearing:

1. **Anchor the run to exact bytes.** A workflow spec is a mutable file. Recording the spec's
   SHA256 makes the mandate immutable *by reference*: any divergence is detectable by re-running
   one command.
2. **Verify the premises, do not assert them.** The two gaps this wave exists to close are
   stated as current-state claims in the spec's question/current_state (authored 2026-09-02,
   measured by the deep review that left criteria 3 + 10 open). This phase re-derives each claim
   against the ACTUAL code at the pin and records the command that produced the evidence, so a
   reader can reproduce every finding without trusting this document. An edge that does not hold
   is a FAILED finding — recorded as a deviation below, never smoothed over.

The two gaps, as the wave states them, are verified below against the state at launch.

---

## 1. The pin

| Field | Value |
|---|---|
| Spec path | `workflows/repository/engine_gaps_verifier_revision.yaml` |
| Spec **SHA256** | `78ad597f6175a822f23c1e2b439aa134205e2d1065b72fd9837ef39999094d4a` |
| Spec size | 16,410 bytes |
| Worktree HEAD (git sha) | `a1081d51a236c5e844b5bfeb9ba588921484fef0` |
| HEAD subject | `spec: engine_gaps_verifier_revision — Wave 1 (deep-review criteria 3 + 10)` |
| Worktree | `/tmp/wt_wave1` — detached `HEAD` at the spec-commit tip |
| Main checkout | `/home/drseuss/ai-finops-framework` — branch `main`, SAME tree (`a1081d51a`) |
| Working tree | clean except modified `run.log` (a runner artifact, not a source file) |
| Control run | `run-85f33d68de3b` — `engine_gaps_verifier_revision`, `state: running`, started `2026-09-02T14:10:16Z`, heartbeat live (beat 17, `orchestrator`) |
| Control db | `/home/drseuss/ai-finops-framework/experiments/results/control/control.db` (machine-local, gitignored), `schema_version: 3`, `control_epoch: 27` |
| Pinned at | 2026-09-02T14:18:35Z |

Reproduce the pin — these are the EXACT bytes the wave executes:

```bash
sha256sum workflows/repository/engine_gaps_verifier_revision.yaml
# 78ad597f6175a822f23c1e2b439aa134205e2d1065b72fd9837ef39999094d4a
git rev-parse HEAD          # (in the worktree)
# a1081d51a236c5e844b5bfeb9ba588921484fef0
```

If either value differs when `w3_adversarial` (or `w4_test_gate`) runs, the spec was edited
mid-run and the mandate this document pins is no longer the mandate being executed — a
reportable finding in itself.

**Spec shape at the pin** — five phases (four `kind: agent` + one `kind: test`); no authored
`status:` (the P2-1 "completion is derived" principle):

| # | Phase | kind | scope | notes |
|---|---|---|---|---|
| 0 | `w1_pin_spec` | agent | `implementation` | **this phase** — the preregistration |
| 1 | `w1_verifier_executor` | agent | `implementation` | the `DockerVerifierExecutor` + dispatch |
| 2 | `w2_revision_identity` | agent | `implementation` | the canonicalized revision digest + `derive_status` fix |
| 3 | `w3_adversarial` | agent | `adversarial_readonly` | independent pro reviewer (requires_deliverable) |
| 4 | `w4_test_gate` | test | `implementation` | the harness gate suite |

---

## 2. Verified current-state edges (the two gaps)

Each edge is stated as the spec's w1/w2 mandate states it, then **independently derived** against
the code at `a1081d51a…`. No finding was accepted on the spec's authority. The mandate's code
anchors (`workflow_runner.py:3214`, `spec_status.py:385`) were checked at the real sites.

**Verdict legend.** **PASS** — the claimed edge holds at the pin, with code/command evidence.
**FAILED (deviation)** — the claimed edge does not hold as stated; the deviation is recorded and
the true state proven. In a pin phase, a FAILED sub-edge is not a wave failure — it is the
correction that makes the implementation phases target the real state.

### Gap 1 (w1) — `kind:test` phases run in-process, the orchestrator fail-closes on them, and no verifier executor exists

#### Edge 1a — `kind:test` phases run in-process: the `run_suite` call. **PASS**

The engine (`runtime.workflow_runner.run_workflow`) owns test semantics. The `kind == "test"`
branch runs the suite IN-PROCESS — no executor, no container, no model call:

```bash
grep -n "if kind == \"test\"" src/agentic_dynamics/runtime/workflow_runner.py
grep -n "suite = run_suite(wd" src/agentic_dynamics/runtime/workflow_runner.py
```

Evidence:

```
workflow_runner.py:2972:            if kind == "test":
workflow_runner.py:2977:                suite = run_suite(wd, language, timeout=phase_timeout,
```

The branch (`:2972-2984`) calls `run_suite(wd, language, timeout=…, target=phase_def.get("tests"))`
at `:2977` — `run_suite` imported from `agentic_dynamics.runtime.test_runner` (`:177`) — and the
verdict is `suite_succeeded(suite)` (`:2981`) recorded on `PhaseResult.test_executed_success`; a
failed/errored suite sets `pr.status = "failed"` (`:2982-2984`). The parallel `test_gate` seam for
agent phases (`_run_test_gate`, `:891-912`) calls the same `run_suite` at `:906`; its post-phase
call site is `:3213-3214`. Test phases produce no attempt record and are never wrapped by the
stall watchdog — the engine docstring and `:3121-3122` ("test phases run in-process, never through
this path") state this as design. **The spec's anchor `:3214` for the run_suite call is the
`test_gate` seam, not the `kind:test` branch (D-1 below); the real `kind:test` in-process call is
at `:2977`.** The engine, not an executor, owns test semantics — confirmed by the existing parity
suite's own comment (`tests/test_workflow_executor_parity.py:199-203`).

#### Edge 1b — the orchestrator fail-closes on `kind:test` phases: the refusal. **FAILED (deviation) — the refusal does not exist in the launched code.**

The mandate asks for the orchestrator's fail-closed refusal of a `kind:test` phase. That refusal
is **not present** at this pin. Evidence:

```bash
grep -rn "REFUSED\|no Docker verifier\|verifier executor first" --include="*.py" src/ scripts/
git show e0bdbcc54^:scripts/run_workflow.py | grep -n "kind == \"test\""   # pre-P0-2 history
```

The only "REFUSED"-class hits in `src/` are `SONAR_STATUS_STALE_REFUSED` (an unrelated quality
signal). The concrete refusal the spec describes — *"[orchestrator] <name>: REFUSED — kind: test
phases have no Docker verifier executor; skipping is forbidden (P0-1 fail-closed)"* — existed in
the **pre-P0-2 second orchestrator loop** (`scripts/run_workflow.py:_run_orchestrator`,
`git show e0bdbcc54^:scripts/run_workflow.py:611-621`). That loop — and its refusal — was
**deleted** by the P0-2 unification (`e0bdbcc54`, "collapse to ONE semantic workflow engine").
Post-P0-2 the `--orchestrator` path injects `DockerAgentExecutor` into the same engine
(`scripts/run_workflow.py:432-449`), and the engine executes `kind:test` in-process at `:2977`
**regardless of which step executor is injected** — the executor is consulted only in the agent
branch (`workflow_runner.py:3136-3139`).

Empirical confirmation at the pin (a Docker-shaped executor injected, a real `kind:test` phase
with a real passing pytest target — read-only probe, no docker, no model):

```
RESULT ok: True state: succeeded
  phase=agent_one kind=agent status=ok test_executed_success=None ...
  phase=gate_run kind=test status=ok test_executed_success=True tests_passed=1 tests_total=1
EXECUTOR RECEIVED: [('agent_one', 'agent')]
```

The executor received only the agent phase; the `kind:test` phase executed **in-process** and
recorded `test_executed_success=True` from `run_suite` — **no refusal, no skip, no dispatch**. So
under `--orchestrator` today a declared verification runs in the orchestrator engine's OWN
container (the privileged socket-holder) rather than in an isolated read-only verifier cell.

*Reading of the deviation.* The w1 gap's CORE premise holds — there is no verifier dispatch and
no container verification, so the reference containerized path still cannot run a `kind:test` as
an isolated verifier bound to the candidate SHA. But the mechanism is **worse than the spec's
"loud refusal"**: post-P0-2 the phase is neither refused nor isolated — it silently executes
in-process in the orchestrator's privileged container. That is precisely the shape `w1` must
replace with a dispatch, and it makes the "no skip — P0-1" guarantee (the suite does run) true in
a way the spec did not predict. The mandate's `w1_verifier_executor` work item is unchanged and
now better-justified; the preregistered baseline corrects the spec's stated mechanism (see D-2).

#### Edge 1c — no verifier executor exists: the `StepExecutor` implementations. **PASS**

```bash
grep -rn "class .*Executor\|Verifier" --include="*.py" src/agentic_dynamics/runtime/executor.py scripts/fleet/docker_executor.py
```

The full executor family at the pin:

```
runtime/executor.py:91:   class StepExecutor(Protocol)     # the seam's contract
runtime/executor.py:105:  class LocalAgentExecutor:          # the default — in-process agent call
scripts/fleet/docker_executor.py:34: class DockerAgentExecutor(StepExecutor):  # sibling-cell agent executor
```

Both concrete executors are **AGENT** executors (the docker one is even named `DockerAgent`).
No `DockerVerifierExecutor` — no verifier executor of any name — exists anywhere in `src/` or
`scripts/` (a repo-wide grep for "verifier" returns zero runtime hits; the only match is the spec
itself). `StepRequest.phase_kind` (`executor.py:40`) is carried but ignored by both executors —
there is no kind-aware dispatch. The existing parity suite has **18 tests and no verifier cases**
(`tests/test_workflow_executor_parity.py`), matching the spec's measured count.

### Gap 2 (w2) — `derive_status` returns the authored status first; no `workflow_revision_id`

#### Edge 2a — `spec_status.py` returns the authored status first. **PASS**

```bash
grep -n "if spec.status" src/agentic_dynamics/experiment/spec_status.py
```

Evidence:

```
spec_status.py:385:    if spec.status:
spec_status.py:386:        return spec.status
```

`derive_status` (`:341-407`) returns the spec's authored `status:` **before any run-evidence
derivation** — the precedence is even documented in its docstring (`:352-353`: "the YAML's
`status`, when the operator authored one (an explicit `draft` or `tombstoned` is a claim only a
human can make)"). The mandate's anchor `:385` is exact.

The live failure mode reproduces at the pin — the `fleet_job_submission` example the spec names:

```bash
grep -n "^status:" workflows/repository/fleet_job_submission.yaml     # -> status: completed (line 18)
python3 -c "..." experiments/results/workflows/fleet_job_submission/20260901T002827Z.json
```

- The YAML authors `status: completed` (`fleet_job_submission.yaml:18`), **and** the spec's
  phases include a `p6_test_gate` (`kind: test`) appended after the last run.
- The LAST run ledger (`20260901T002827Z.json`) records **one** phase —
  `p5_egress_proxy_enforcement` — succeeded. **The `p6_test_gate` phase has never run.**
- Yet the spec index (`experiments/specs/index.json`, spec-status/v2, 181 specs) reports
  `fleet_job_submission`: `status: completed`, `n_runs: 3`, `latest_ok: True` — the authored
  status winning over the evidence (a completed-with-a-never-run-gate entry).

That is exactly the deep-review's 'fleet_job_submission completed with a never-run gate' failure
mode: the prose (`status:`) decides what the run evidence should decide.

#### Edge 2b — no `workflow_revision_id` (canonicalized spec revision digest). **PASS** (with one recorded imprecision, D-3)

The mandate: "no `workflow_revision_id` exists (grep)". The grep does find the NAME — but only as
an **empty skeleton**, never as a revision identity:

```bash
grep -rn "workflow_revision_id" --include="*.py" src/ scripts/ | grep -v control_db.py
grep -rn "workflow_revision_id\s*=" --include="*.py" src/ scripts/
grep -rn "sha256\|canonical\|digest" --include="*.py" src/agentic_dynamics/experiment/
```

Evidence:

```
control_db.py:839:    workflow_revision_id TEXT NOT NULL DEFAULT '',     # the runs-table column
control_status.py:214/350:  "workflow_revision_id": ... run.workflow_revision_id,  # the packet echoes it
scripts/run_workflow.py:822:  run = db.create_run(spec_name=..., model=..., state=..., reason=...)  # field NEVER passed
experiment_spec.py:645:  spec_id -> "<name>@<version>"                    # the ONLY spec identity; no digest
```

- The control-db `runs` row has a `workflow_revision_id` column (`control_db.py:839`) defaulting
  to `''`, and the control packet carries it (`control_status.py:350`) — but **no code computes a
  canonicalized spec digest and no caller populates it**. `create_run` is never handed the field
  (`scripts/run_workflow.py:822` omits it), so it stays `''`. The live row for THIS run proves it:
  `run-85f33d68de3b` has `workflow_revision_id = ''` and `candidate_sha = ''` at the pin.
- **No canonicalization exists anywhere in the experiment plane**: `experiment_spec.py` has no
  `sha256`/`canonical`/`digest` code; the only spec identity is the ledger's
  `spec_id = "<name>@<version>"` (`:645-649`). `spec_status.derive_status` never consults the
  column — completion is keyed to the authored status (Edge 2a) and to run ledgers, never to a
  revision digest.
- Editing a spec therefore cannot invalidate completion: no revision is recorded, so a completed
  run of revision A and an edited revision B are indistinguishable to `derive_status`.

The substantive claim holds — **no revision identity exists, and completion is not keyed to one**.
The recorded imprecision is that the field name already exists as an empty, never-populated
control-db column (D-3); the w2 work is to give it the canonicalized-digest semantics the control
db's own docstring already promises ("Identifies the exact spec bytes/revision executed…",
`control_db.py:461-464`) but nothing delivers.

---

## 3. Preregistered run facts (measured at the pin)

| Fact | Method | Measured |
|---|---|---|
| The spec is unedited since the run launched | `sha256sum` = the pin's digest | **PASS** — `78ad597f…` |
| This run's row is live and the revision field is empty | live control db `runs` row | **PASS** — `run-85f33d68de3b` `running`, `workflow_revision_id=''`, `candidate_sha=''` |
| `kind:test` runs in-process under ANY executor | code `:2972-2984` + injected-executor probe | **PASS** — suite ran in-process, executor untouched |
| No verifier executor is injectable | executor family grep | **PASS** — only `LocalAgentExecutor` + `DockerAgentExecutor` |
| Authored status wins in `derive_status` | `spec_status.py:385-386` + the live index | **PASS** — `fleet_job_submission` shows `completed` with a never-run `p6_test_gate` |
| No canonicalized spec revision digest | `experiment_spec.py` grep + run row | **PASS** — no digest code; field empty everywhere |

---

## 4. Deviations recorded against the pinned bytes / mandate

Recorded per the D-series convention. Each deviation is a correction to the spec's stated
baseline that the implementation phases should consume; none changes the wave's work items.

**D-1 — the spec's `workflow_runner.py:3214` anchor points at the `test_gate` seam, not the
`kind:test` branch.** The mandate (and the spec's `domain_context`) locates the in-process
`run_suite` call at `:3214`. That line is the `_run_test_gate(...)` call for **agent** phases
declaring `test_gate: true` (`:3213-3214`). The genuine `kind:test` in-process `run_suite` call is
the `:2972-2984` branch (`:2977`). Both seams exist; the claim they support (Edge 1a) was verified
at both real sites.

**D-2 — the "orchestrator fail-closed refusal" is not in the launched code (Edge 1b FAILED).**
The refusal the spec names lived in the pre-P0-2 second orchestrator loop, deleted by the P0-2
unification (`e0bdbcc54`). At the pin the unified engine runs `kind:test` in-process in the
orchestrator's own container under `--orchestrator` — **not refused, not skipped, not isolated**.
The w1 gap's core premise (no container verification, no verifier dispatch) holds and is now
better evidenced; the "loud refusal" the spec's question text leans on is gone and the truth is
more severe (a silent in-process run in the privileged parent). `w1_verifier_executor` should
treat the current behavior as "runs in-process in the parent", not "refuses", when it turns the
fail-closed posture into a dispatch.

**D-3 — the field name `workflow_revision_id` already exists as an empty control-db column (Edge
2b imprecision).** The mandate says "no `workflow_revision_id` exists"; strictly, the `runs`
column (`control_db.py:839`) and the packet field (`control_status.py:350`) exist but are never
populated (always `''`) and are never derived from a canonicalized spec. The substantive claim —
no revision identity, completion not keyed to one — holds and is proven by this run's own live
row (`run-85f33d68de3b`, `workflow_revision_id=''`). The w2 work should fill the existing column's
semantic promise rather than invent a new surface.

---

## 5. Scope compliance

The phase mandate (w1_pin_spec prompt): write this preregistration carrying the pin + the two
gaps verified against the actual code (DB read by absolute path at the main checkout), then
commit with the `[workflow] w1_pin_spec — <goal prefix>` subject.

- **Created:** `docs/reviews/engine_gaps_verifier_revision_preregistration.md` (this file) — the
  wave's pin, in the `/tmp/wt_wave1` worktree at the spec-commit tip.
- **Edited:** nothing else. Every verification above is read-only — `sha256sum`, `git rev-parse`,
  `git show`, `git grep`, `grep`, read-only `sqlite3.connect(...)` SELECTs against the live
  control db, and an in-process engine probe with a scripted Docker-shaped executor and a trivial
  real pytest target (no docker daemon, no model call, no credentials).
- **Not done, deliberately:** the spec's stale anchors (`:3214`, the "fail-closed refusal"
  wording) were left unrepaired — repairing them would edit the very spec whose SHA256 this
  document pins. The `run.log` modification in the working tree is a runner artifact, untouched
  and unstaged.

---

## 6. Verdict

| # | Mandate edge (as stated) | Status at the pin |
|---|---|---|
| 1a | `kind:test` phases run in-process — find the `run_suite` call | **PASS** — `workflow_runner.py:2977` (branch `:2972-2984`); `test_gate` seam `:906`/`:3213-3214` |
| 1b | the orchestrator fail-closes on `kind:test` — find the refusal | **FAILED (D-2)** — no refusal in the launched code; the pre-P0-2 refusal was deleted (`e0bdbcc54`). The engine runs `kind:test` in-process in the orchestrator's own container under an injected executor (probe-proven: suite ran, `test_executed_success=True`, executor never received the phase) |
| 1c | no verifier executor exists — grep `StepExecutor` | **PASS** — only `StepExecutor` (Protocol), `LocalAgentExecutor`, `DockerAgentExecutor`; no verifier anywhere |
| 2a | `spec_status.py` returns the authored status first — find the line | **PASS** — `spec_status.py:385-386`; live `fleet_job_submission` index entry `completed` with a never-run `p6_test_gate` |
| 2b | no `workflow_revision_id` exists — grep | **PASS (D-3)** — the name exists as an empty, never-populated control-db column; no canonicalized spec digest exists anywhere; completion is not keyed to a revision (this run's own row: `''`) |

**Pin verdict: Gap 1's core premise is CONFIRMED (in-process-only test phases, no verifier
executor, no kind-aware dispatch); the "loud orchestrator refusal" sub-edge is the one deviation —
the refusal was removed by the P0-2 unification and the true current behavior is a silent
in-process run in the orchestrator's privileged parent, which strengthens the w1 mandate. Gap 2 is
CONFIRMED as stated: authored status wins at `spec_status.py:385-386`, reproducing the
`fleet_job_submission` never-run-gate failure mode live, and no canonicalized spec revision digest
exists anywhere.** The five findings above — each with code + command + (where live) db evidence,
none asserted — are the baseline the implementation phases (`w1_verifier_executor`,
`w2_revision_identity`) and the adversarial review (`w3_adversarial`) will be measured against.

The mandate is anchored: spec SHA256
`78ad597f6175a822f23c1e2b439aa134205e2d1065b72fd9837ef39999094d4a` at git
`a1081d51a236c5e844b5bfeb9ba588921484fef0`, run `run-85f33d68de3b`. `w1_verifier_executor`
(implementation) may proceed.
