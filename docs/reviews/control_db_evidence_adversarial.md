---
status: accepted
kind: adversarial
spec: control_db_evidence
phase: e6_adversarial
run: verification-rerun
run_id: run-5e31f69b4afa
reviewer_model: deepseek/deepseek-v4-pro
author_model: deepseek/deepseek-v4-flash
generated_at: 2026-09-02T13:31:58Z
---

# Adversarial review — `control_db_evidence` VERIFICATION RE-RUN (e1–e5)

**Independence.** This is the e6 phase of the VERIFICATION RE-RUN, executed by
`deepseek/deepseek-v4-pro` (a different model and session from the `deepseek/deepseek-v4-flash`
author, per the house independence convention). The role is falsification, not certification.
Every claim below was re-derived against the actual code at HEAD `d6fe6becf` and the LIVE control
database at `/home/drseuss/ai-finops-framework/experiments/results/control/control.db` — never
inherited from the author's commit messages, the spec, or the prior wave's adversarial review.

The question this review answers is narrower and sharper than the first wave's: the first run
(`run-ba8a4deda548`) committed e1 mid-flight and recorded **0 / 0** rows as an accepted limitation
(F1). This run (`run-5e31f69b4afa`) launched with the e1 recorder already in the code, so its
proof criterion is preregistered as **`step_attempts >= 8` and `gate_results > 0` for
`run-5e31f69b4afa` after the run**. The review attacks that criterion and each evidence edge.

---

## 1. Method (how each edge was attacked)

| Edge | Attack | Evidence source |
|---|---|---|
| e1 | Does the LIVE db hold per-phase rows for a REAL run? Is the write side called in the phase loop (not just testable)? **Is the preregistered criterion even satisfiable?** | code read (`workflow_runner.py`, `run_workflow.py`, `runtime/phase_evidence.py`, `control/phase_evidence.py`); live db SELECT; gate-fire audit |
| e2 | Does the drain command exist + work? Does the sweep cancel a dangling `running` row via the legitimate transition API? | code read (`control_drain_outbox.py`, `control_sweep_zombies.py`, `run_lifecycle.py`); `ALLOWED_TRANSITIONS` check |
| e3 | Is the production receipt dir hermetic? Are the deadbeef artifacts really gone from history (both waves)? | `git ls-files`, `git log -S deadbeef`; code read (`publication.py`, `publish_release.py`); live dir check |
| e4 | Does the epoch see phase progress in the LIVE db? | code read (`control_db.py`, `control_status.py`); live db epoch arithmetic |
| e5 | Can the guard be fooled (a branch-introduced failure labeled pre-existing passes the guard)? | code read (`preexisting_guard.py`, `check_preexisting.py`) |
| e7 | The harness gate green? | full gate run over the e7 list |

Test gate result (the e7 list, run fresh this phase): **499 passed, 1 failed** — the single
failure is `tests/test_publication_singular_door.py::test_readme_figures_match_public_statistics`,
a pre-existing README "By the Numbers" drift (see F5).

---

## 2. Finding table

| # | Finding | Attack | Re-verification evidence | Fix-or-record | Residual scope |
|---|---|---|---|---|---|
| **F1** | **The run's own proof criterion is unsatisfiable by a clean run: `gate_results > 0` requires a gate to FIRE, and a clean run fires none.** The recorder writes a `gate_results` row only when a gate leaves a verdict (a violation, or an `APPROVED` relabel reuse) — never for a clean gate. After six clean phases the live db holds **6 `step_attempts` / 0 `gate_results`**, and the two remaining phases (e6 agent, e7 test) will fire no gate either. The run is on track to end `step_attempts = 8, gate_results = 0` — the recorder works perfectly and the criterion still fails. | "After a REAL run, does the db hold per-phase `step_attempts` + `gate_results`?" — with the criterion itself under attack. | Live db (read-only, this phase): `step_attempts` = 6 rows for `run-5e31f69b4afa` (e0–e5, all `state='ok'`, real tokens/cost), `gate_results` = 0. Code: `runtime/phase_evidence.py` module docstring — *"A phase produces a gate-result row only when a gate actually FIRED… a gate that ran cleanly leaves nothing behind"*; `phase_gate_verdicts` maps `GATE_FIELDS = (commit_gate, relabel_gate, deploy_gate)` and returns nothing for `None`. The three gates all fire only on violations and are all **skipped for `kind == "test"`** (`workflow_runner.py`: `if kind != "test"` guards `_enforce_deploy_gate` / `_enforce_commit_prefix` / `_enforce_doc_contract`). e6 is a clean-doc commit; e7 is a test phase. Therefore `gate_results` stays 0. | **RECORD** (criterion defect in e0's preregistration, not a code defect in e1). The honest proof of the recorder is `step_attempts >= 8` **live** plus the synthetic `gate_results` proof already in `tests/test_phase_evidence.py` (`test_engine_records_two_attempt_rows_and_the_gate_results_phases_produced`). Recommend the operator amend the criterion to *`step_attempts >= 8` AND `gate_results >= 0`, where `0` is the correct null-not-zero outcome of a clean run.* | The e1-e5 author re-asserted "the criterion accrues as e1–e7 complete" at every phase (e1 through e5 verify docs) without noticing `gate_results` is structurally stuck at 0 for a clean run. The criterion as written can only be met by inducing a violation or fabricating a gate row — the exact null-not-zero violation the evidence tables exist to prevent. |
| **F2** | `start_attempt`/`finish_attempt` are recorded **atomically at phase END**; no persistent `running` `step_attempts` row ever exists, the epoch bumps by +2 only at phase **end** (not +1 at start), and `phases_completed == phases_total` in the live engine. | "Does the epoch see phase progress?" + the `start_attempt` docstring's claim that a crashing orchestrator leaves a `running` row. | `_emit_phase_evidence` runs at the very end of phase processing (after gates + checkpoint flip, `workflow_runner.py:3363`); `record_phase_evidence` writes start+finish back-to-back in ONE transaction (`control/phase_evidence.py`). Live db: all 6 rows are terminal `ok`, zero `running` rows. Epoch 21 = 9 (launch) + 12 (6 phases × +2), all at phase end. | **RECORD** (accepted limitation — carried from the first wave's F2, re-verified). | e4's core claim holds (epoch advances +2 per completed phase, turn-to-turn diff sees completion). But "phase N of M in flight" is not available: `phases_total` means "phases seen so far", not the spec's declared total; a run killed mid-phase leaves no `step_attempts` row for that phase (the run heartbeat + e2 sweep covers the dangling-row hole instead). |
| **F3** | Deadbeef receipts are gone from the **tree** but still present in **history** (8 commits across both waves). | "Are the deadbeef artifacts really gone from history (grep both waves)?" | `git ls-files experiments/results/publication/` = **0**; the production dir is **physically absent** in both this worktree and the main checkout. `git log --all -S deadbeef -- experiments/results/publication/` = **8 commits** (2× p7 `2d6692d52`/`edd0e928d`, f1 `3c5ecb885`, f3 `16bf26eeb`, f4 `63682849a`, f6 `756c3d4ab`/`ca0248992`, plus the e3 deletion `813a7de6c`). e3 chose the **documented deletion commit**, not a filter-repo rewrite. | **RECORD** (correct; the operator's deletion-vs-rewrite decision is named-not-done). | The history rewrite is a P0 permanence action on shared `origin/main` (see §4). Hermeticity itself holds: `receipt_dir_for_db` follows the `--db` override (`publication.py:996`), never the production `RECEIPT_DIR`. |
| **F4** | The e5 guard can be **fooled**: `--base` is an **unvalidated sha**, and the doc-mode checker binds no citation to a specific test. | "Can the guard be fooled (a branch-introduced failure labeled pre-existing passes the guard)?" | `prove_preexisting` resolves `base` via `_resolve_sha` (`preexisting_guard.py:162` → `git rev-parse --verify <rev>^{commit}`) and never verifies it is the true `git merge-base` with main — an author can pass `--base <their own earlier commit>` where the test fails and obtain `verdict=pre-existing`. `flag_uncited_preexisting_claims` (`:287`) only tests that **some** `verdict=pre-existing` citation exists in the doc; it never binds the citation's `test=` to the specific claimed failure. | **RECORD** (residual bypass; propose as follow-up). | The primary prove-mode guard is sound: it runs the SAME node at base and head and returns `branch-introduced` for synthetic base-pass/head-fail. The bypasses are (a) unvalidated `--base`, (b) unbound doc-mode citation. Small follow-up, not a blocker to the core mislabel-catching mechanism. |
| **F5** | The e7 harness gate is **red** on a pre-existing README drift that is out of this wave's scope but inside the gate's test list. | "The harness test gate." | `pytest` over the full e7 list = **499 passed, 1 failed**. The failure is `test_publication_singular_door.py::test_readme_figures_match_public_statistics` — README says `178 (11 experiments + 167 workflows)`, `public_statistics` computes `11 + 167 = 178` but the test asserts the canonical line is absent (the README figure drifted from the regenerated statistics). Pre-existing: `git diff main..HEAD -- README.md apps/website/data.js` is **empty** (this wave touched neither). The e3 verification already recorded this as R-1. | **RECORD** (merge-blocker). | The wave cannot record a green gate until either (a) the README "By the Numbers" block is regenerated to match `public_statistics`, or (b) the operator scopes the gate. Out of F1–F5 scope; the corpus/README drift belongs to a different wave. |

---

## 3. What passed (clean-sweep re-verification of the load-bearing claims)

These are the claims an adversarial review must actually re-verify, and each held — this is the
positive result the verification re-run exists to produce:

- **e1 write side is genuinely wired AND live — not merely testable.** `_emit_phase_evidence`
  (`workflow_runner.py:931`, invoked `:3363`) → `PhaseEvidence` → `make_phase_evidence_recorder`
  (`run_workflow.py:565`) → `record_phase_evidence` (`control/phase_evidence.py:40`) → the db's
  own `start_attempt`/`finish_attempt`/`record_gate_result` in one transaction. **The strongest
  possible proof: the LIVE db now holds 6 real `step_attempts` rows for this run**, with real
  tokens (`109832`, `128397`, `102097`, `116651`, `91085`, `93534`) and real cost (`$0.0280`,
  `$0.0334`, `$0.0298`, `$0.0273`, `$0.0230`, `$0.0245`) — written by the engine at each phase
  end, not by a test. **PASS** (subject to F1's criterion defect and F2's granularity caveat).
- **e1 verify (b)–(e)** hold in the merged tests: a failed phase records `failed` (never skipped);
  a retried phase records `attempt_no` 1 then 2; a control-db outage never fails the run (named
  warning); `--only-phase` records nothing. **PASS** (`tests/test_phase_evidence.py`).
- **e2 drain command exists + works**: `agentic-dynamics control drain-outbox` →
  `scripts/control_drain_outbox.py`, drains through the same `OutboxPublisher`, reports
  `outbox_before/after` honestly, exit 3 without a db (never creates one). **PASS**
  (`tests/test_control_drain_outbox.py`).
- **e2 zombie sweep cancels via the legitimate API**: `sweep_zombie_runs` →
  `db.transition_run(run.run_id, RunState.CANCELLED, reason=…, actor=…)` at `run_lifecycle.py:237`
  — the `ALLOWED_TRANSITIONS`-governed API, never raw SQL. Three-valued liveness (live/zombie/
  unknown); a live run with a fresh heartbeat is untouched. Live db corroborates: the two killed
  runs (`run-d61ec458cb6b`, `run-0aeb16f0d855`) sit `cancelled` via `transition_run`. **PASS**
  (`tests/test_run_lifecycle.py`).
- **e3 hermeticity**: `write_receipt(receipt, db_path=…)` archives beside the tmp db, never the
  production `RECEIPT_DIR`; the production dir is physically absent in both checkouts; the guard
  test + negative control hold. **PASS** (`tests/test_publish_release.py`) — subject to F3's
  history purge being named-not-done.
- **e4 epoch + packet**: `_bump_epoch` fires in `start_attempt`/`finish_attempt`
  (`control_db.py:1782`/`:1828`) as well as `create_run`/`transition_run`, while
  `record_run_heartbeat` never does. **Live arithmetic confirms it**: launch epoch 9 → now 21 =
  +12 for 6 phases (+2 each), while the heartbeat advanced to beat 80 without moving the epoch
  (epoch-neutral). The packet's `active_runs` entry carries `phases_completed`/`phases_total`
  from `step_attempts`. **PASS** (subject to F2's granularity caveat).
- **e5 prove-mode guard**: deterministic, model-free, and the README-drift claim was re-proven
  live by the guard (base FAIL + head FAIL → `pre-existing`, exit 0). **PASS** (subject to F4's
  `--base`/doc-mode bypasses).

---

## 4. Release verdict

**Not merge-ready to `main` as-is.** The code deliverables e1–e5 are correct and well-tested,
and — for the first time — the load-bearing claim is TRUE on a live database: this run is
writing real per-phase `step_attempts` rows (6/6 so far, on track for 8). Three blockers stand
between this worktree and the permanence gate:

1. **The run's own proof criterion `gate_results > 0` will be UNSATISFIED at run end (F1).**
   Not because the recorder is broken — because the criterion is mis-specified. A clean run
   fires no gate, and `gate_results = 0` is the correct null-not-zero outcome. The operator must
   amend the criterion or accept `step_attempts >= 8` + the synthetic `gate_results` test as the
   proof; otherwise the re-run "fails" its own preregistration despite doing everything right.
2. **The e7 harness gate is red (F5)** — `test_readme_figures_match_public_statistics` (README
   drift), pre-existing and out of this wave's scope, but mechanically fail-closed.
3. **The history purge is unresolved (F3)** — deadbeef receipts are out of the tree but still in
   the two waves' reachable history.

**P0 actions the operator must take after merge (named, not done by this wave):**

1. **The history-purge decision.** The 13 deadbeef/operator-test receipts remain in the pushed,
   shared history of both waves (8 commits). The e3 author chose the deletion-commit (tree
   purge). Excising them from history is a **filter-repo rewrite of shared `origin/main`** — a
   P0 permanence action the operator alone decides (rewrite vs. accept the noise). *Not done.*
2. **The publication-gate arming.** Confirm the production `experiments/results/publication/`
   holds no `deadbeef`/`operator-test` artifacts and that the hermetic guard
   (`test_production_receipt_dir_is_hermetic`) is live in the suite/CI so a test can never write
   into a production path again. The code exists; arming it in production is the operator's step.
   *Not done.*
3. **The README "By the Numbers" drift** (prerequisite to a green e7 gate, F5). Regenerate the
   block to match `public_statistics` (the drift is pre-existing and out of F1–F5 scope — an
   operator decision). *Not done.*
4. **Amend or reinterpret the run criterion `gate_results > 0`** (F1) so the re-run's proof is
   recorded honestly rather than left as an unmet clause. *Not done.*

**Accepted limitations (recorded, not themselves blocking the merge decision by themselves):**
F2 (epoch/progress granularity is completion-only), F4 (doc-mode citation not bound to the claim;
`--base` unvalidated — small follow-ups).

---

## 5. Log

| Phase | Edge | Verdict |
|---|---|---|
| e1 | write side wired + LIVE (6 real `step_attempts` rows); criterion `gate_results > 0` unsatisfiable by a clean run | PASS with recorded finding (F1) |
| e2 | drain command + zombie sweep via legitimate `transition_run` API | PASS |
| e3 | hermeticity + tree purge; history purge named-not-done | PASS with recorded finding (F3) |
| e4 | epoch + packet phase-progress, live (+2/phase, epoch 9→21) | PASS with recorded finding (F2) |
| e5 | prove-mode guard sound; `--base`/doc-mode bypasses | PASS with recorded finding (F4) |
| e7 | harness gate | **FAIL** (1 pre-existing failure, F5) |

**Verdict: FAIL — merge-blocked on the mis-specified run criterion (F1), the red e7 gate (F5,
pre-existing README drift), and the unresolved history-purge P0 decision (F3).** Findings: 5
(F1–F5). Zero code defects in the e1–e5 deliverables; the load-bearing e1 claim is now TRUE live
(real per-phase rows); one criterion defect recorded (F1), one merge-blocking gate failure (F5),
one named-not-done P0 decision (F3), two accepted limitations (F2, F4).
