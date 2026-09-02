---
status: accepted
kind: preregistration
spec: control_db_evidence
phase: e0_pin_spec
generated_at: 2026-09-02T05:28:15Z
---

# Preregistration — `control_db_evidence`

**The house pin convention.** This document is written BEFORE any implementation phase
runs. Its purpose is twofold, and both halves are load-bearing:

1. **Anchor the run to exact bytes.** A workflow spec is a mutable file. If it is edited
   mid-run, the run that finishes is not the run that started, and the adversarial phase
   (e6) has no fixed target to falsify. Recording the spec's SHA256 makes the mandate
   immutable *by reference*: any later divergence is detectable by re-running one command.
2. **Verify the premises, do not assert them.** The spec's `current_state` block is a
   set of claims about the repository and the live control database, written by the spec
   author on 2026-09-02. Every implementation phase (e1–e5) is justified by those claims —
   you do not build a per-phase evidence write if rows already appear, and you do not purge
   deadbeef receipts that were never committed. A preregistration that copied those claims
   forward would be circular. This one re-derives each of the five mandated edges from the
   actual code and the LIVE control database — which lives at the MAIN checkout,
   `/home/drseuss/ai-finops-framework/experiments/results/control/control.db`, gitignored
   and absent from this worktree — and records the command that produced the evidence, so a
   reader can reproduce every PASS without trusting this document.

The mandate is: **an edge that does not hold is a FAILED finding.** All five edges hold.
One spec-integrity deviation was found and is recorded in §4 — it does not falsify any
edge, but it is a fact about the pinned bytes and the reader is entitled to it.

---

## 1. The pin

| Field | Value |
|---|---|
| Spec path | `workflows/repository/control_db_evidence.yaml` |
| Spec **SHA256** | `096199a79b8cd1a5b0073f4e9fdfd4f2f72a1f1675aaccd4a8661aca01ffc5cb` |
| Spec size | 26,079 bytes |
| Worktree HEAD (git sha) | `fb48b889c51c3f43166148f827df18a3f50df0fc` |
| HEAD subject | `spec: control_db_evidence — correct the false premises (the 2026-09-02 pin findings)` |
| HEAD committed | 2026-09-02 07:22:40 +0200 |
| Branch | detached `HEAD` (worktree `/tmp/wt_evidence`) — `git rev-parse main` = `fb48b889c…`, i.e. the worktree sits at main's tip |
| Working tree | clean except modified `run.log` (a runner artifact, not a source file) |
| Control db | `/home/drseuss/ai-finops-framework/experiments/results/control/control.db` (machine-local, gitignored, NOT in this worktree) |
| Pinned at | 2026-09-02T05:28:15Z |

Reproduce the pin — these are the EXACT bytes the run executes:

```bash
sha256sum workflows/repository/control_db_evidence.yaml
# 096199a79b8cd1a5b0073f4e9fdfd4f2f72a1f1675aaccd4a8661aca01ffc5cb
git rev-parse HEAD
# fb48b889c51c3f43166148f827df18a3f50df0fc
```

If either value differs at the time e6 (adversarial) or e7 (test gate) runs, the spec was
edited mid-run and the mandate this document pins is no longer the mandate being executed.
That is itself a reportable finding, and this table is what makes it detectable.

### Spec shape at the pin (what is being anchored)

Eight phases, of which seven are `kind: agent` and one is `kind: test`:

| # | Phase | kind | scope |
|---|---|---|---|
| 0 | `e0_pin_spec` | agent | `implementation` |
| 1 | `e1_phase_evidence` | agent | `implementation` |
| 2 | `e2_drain_and_lifecycle` | agent | `implementation` |
| 3 | `e3_hermetic_publication` | agent | `implementation` |
| 4 | `e4_phase_epoch` | agent | `implementation` |
| 5 | `e5_preexisting_guard` | agent | `implementation` |
| 6 | `e6_adversarial` | agent | `adversarial_readonly` |
| 7 | `e7_test_gate` | test | `implementation` |

---

## 2. Verified current-state edges

Each edge is stated as the spec states it, then **independently re-derived** against the
code at `fb48b889c…` and the live control database. "Method" is the command actually run;
"Evidence" is its actual output. No edge below was accepted on the spec's authority. The
control db was read by absolute path per the pin (this worktree has no
`experiments/results/control/` directory).

### Edge 1 — `step_attempts`/`gate_results` are 0 for run-2bc253a8d87a; `record_gate_result` has no production caller → **PASS**

*Method (the live db — both tables, globally and per-run).*

```bash
python3 -c "
import sqlite3
c = sqlite3.connect('/home/drseuss/ai-finops-framework/experiments/results/control/control.db')
print('step_attempts:', c.execute('SELECT COUNT(*) FROM step_attempts').fetchone())
print('gate_results:', c.execute('SELECT COUNT(*) FROM gate_results').fetchone())
print('runs:', c.execute('SELECT run_id, spec_name, state FROM runs').fetchall())
"
```

*Evidence.*

```
step_attempts: (0,)
gate_results: (0,)
runs: [('run-2bc253a8d87a', 'control_db_followups', 'promotable'), ...]
```

Both evidence tables are empty across the whole database, so trivially 0 for
`run-2bc253a8d87a` — the `control_db_followups` run that the deep review measured as having
executed **8 phases** (verified from its run ledger,
`experiments/results/workflows/control_db_followups/20260902T031150Z.json`: `phases` =
`f0_pin_spec … f7_test_gate`, all `status: ok`, `phase count: 8`). The run's terminal row
(`state: promotable`) and its transitions exist; the per-phase evidence does not.

*Method (callers).* Grep the whole tree for `record_gate_result`, then separate the
definition from callers and the test callers from production callers.

```bash
grep -rn "record_gate_result" --include="*.py" src/ scripts/ apps/
grep -rn "record_gate_result" --include="*.py" tests/
```

*Evidence.*

```
src/agentic_dynamics/control/control_db.py:1742:    def record_gate_result(
tests/test_control_status.py:193,262,319,346,499   db.record_gate_result(...)
tests/test_control_db.py:532,549,551,569,580,581,589,598,608,792,867   ...record_gate_result(...)
```

`record_gate_result` is defined at `control_db.py:1742`; **zero callers in `src/`,
`scripts/`, or `apps/`** — every call site is in `tests/`. Corroborating the same gap on
the sibling writers: `start_attempt`/`finish_attempt` (the `step_attempts` INSERT +
close path, `control_db.py:1643`/`:1681`) also have **zero production callers** (only
`tests/test_control_db.py` references them). The write side of the resume re-point exists
as code and is exercised only by tests; nothing in the run path calls it. This is the
mechanical proof of "the db recorded 0 step_attempts for an 8-phase run".

*Reading.* The edge holds. e1 has greenfield tables to fill and a real write seam to wire.

### Edge 2 — the outbox's 68 rows are all DELIVERED (the run-path drain works); no drain COMMAND exists; no zombie-run sweep exists → **PASS**

*Method (the outbox rows).*

```bash
python3 -c "
import sqlite3
c = sqlite3.connect('/home/drseuss/ai-finops-framework/experiments/results/control/control.db')
print('by run/status:', c.execute('SELECT run_id, status, COUNT(*) FROM outbox GROUP BY run_id, status').fetchall())
print('pending:', c.execute(\"SELECT COUNT(*) FROM outbox WHERE status='pending'\").fetchone())
print('delivered:', c.execute(\"SELECT COUNT(*) FROM outbox WHERE status='delivered'\").fetchone())
print('dead:', c.execute(\"SELECT COUNT(*) FROM outbox WHERE status='dead'\").fetchone())
"
```

*Evidence.*

```
by run/status: [('run-2bc253a8d87a', 'delivered', 68)]
pending: (0,)
delivered: (68,)
dead: (0,)
```

All 68 outbox rows belong to `run-2bc253a8d87a` and are `delivered` — the drain that ran at
the followups run's terminal write delivered every row (the deep review's "68 pending,
never drains" was a misread of a row count for a status; the at-least-once promise HOLDS in
the run path).

*Method (a drain COMMAND).* The CLI's `control` namespace maps exactly one subcommand.

```bash
grep -n '"control"' src/agentic_dynamics/cli.py
grep -rni "drain.outbox\|drain_outbox\|drain-outbox\|control drain" --include="*.py" --include="*.md" src/ scripts/ apps/ docs/ workflows/
grep -rn "\.drain(" --include="*.py" src/ scripts/
```

*Evidence.*

```
("control", "status"): "control_status.py",        # the ONLY control subcommand
(no output)                                        # no drain-outbox surface anywhere
scripts/run_workflow.py:891:  report = ob.OutboxPublisher(db, authorized=True).drain()
```

`OutboxPublisher.drain` (`src/agentic_dynamics/control/outbox.py:484`) has exactly **one
production caller** — `scripts/run_workflow.py:891`, inside `_control_terminal_write` (the
run-path drain). There is no operator-visible drain command: no CLI mapping, no backing
script, no `control drain-outbox` surface. (The `fleet_manager.py` "drain" is a docker
service command over `fleet:commands`, unrelated to the outbox.)

*Method (a zombie-run sweep).*

```bash
grep -rni "zombie\|cancell.*running\|running.*heartbeat\|sweep" --include="*.py" src/ scripts/ | grep -vi "test\|orphan_sweep\|fleet"
grep -rni "transition_run.*cancelled\|\.cancel(" --include="*.py" src/ scripts/
```

*Evidence.* No production code transitions a stale `running` control-run row to `CANCELLED`.
The only "sweep" on the control plane, `src/agentic_dynamics/control/orphan_sweep.py`,
reaps orphaned **subagent processes** in the opencode session layer — it never touches the
control db's `runs` table. The two zombie runs the deep review proved on 2026-09-02 are
visible as historical fact in the db: `run-d61ec458cb6b` and `run-0aeb16f0d855` were
cancelled by hand via `transition_run` (reason: `operator cancel: killed run left a
dangling row (deep-review cleanup)`), not by any sweep.

*Reading.* The edge holds in all three parts: the run-path drain works (68/68 delivered),
no drain command exists for operator recovery, and no zombie-run sweep exists — e2's two
deliverables are genuinely absent.

### Edge 3 — 13 deadbeef/operator-test receipts are committed; `write_receipt` ignores `--db` → **PASS**

*Method (the committed receipts).*

```bash
git ls-files experiments/results/publication/ | wc -l
for f in $(git ls-files experiments/results/publication/); do grep -lq "deadbeef\|operator-test" "$f" && echo "$f"; done | wc -l
python3 -c "import json; d=json.load(open('<a tracked receipt>')); print(d['repo_sha'], d['operator'])"
git log --all --oneline --diff-filter=A -S "deadbeef" -- experiments/results/publication/
```

*Evidence.*

```
tracked at HEAD: 13
receipts carrying deadbeef|operator-test: 13 / 13
repo_sha = deadbeef     operator = operator-test     release_id = None
7 commits added deadbeef receipts across both waves:
  2d6692d52 [workflow] p7_adversarial … (+12 files)   edd0e928d [workflow] p7_adversarial … (+1 file)   # publication wave
  3c5ecb885 [workflow] f1_resume_repoint …           16bf26eeb [workflow] f3_dry_run_no_touch …
  63682849a [workflow] f4_portal_repoint …            756c3d4ab, ca0248992 [workflow] f6_adversarial …  # followups wave
```

Every one of the 13 git-tracked receipt files under `experiments/results/publication/` at
this pin carries `repo_sha: deadbeef` and `operator: operator-test` — test artifacts
committed as provenance. `git log` confirms they entered history across 7 commits spanning
both waves (the p7 commits of the publication wave; the f1/f3/f4/f6 commits of the
followups wave). At THIS tree (main's tip) all 13 trace to the p7 commits; the followups
wave added further deadbeef receipts in 5 commits on its (unmerged, promotable) branch.

*Method (`write_receipt` ignores `--db`).* Read the definition and the production call site.

```bash
grep -n "RECEIPT_DIR\|def write_receipt" src/agentic_dynamics/control/publication.py
grep -n "write_receipt\|--db\|ControlDB.open" scripts/publish_release.py
```

*Evidence.*

```
publication.py:80:   RECEIPT_DIR = PROJECT_ROOT / "experiments" / "results" / "publication"
publication.py:996: def write_receipt(receipt, *, directory=None):
publication.py:1002:    target_dir = Path(directory) if directory is not None else RECEIPT_DIR
publish_release.py:280: parser.add_argument("--db", default=None, ...)
publish_release.py:436: receipt_path = pub.write_receipt(receipt)          # NO directory override
publish_release.py:439: with ControlDB.open(args.db) as db:                # --db reaches ONLY the db handle
```

`write_receipt` writes to the module-level `RECEIPT_DIR` (`publication.py:80`) whenever its
`directory=` parameter is `None` (`:1002`). The production call at `publish_release.py:436`
passes no `directory`, and the `--db` flag flows only into `ControlDB.open` (`:439`) — so
the receipt archive path is the production `experiments/results/publication/` **regardless
of `--db`**. The test suite proves the consequence: `tests/test_publish_release.py` runs
`pr.main([... "--db", str(tmp_path / ...), "--operator", "operator-test"])` and monkeypatches
`read_head_sha` → `"deadbeef"`, and `test_failed_deploy_is_recorded` (the non-dry-run path
that reaches step 7's receipt write) leaves a `deadbeef`/`operator-test` receipt in the
production `RECEIPT_DIR` — which the p7/f-wave agents then committed. That is the exact
mechanism e3 must make hermetic.

*Reading.* The edge holds. 13 test receipts are committed and the path by which they got
there (the `--db` override not reaching `write_receipt`) is verified in code.

### Edge 4 — `control_epoch` is 2 for an 8-phase run (run-state transitions only) → **PASS**

*Method (the live db + the epoch derivation).*

```bash
python3 -c "
import sqlite3
c = sqlite3.connect('/home/drseuss/ai-finops-framework/experiments/results/control/control.db')
print('control_meta:', c.execute('SELECT * FROM control_meta').fetchall())
print('transitions:', c.execute('SELECT run_id, from_state, to_state FROM run_transitions').fetchall())
"
grep -n "_bump_epoch" src/agentic_dynamics/control/control_db.py
```

*Evidence.*

```
control_meta: [('schema_version', '2'), ('control_epoch', '7')]
run_transitions (7 rows):
  run-2bc253a8d87a  None→running, running→promotable      # the 8-phase followups run: 2 transitions
  run-d61ec458cb6b  None→running, running→cancelled       # zombie, cancelled by hand
  run-0aeb16f0d855  None→running, running→cancelled       # zombie, cancelled by hand
  run-ba8a4deda548  None→running                          # the current control_db_evidence run
_bump_epoch call sites: control_db.py:1425 (create_run), control_db.py:1511 (transition_run)   # ONLY these two
```

The epoch is a **global monotonic counter** bumped exactly twice in the whole module —
`create_run` (`:1425`) and `transition_run` (`:1511`) — and the live db confirms the 1:1
mapping (7 transition rows, epoch 7). `run-2bc253a8d87a`, the run that executed **8 phases**
(see Edge 1), contributed exactly **2** transitions (`create→running`, `running→promotable`)
and therefore advanced the epoch by exactly **2 for its 8 phases**. None of the 8 phases
moved the epoch: `start_attempt`/`finish_attempt`/`record_gate_result` never call
`_bump_epoch`, and the tables they would write are empty (Edge 1). The current live epoch of
7 (vs. the deep review's 2) is the same counter after the two zombie-run cancellations (+4)
and this run's creation (+1) — the per-run contribution of the 8-phase run is unchanged at
2. The packet (`src/agentic_dynamics/control/control_status.py:721-733`) exposes
`control_epoch` and run-state refs but **no `phases_completed`/`phases_total`** — a master
diffing turns sees run-state changes, never phase progress.

*Reading.* The edge holds: the epoch advanced 2 for an 8-phase run, with the derivation
proving the advance is run-state-only. e4's per-phase epoch + phase-progress fields have a
real gap to fill.

### Edge 5 — no pre-existing-drift guard exists → **PASS**

*Method.* Search for the guard by every plausible name, then check for the two files e5
would create.

```bash
ls tests/test_preexisting_drift_guard.py scripts/check_preexisting.py 2>&1
grep -rni "pre-existing\|preexisting\|pre_existing\|merge.base\|merge_base" --include="*.py" src/ scripts/ | grep -vi "test"
```

*Evidence.*

```
ls: cannot access 'tests/test_preexisting_drift_guard.py': No such file or directory
ls: cannot access 'scripts/check_preexisting.py': No such file or directory
```

No module, script, or test implements the guard's contract — "given a failing test and a
merge-base, prove the failure exists at the merge-base BEFORE the author may call it
pre-existing". The `pre-existing`/`merge-base` hits in production code are unrelated:
`workflow_runner.py`/`promote.py`/`pipeline.py` use `git merge-base` for ancestor checks and
squash-diff computation, `evidence_prereq_gate.py` verifies a prerequisite commit is an
ancestor, and the `pre-existing` adjectives in `sonar.py`/`lsp_diagnostics.py` are novelty
rules for code-quality issues — none is a review-rail guard that would make the f4/f5
mislabeling pattern fail mechanically. There is no citation requirement anywhere that a
"pre-existing" claim in a review doc must name a base sha + test + before/after outcome.

*Reading.* The edge holds. The guard does not exist in any form e5 could be accused of
modifying; it is greenfield.

---

## 3. Supporting current-state facts (verified, not mandated)

These are not among the five mandated edges, but the spec's `current_state` asserts them and
later phases depend on them. They were cheap to verify, so they were verified.

| Assertion | Method | Result |
|---|---|---|
| The 8-phase run's phases are real | read `experiments/results/workflows/control_db_followups/20260902T031150Z.json` | **PASS** — 8 phases `f0_pin_spec…f7_test_gate`, all `ok` |
| The run-path drain's sole caller | `grep -rn "\.drain(" src/ scripts/` | **PASS** — only `scripts/run_workflow.py:891` |
| The db has two cancelled zombie runs | `run_transitions` query | **PASS** — `run-d61ec458cb6b`, `run-0aeb16f0d855`, cancelled by hand with the deep-review reason |
| The packet carries no phase-progress field | read `build_packet` (`control_status.py:721-733`) | **PASS** — `control_epoch` yes; `phases_completed`/`phases_total` absent |
| `step_attempts` writers (`start_attempt`/`finish_attempt`) have no production callers | `grep` src/ scripts/ apps/ | **PASS** — tests only |

---

## 4. Deviations found in the pinned bytes

Recorded per the D-series convention: one-line notes with reasoning. The deviation does not
falsify any edge, so it does not fail this phase — but it is a property of the exact bytes
being pinned, and e6 should treat it as known.

**D-1 — the spec's code anchors are stale by ~79 lines at one site.** The e0 mandate and the
spec's `domain_context` both point at the `write_receipt` call at `publish_release.py:515`;
the call is actually at **`:436`** in the pinned tree (the file is 499 lines; the deep
review's measurement predates later edits). The claim itself — `write_receipt` receives no
`directory` and so writes to `RECEIPT_DIR` regardless of `--db` — was verified at the real
site (Edge 3) and holds. Recorded so e6 does not waste an attack on a vanished line number.

---

## 5. Scope compliance

The phase mandate (e0 prompt): write this preregistration carrying the pin + the five
verified edges, then commit with the `[workflow] e0_pin_spec — <goal prefix>` subject.

- **Created:** `docs/reviews/control_db_evidence_preregistration.md` (this file) — one file.
- **Edited:** nothing. Every verification above is read-only — `sha256sum`, `git rev-parse`,
  `git log`, `git ls-files`, `grep`, `sed`, and read-only `sqlite3.connect(...)` SELECTs
  against the live control db at the main checkout.
- **Not done, deliberately:** D-1 was left unrepaired (repairing it would edit the very spec
  whose SHA256 this document pins). The `run.log` modification in the working tree is a
  runner artifact, untouched.

---

## 6. Verdict

| # | Edge | Verdict |
|---|---|---|
| 1 | `step_attempts`/`gate_results` are 0 for run-2bc253a8d87a; `record_gate_result` has no production caller | **PASS** |
| 2 | The outbox's 68 rows are all DELIVERED; no drain COMMAND; no zombie-run sweep | **PASS** |
| 3 | 13 deadbeef/operator-test receipts are committed; `write_receipt` ignores `--db` | **PASS** |
| 4 | `control_epoch` is 2 for an 8-phase run (run-state transitions only) | **PASS** |
| 5 | No pre-existing-drift guard exists | **PASS** |

**5/5 PASS. No edge failed. One deviation recorded (D-1), not falsifying.**

The mandate is anchored: spec SHA256
`096199a79b8cd1a5b0073f4e9fdfd4f2f72a1f1675aaccd4a8661aca01ffc5cb` at git
`fb48b889c51c3f43166148f827df18a3f50df0fc`, with every premise verified against the code
and the live control db — never inherited from the spec. `e1_phase_evidence` may proceed.
