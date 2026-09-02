---
status: accepted
kind: preregistration
spec: control_db_evidence
phase: e0_pin_spec
run: verification-rerun
generated_at: 2026-09-02T12:53:40Z
---

# Preregistration — `control_db_evidence` (VERIFICATION RE-RUN on merged main)

**The house pin convention.** This document is written BEFORE any implementation phase of the
verification re-run executes. Its purpose is twofold, and both halves are load-bearing:

1. **Anchor the run to exact bytes.** A workflow spec is a mutable file. Recording the spec's
   SHA256 makes the mandate immutable *by reference*: any divergence is detectable by re-running
   one command.
2. **Verify the premises, do not assert them.** The e0 mandate's five edges describe the state
   the ORIGINAL evidence run pinned on 2026-09-02 (the pre-fix baseline: empty evidence tables,
   no production caller, no drain command, no sweep, 13 committed deadbeef receipts, a
   run-state-only epoch, no pre-existing guard). This run does **not** launch from that state —
   it launches from merged main (`a5ca7988f`), where the wave those five edges justified (e1–e5)
   has **already merged**. So this preregistration re-derives each mandated edge against the
   ACTUAL code and the LIVE control database *as they are at launch*, and records the command that
   produced the evidence, so a reader can reproduce every finding without trusting this document.

**Why a verification re-run exists (the run's mandate).** The first `control_db_evidence` run
(`run-ba8a4deda548`) committed e1 **mid-flight**. Its orchestrator was a single in-process
pipeline launched before e1 existed; it never reloaded its modules, so every phase of that run
executed pre-e1 code and the recorder never fired — `step_attempts: 0`, `gate_results: 0` for an
8-phase run. The adversarial phase of that run (e6) recorded this as an **accepted limitation**
(F1): *"The first run launched after merge is the first to populate the tables live. Not a code
defect."* **This re-run is that first post-merge run** (control-db row `run-5e31f69b4afa`). It
starts with the e1 recorder ALREADY in the launched code, so every executed phase — e0 through e7
— must record its `step_attempts` + `gate_results` rows in the live control db. **The proof this
run owes is the db after the run: `step_attempts >= 8` and `gate_results > 0` for this run_id.**

The five edges are verified below against the state at launch. The verdict legend is stated up
front so no status is misread.

---

## 1. The pin

| Field | Value |
|---|---|
| Spec path | `workflows/repository/control_db_evidence.yaml` |
| Spec **SHA256** | `a358cde6607afd2e99adfce346a8a8d895d9f5042c51ab15f585c7918bdb0044` |
| Spec size | 26,120 bytes |
| Worktree HEAD (git sha) | `a5ca7988f69f028fee59fe9b678d3b68576d3d2b` |
| HEAD subject | `spec index + surfaces regenerated (control_db_evidence merged)` |
| Branch | detached `HEAD` — the worktree `/tmp/wt_evidence_verify` sits at merged main's tip |
| Working tree | clean except modified `run.log` (a runner artifact, not a source file) |
| Run (this re-run) | `run-5e31f69b4afa` — `control_db_evidence`, `state: running`, started `2026-09-02T12:48:46Z`, heartbeat live (last seen `12:50:46Z`, beat 6) |
| First evidence run | `run-ba8a4deda548` — `control_db_evidence`, `state: failed`, ran `05:23→08:22Z` on the PRE-e1 engine (the F1 accepted limitation) |
| Control db | `/home/drseuss/ai-finops-framework/experiments/results/control/control.db` (machine-local, gitignored, NOT in this worktree), `schema_version: 3`, `control_epoch: 9` |
| Pinned at | 2026-09-02T12:53:40Z |

Reproduce the pin — these are the EXACT bytes the run executes:

```bash
sha256sum workflows/repository/control_db_evidence.yaml
# a358cde6607afd2e99adfce346a8a8d895d9f5042c51ab15f585c7918bdb0044
git rev-parse HEAD
# a5ca7988f69f028fee59fe9b678d3b68576d3d2b
```

If either value differs at the time e6 (adversarial) or e7 (test gate) runs, the spec was edited
mid-run and the mandate this document pins is no longer the mandate being executed. That is itself
a reportable finding, and this table is what makes it detectable.

**Spec shape at the pin** — unchanged from the original pin except one line: the spec's e7 gate
list gained `tests/test_phase_evidence.py` (added by e1's commit `c353ddf58`; the only spec diff
since the original pin at `fb48b889c`). Eight phases, seven `kind: agent` + one `kind: test`:

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

## 2. Verified current-state edges (re-derived on merged main)

Each edge below is stated as the e0 mandate states it, then **independently re-derived** against
the code at `a5ca7988f…` and the live control database. No finding was accepted on the spec's or
the original preregistration's authority. The control db was read by absolute path per the pin
(this worktree has no `experiments/results/control/` directory).

**Verdict legend (VERIFICATION RE-RUN semantics).** Each mandate clause is a claim about the state
at the ORIGINAL pin — the open gaps the wave was built to close. On merged main those gaps are the
wave's deliverables. Statuses therefore mean:

- **PASS** — the mandate's claim still describes the current state. These are the *historical
  facts* a recorder cannot and must not retrofit (the old run's empty tables, the delivered rows,
  the old run's recorded epoch contribution). They are the reason the original run could not
  self-prove and this re-run can.
- **SUPERSEDED** — the mandate's claim described an open gap that the merged wave closed. The
  closing fix is verified present in the launched code (evidence + command cited below). In a
  verification re-run, SUPERSEDED is the **positive result**: it is exactly the precondition that
  lets this run finally write real per-phase rows. Each SUPERSEDED is recorded as a deviation per
  the e0 mandate's "an edge that does not hold is a FAILED finding — record the deviation" rule;
  every deviation here is the run's own subject, none is unexpected.

### Edge 1 — `step_attempts`/`gate_results` are 0 for run-2bc253a8d87a; `record_gate_result` has no production caller

*Clause (a) — the old run's tables are empty.* **PASS** (historical fact, unchanged).

*Method (the live db — globally and per-run).*

```bash
python3 -c "
import sqlite3
c = sqlite3.connect('/home/drseuss/ai-finops-framework/experiments/results/control/control.db')
print('step_attempts:', c.execute('SELECT COUNT(*) FROM step_attempts').fetchone())
print('gate_results:', c.execute('SELECT COUNT(*) FROM gate_results').fetchone())
print('sa for run-2bc253a8d87a:', c.execute(\"SELECT COUNT(*) FROM step_attempts WHERE run_id='run-2bc253a8d87a'\").fetchone())
print('gr for run-2bc253a8d87a:', c.execute(\"SELECT COUNT(*) FROM gate_results WHERE run_id='run-2bc253a8d87a'\").fetchone())
"
```

*Evidence.*

```
step_attempts: (0,)
gate_results: (0,)
sa for run-2bc253a8d87a: (0,)
gr for run-2bc253a8d87a: (0,)
```

`run-2bc253a8d87a` (the `control_db_followups` run — 8 executed phases, all `status: ok` per its
ledger) finished at `03:11:50Z`, before e1 existed. Its per-phase evidence is permanently absent:
the recorder cannot retrofit a finished run. **This is the defect the re-run exists to prove is
fixed for runs launched after merge** — including this one. At e0 pin time the tables are empty
*for the whole db* (evidence is recorded at phase END; e0 is the first phase and has not ended
yet).

*Clause (b) — `record_gate_result` has no production caller.* **SUPERSEDED** — the e1 fix is live.

*Method (callers).*

```bash
grep -rn "record_gate_result" --include="*.py" src/ scripts/ apps/ | grep -v "def record_gate_result"
grep -rn "_emit_phase_evidence\|record_phase_evidence" --include="*.py" src/ scripts/ | grep -v "def \|test"
```

*Evidence.*

```
src/agentic_dynamics/control/phase_evidence.py:81:  db.record_gate_result(          # inside record_phase_evidence
src/agentic_dynamics/runtime/workflow_runner.py:3364:  _emit_phase_evidence(          # in the phase loop
src/agentic_dynamics/control/phase_evidence.py:111:  record_phase_evidence(db, run_id, evidence)   # inside make_phase_evidence_recorder
```

The write side is **wired end-to-end** in the launched code:

- `make_phase_evidence_recorder(db, run_id)` (`control/phase_evidence.py`) binds the per-phase
  writer and returns `None` only in child mode (`--only-phase`) or when there is no run row — the
  parent-aggregates contract. The composition root calls it at `scripts/run_workflow.py:565`
  (`make_phase_evidence_recorder(control_db, control_run_id)`) and hands the result to the engine
  at `:612`.
- The engine calls `_emit_phase_evidence(...)` **once per executed phase, for every outcome**, at
  `workflow_runner.py:3363-3372` — after every gate ran and after a checkpoint phase's `awaiting`
  flip, so the recorded status is the phase's final status. A failed phase records a FAILED
  attempt; a control-db outage is caught and reported as a NAMED warning, never failing the phase.
- `record_phase_evidence` (`control/phase_evidence.py:40`) composes `start_attempt` →
  `finish_attempt` + one `record_gate_result` per gate verdict **in one transaction**, reusing the
  db's own writers (attempt numbering from `next_attempt_no`; the `uq_step_attempts_run_step_no`
  UNIQUE contract; `record_gate_result`'s non-empty `candidate_sha` enforcement).

*Reading.* Clause (a) holds (the historical run is unfixable — that is why a re-run is the proof
vehicle). Clause (b) is superseded: `record_gate_result` now has exactly one production caller
(`phase_evidence.py:81`), reached from the engine's phase loop. The recorder that the first run
could not load is the recorder this run was launched with.

### Edge 2 — the outbox's 68 rows are all DELIVERED; no drain COMMAND exists; no zombie-run sweep exists

*Clause (a) — the 68 rows are all DELIVERED.* **PASS** (unchanged).

*Method (the outbox rows).*

```bash
python3 -c "
import sqlite3
c = sqlite3.connect('/home/drseuss/ai-finops-framework/experiments/results/control/control.db')
print('by run/status:', c.execute('SELECT run_id, status, COUNT(*) FROM outbox GROUP BY run_id, status').fetchall())
print('pending:', c.execute(\"SELECT COUNT(*) FROM outbox WHERE status='pending'\").fetchone())
print('dead:', c.execute(\"SELECT COUNT(*) FROM outbox WHERE status='dead'\").fetchone())
"
```

*Evidence.*

```
by run/status: [('run-2bc253a8d87a', 'delivered', 68), ('run-ba8a4deda548', 'delivered', 64)]
pending: (0,)
dead: (0,)
```

All 68 rows for `run-2bc253a8d87a` are `delivered`. Corroborating: the first evidence run's outbox
(`run-ba8a4deda548`) also drained to empty (64/64 `delivered`) — the run-path drain works in the
normal run path, exactly as the deep review established.

*Clause (b) — no drain COMMAND exists.* **SUPERSEDED** — the e2 drain command is live.

*Method.*

```bash
grep -n "drain-outbox\|sweep-zombies" src/agentic_dynamics/cli.py
ls scripts/control_drain_outbox.py
```

*Evidence.*

```
src/agentic_dynamics/cli.py:113:  ("control", "drain-outbox"): "control_drain_outbox.py",
src/agentic_dynamics/cli.py:166:  control     status|drain-outbox|sweep-zombies
scripts/control_drain_outbox.py          # DRAIN_SCHEMA = "control-drain-outbox/v1"
```

`agentic-dynamics control drain-outbox` now exists (CLI mapping → `scripts/control_drain_outbox.py`),
an operator-visible drain command with a JSON report (`delivered`/`dead`/`pending`). The e2 gap the
original pin measured is closed.

*Clause (c) — no zombie-run sweep exists.* **SUPERSEDED** — the e2 sweep is live.

*Method.*

```bash
grep -n "sweep-zombies" src/agentic_dynamics/cli.py
head -30 scripts/control_sweep_zombies.py
```

*Evidence.*

```
src/agentic_dynamics/cli.py:114:  ("control", "sweep-zombies"): "control_sweep_zombies.py",
scripts/control_sweep_zombies.py
```

`agentic-dynamics control sweep-zombies` now exists. It finds `running` runs whose **run heartbeat**
has expired and transitions each to `CANCELLED` **via `transition_run`** (the same
`ALLOWED_TRANSITIONS`-governed API the packet's `safe_actions` derive from — never raw SQL), with
three-valued liveness (`live` untouched / `zombie` cancelled / `unknown` reported, never guessed).
The db confirms the heartbeat table the sweep reads: `run_heartbeats` now exists (one row, this
run's, beat 6, fresh). The manual-cancellation hole the deep review proved on 2026-09-02 is now
mechanically covered.

*Reading.* Clause (a) holds; clauses (b) and (c) are superseded by the merged e2 deliverables. The
two operator/lifecycle gaps the original pin recorded are closed in the launched code.

### Edge 3 — 13 deadbeef/operator-test receipts are committed; `write_receipt` ignores `--db`

*Clause (a) — 13 deadbeef/operator-test receipts are committed.* **SUPERSEDED** — the e3 purge
removed them from the tree.

*Method.*

```bash
git ls-files experiments/results/publication/ | wc -l
git grep -l "deadbeef\|operator-test" -- experiments/results/publication/
git log --oneline -- experiments/results/publication/
```

*Evidence.*

```
0                                   # files tracked under experiments/results/publication/
(no output)                          # no tracked file carries deadbeef|operator-test at HEAD
813a7de6c [workflow] e3_hermetic_publication …   # the e3 deletion commit
edd0e928d 2d6692d52 [workflow] p7_adversarial …  # the deep-history adds the purge removed
```

Zero receipts are tracked at this tree; the purge was a **documented deletion commit** in e3
(`813a7de6c`), removing the 13 deadbeef/operator-test receipts from the tree (the operator's
deletion-vs-rewrite decision is recorded in that commit's body — the rewrite was declined, the
deletion chosen). The deep-history ADD commits remain reachable (a deletion preserves history), but
no committed receipt carries `repo_sha: deadbeef` / `operator: operator-test` at this pin.

*Clause (b) — `write_receipt` ignores `--db`.* **SUPERSEDED** — the receipt path now follows the db.

*Method (the definition and the production call site).*

```bash
grep -n "def receipt_dir_for_db\|def write_receipt\|target_dir = Path(directory)" src/agentic_dynamics/control/publication.py
grep -n "write_receipt(receipt" scripts/publish_release.py
```

*Evidence.*

```
publication.py:996:  def receipt_dir_for_db(db_path=...):        # new resolver
publication.py:1013-1018:  None → RECEIPT_DIR; explicit --db elsewhere → sibling "publication" beside it
publication.py:1021:  def write_receipt(receipt, *, directory=None, db_path=None):
publication.py:1037:  target_dir = Path(directory) if directory is not None else receipt_dir_for_db(db_path)
publish_release.py:436:  receipt_path = pub.write_receipt(receipt, db_path=args.db)
```

`write_receipt` now accepts `db_path=` alongside `directory=` and derives the archive from
`receipt_dir_for_db(db_path)`: with no override the archive is the production `RECEIPT_DIR`
(unchanged), but an explicit `--db` pointing elsewhere redirects the archive to a sibling
`publication/` beside that db — NEVER the production archive. The production call at
`publish_release.py:436` now passes `db_path=args.db`, so an operator-test suite run archives its
receipts next to its tmp db. The e3 mechanism the original pin identified (the `--db` override not
reaching `write_receipt`) is gone.

*Reading.* Both clauses superseded: the committed deadbeef receipts are purged from the tree and
`write_receipt` honors the `--db` override end-to-end. (The mandate's code anchor `:515` is stale
at this tree too — the call is at `:436`; recorded as D-1 below, inherited from the original pin.)

### Edge 4 — `control_epoch` is 2 for an 8-phase run (run-state transitions only)

*Historical record.* **PASS** (unchanged fact): `run-2bc253a8d87a`'s recorded contribution to the
epoch is still exactly **2** — its two run-state transitions (`None→running`,
`running→promotable`), rows 1–2 of `run_transitions`. The epoch it moved is 2 for its 8 phases,
because it ran on the pre-fix engine.

*The derivation.* **SUPERSEDED** — the epoch now advances per phase.

*Method (the live db + the epoch derivation).*

```bash
python3 -c "
import sqlite3
c = sqlite3.connect('/home/drseuss/ai-finops-framework/experiments/results/control/control.db')
print('control_meta:', c.execute('SELECT * FROM control_meta').fetchall())
print('transitions:', c.execute('SELECT COUNT(*) FROM run_transitions').fetchone())
"
grep -n "_bump_epoch" src/agentic_dynamics/control/control_db.py
grep -n "phases_completed\|phases_total" src/agentic_dynamics/control/control_status.py | head -4
```

*Evidence.*

```
control_meta: [('schema_version', '3'), ('control_epoch', '9')]
transitions: (9,)
_bump_epoch call sites (4, not 2): control_db.py:1479 (create_run), :1565 (transition_run),
                                   :1782 (start_attempt), :1828 (finish_attempt)
control_status.py:355-393  # _phase_progress(): phases_completed/phases_total from step_attempts
```

The epoch derivation in the launched code is **per-phase**: `_bump_epoch` fires in
`start_attempt` (`:1782`) and `finish_attempt` (`:1828`) as well as `create_run`/`transition_run`,
so a run on the merged engine advances the epoch by 2 per completed phase, and the packet's
`active_runs`/`promotable_runs` entries now carry `phases_completed`/`phases_total` derived from
the `step_attempts` rows (schema fields `control_status.py:215-216`). The live counter stands at
**9 = 9 transition rows** because no post-fix run has completed a phase yet — the only full
8-phase run since e1 was committed (`run-ba8a4deda548`) launched on the pre-fix engine, and its
e0→e7 phases advanced nothing. This run (`run-5e31f69b4afa`) is the first that will move the epoch
per phase.

*Reading.* The historical clause holds (that run's recorded contribution is still 2 — the datum the
spec was built on). The derivation clause is superseded: the epoch's meaning is now "any durable
state change, run-level or phase-level", and the packet exposes phase progress. A turn-to-turn diff
during this run will show phase movement.

### Edge 5 — no pre-existing-drift guard exists

*Method.* **SUPERSEDED** — the guard exists.

```bash
ls tests/test_preexisting_drift_guard.py scripts/check_preexisting.py 2>&1
```

*Evidence.*

```
tests/test_preexisting_drift_guard.py
scripts/check_preexisting.py
```

Both files the original pin found absent now exist. The e5 guard — a named, deterministic, no-model
check that proves a failure exists at the wave's merge-base (temp worktree + run the failing test)
before the author may call it pre-existing — is merged. The mislabeling pattern the f4/f5 commits
exhibited can now be caught mechanically.

*Reading.* Superseded: the guard the original pin verified as absent is present in the launched
code.

---

## 3. Preregistered run criterion (the proof this run owes)

The verification re-run's mandate is that the e1 recorder — now in the launched code — writes real
per-phase rows for a real run. The criterion is preregistered here, measured against the SAME live
db and run_id the pin reads:

> **After this run completes, the live control db must hold, for `run-5e31f69b4afa`:
> `step_attempts >= 8` and `gate_results > 0`.**

Supporting preregistered facts:

| Fact | Method | Measured at e0 pin |
|---|---|---|
| This run's row exists and is live | `runs` + `run_heartbeats` | **PASS** — `run-5e31f69b4afa` `running`, heartbeat fresh (beat 6) |
| The evidence tables are empty at launch | `SELECT COUNT(*) FROM step_attempts/gate_results` | **PASS** — `(0,)` / `(0,)` (evidence records at phase END) |
| The recorder is bound for this run | composition root `run_workflow.py:565` + the engine seam `workflow_runner.py:3363` | **PASS** — `control_db` open + `control_run_id` minted (the run row exists) |
| Every phase self-records | `_emit_phase_evidence` runs for EVERY executed phase, any outcome | **PASS** — code read at `workflow_runner.py:3355-3372` |

---

## 4. Deviations recorded against the pinned bytes / mandate

Recorded per the D-series convention. No deviation is unexpected; each is the verification re-run's
subject or a known-stale anchor.

**D-1 — the mandate's `publish_release.py:515` anchor is stale (inherited).** The e0 mandate (and
the spec's `domain_context`) point at the `write_receipt` call at `publish_release.py:515`; the
call is at **`:436`** in this tree. This was recorded as D-1 by the original e0 pin and remains
true — the file is 499 lines. The underlying claim was verified at the real site (Edge 3).

**D-2 — the five mandate edges describe the pre-fix baseline; on merged main six clauses are
SUPERSEDED.** The e0 mandate was authored against the state the original pin measured. Launching on
merged main, the gap clauses no longer hold — each because the merged wave closed it. Recorded per
edge above with code + db evidence: Edge 1(b) e1 recorder; Edge 2(b)/(c) e2 drain command + zombie
sweep; Edge 3(a)/(b) e3 purge + `--db`-honoring receipts; Edge 4 (derivation) e4 per-phase epoch;
Edge 5 e5 guard. In a verification re-run these are the positive findings: the launch state IS the
fixed state, which is what lets this run write rows. Historical clauses (Edge 1(a), Edge 2(a),
Edge 4 record) hold unchanged.

---

## 5. Scope compliance

The phase mandate (e0 prompt): write this preregistration carrying the pin + the five verified
edges, then commit with the `[workflow] e0_pin_spec — <goal prefix>` subject.

- **Created/rewritten:** `docs/reviews/control_db_evidence_preregistration.md` (this file) — the
  re-run's pin, superseding the original run's preregistration in the tree (the original remains in
  history at `d454abd02`/`e0638c2e7`).
- **Edited:** nothing else. Every verification above is read-only — `sha256sum`, `git rev-parse`,
  `git log`, `git ls-files`, `git grep`, `grep`, and read-only `sqlite3.connect(...)` SELECTs
  against the live control db at the main checkout.
- **Not done, deliberately:** the spec's stale `:515` anchor was left unrepaired (repairing it
  would edit the very spec whose SHA256 this document pins). The `run.log` modification in the
  working tree is a runner artifact, untouched and unstaged.

---

## 6. Verdict

| # | Mandate edge (as stated) | Status at launch on merged main |
|---|---|---|
| 1a | `step_attempts`/`gate_results` are 0 for run-2bc253a8d87a | **PASS** — historical; the recorder cannot retrofit a pre-e1 run |
| 1b | `record_gate_result` has no production caller | **SUPERSEDED** — e1 recorder live (`phase_evidence.py:81` ← `workflow_runner.py:3364`) |
| 2a | the outbox's 68 rows are all DELIVERED | **PASS** — 68/68 delivered, 0 pending, 0 dead |
| 2b | no drain COMMAND exists | **SUPERSEDED** — `control drain-outbox` exists (`cli.py:113`) |
| 2c | no zombie-run sweep exists | **SUPERSEDED** — `control sweep-zombies` exists (`cli.py:114`); `run_heartbeats` table live |
| 3a | 13 deadbeef/operator-test receipts are committed | **SUPERSEDED** — purged by e3 deletion commit; 0 tracked at HEAD |
| 3b | `write_receipt` ignores `--db` | **SUPERSEDED** — honors `db_path` (`publication.py:1037`; `publish_release.py:436`) |
| 4 | `control_epoch` is 2 for an 8-phase run | **PASS** (record — that run's contribution is still 2) / **SUPERSEDED** (derivation — epoch now bumps per attempt start/finish) |
| 5 | no pre-existing-drift guard exists | **SUPERSEDED** — `scripts/check_preexisting.py` + `tests/test_preexisting_drift_guard.py` present |

**Re-run verdict: the five pre-fix gaps the original pin verified are CLOSED in the launched code —
every SUPERSEDED above is that closure, verified with code and live-db evidence, none asserted. The
three historical facts hold unchanged. No unexpected deviation.** This is exactly the launch state
the e6 adversarial review of the first run predicted: *"the first run launched after merge is the
first to populate the tables live."* This run is that run. The proof criterion is preregistered in
§3: **`step_attempts >= 8` and `gate_results > 0` for `run-5e31f69b4afa` after the run.**

The mandate is anchored: spec SHA256
`a358cde6607afd2e99adfce346a8a8d895d9f5042c51ab15f585c7918bdb0044` at git
`a5ca7988f69f028fee59fe9b678d3b68576d3d2b`, with every edge verified against the code and the live
control db — never inherited from the spec. `e1_phase_evidence` (verification) may proceed.
