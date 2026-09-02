---
status: accepted
kind: adversarial
spec: control_db_evidence
phase: e6_adversarial
reviewer_model: deepseek/deepseek-v4-pro
author_model: deepseek/deepseek-v4-flash
generated_at: 2026-09-02T10:00:00Z
---

# Adversarial review — `control_db_evidence` (e1–e5)

**Independence.** This is the e6 phase, run by `deepseek/deepseek-v4-pro` (a different model
and session from the `deepseek/deepseek-v4-flash` author, per the house independence
convention). The role is falsification, not certification. Every claim below was re-derived
against the actual code at `HEAD` (`29f9d65f2`) and the LIVE control database at
`/home/drseuss/ai-finops-framework/experiments/results/control/control.db` — never inherited
from the author's commit messages or the spec.

---

## 1. Method (how each edge was attacked)

| Edge | Attack | Evidence source |
|---|---|---|
| e1 | Is the write side actually called in the phase loop (not just testable)? Does the live db hold per-phase rows? | code read (`workflow_runner.py`, `run_workflow.py`, `phase_evidence.py`); strongest synthetic (`tests/test_phase_evidence.py`); live db SELECT |
| e2 | Does the drain command exist + work? Does the sweep cancel a dangling `running` row via the legitimate transition API? | code read (`control_drain_outbox.py`, `control_sweep_zombies.py`, `run_lifecycle.py`); `ALLOWED_TRANSITIONS` check; tests |
| e3 | Is the production receipt dir hermetic against the suite? Are the deadbeef artifacts gone from history (both waves)? | `git ls-files`, `git log -S deadbeef --all`; code read (`publication.py`, `publish_release.py`); tests |
| e4 | Does the epoch see phase progress in the live db? Does the packet expose phase-progress? | code read (`control_db.py`, `control_status.py`); live db; tests |
| e5 | Can the guard be fooled (a branch-introduced failure labeled pre-existing passes the guard)? | code read (`preexisting_guard.py`); empirical probe of the doc-mode checker |
| e7 | The harness gate green? | full gate run (`pytest` over the e7 list) |

Test gate result (the e7 list, run fresh): **499 passed, 1 failed** — the single failure is
`tests/test_doc_lifecycle.py::test_readme_spec_counts_match_index`, a pre-existing README
spec-count drift (see F5).

---

## 2. Finding table

| # | Finding | Attack | Re-verification evidence | Fix-or-record | Residual scope |
|---|---|---|---|---|---|
| F1 | The live control db holds **0** `step_attempts` / **0** `gate_results` for the current run, despite a correctly-wired write side. | "After a REAL run, does the db hold per-phase rows?" | Live db: `step_attempts=(0,)`, `gate_results=(0,)`, `schema_version=2`, no `run_heartbeats` table, `run-ba8a4deda548` (this run) still `running`. **BUT** the write side IS called in the phase loop: `_emit_phase_evidence` invoked at `workflow_runner.py:3363-3364`, recorder injected at `run_workflow.py:565`, writer composes `start_attempt`→`finish_attempt`+`record_gate_result` in one transaction (`control/phase_evidence.py:64-92`). Strongest synthetic `test_engine_records_two_attempt_rows_and_the_gate_results_phases_produced` runs the REAL engine + REAL writer + REAL db and asserts real rows. | RECORD (accepted limitation) | The orchestrator is a single in-process pipeline launched **before** e1 was committed; it never reloads its modules, so this run executes pre-e1 code. The first run launched after merge is the first to populate the tables live. Not a code defect. |
| F2 | `start_attempt`/`finish_attempt` are recorded **atomically at phase END**; the epoch and `phases_total` therefore only move at completion — the "in-flight phase" granularity is dead code in the engine path. | "Does the epoch see phase progress?" + the `start_attempt` docstring claim "an attempt that crashes the orchestrator still leaves a `running` row". | `_emit_phase_evidence` runs at the very end of phase processing (after gates + checkpoint flip); `record_phase_evidence` writes start+finish back-to-back in one transaction. So (a) no persistent `running` step_attempt row ever exists, (b) the epoch bumps by 2 only at phase **end** (not 1 at start), (c) `phases_completed == phases_total` always in the live engine. The e4 test `test_active_run_carries_phase_progress_derived_from_step_attempts` demonstrates `1/2` only by calling `start_attempt`/`finish_attempt` **separately** — a call pattern the engine never makes. | RECORD (accepted limitation) | e4's core claim **holds** (epoch advances per phase = 2/phase, not only on run-state); a turn-to-turn diff sees completion. But "phase N of M" is not available: `phases_total` means "phases seen so far", not the spec's declared total; a run killed mid-phase still leaves no `step_attempts` row for that phase (the run-level heartbeat + zombie sweep of e2 covers the dangling-row hole instead). |
| F3 | Deadbeef receipts are gone from the **tree** but still present in **history** (8 commits across both waves). | "Are the deadbeef artifacts really gone from history (grep both waves)?" | `git ls-files experiments/results/publication/` = **0**. `git log --all -S deadbeef -- experiments/results/publication/` = **8 commits** (2× p7 + 5× followups f-wave + the e3 deletion commit). The e3 commit body records the choice: **documented deletion commit, not a filter-repo rewrite**, because the introducing commits are already merged into shared `origin/main` history. | RECORD (correct; the operator decision is named-not-done) | The history rewrite is a P0 permanence action (see §4). Hermeticity itself is verified: `receipt_dir_for_db` follows the `--db` override (`publication.py`), and the suite is proven hermetic (guard test + negative control both pass). |
| F4 | The e5 doc-mode guard can be fooled: a `verdict=pre-existing` citation is **not bound to the specific test** it licenses, and `--base` is an **unvalidated** sha. | "Can the guard be fooled (a branch-introduced failure labeled pre-existing passes the guard)?" | The PROVE mode is sound: it runs the SAME node at base and head and correctly returns `branch-introduced` for synthetic base-pass/head-fail (tested + confirmed; I also ran it live against the README drift and it returned the correct `pre-existing`). BUT the doc-mode `flag_uncited_preexisting_claims` only tests that **some** `verdict=pre-existing` citation exists. Empirical probe: a claim "test_readme_spec_counts_match_index is pre-existing drift" + a citation for `tests/test_other.py::test_other` returns `[]` (accepted). `prove_preexisting` resolves any rev the caller passes (`_resolve_sha`) and never verifies it is the true `git merge-base` with main — an author can pass `--base <their own earlier commit>` and obtain `pre-existing`. | RECORD (residual bypass; propose as follow-up) | The primary prove-mode guard is sound and the mislabel fails mechanically **when the true merge-base is supplied**. The doc-mode wiring and the unvalidated `--base` are the two bypasses. Fixing them (bind citation `test=` to the claim; compute/verify the merge-base) is a small follow-up, not a blocker. |
| F5 | The e7 harness gate is **red** on a pre-existing README spec-count drift that is out of this wave's scope but inside the gate's test list. | "The harness test gate." | `pytest` over the e7 list = **499 passed, 1 failed**. The failure is `test_doc_lifecycle.py::test_readme_spec_counts_match_index` (README `178 (11+167)` vs index `180 (11+169)`; ground truth = 169 workflow YAMLs). Verified pre-existing: at base `fb48b889c` the same test FAILS (index `n_specs=180`, README `178`), and this wave did **not** touch `README.md` or `experiments/specs/index.json` (empty diff). The e5 guard confirms `verdict=pre-existing`. | RECORD (merge-blocker) | The wave cannot record a green gate until either (a) `README.md:96` is corrected to `180 (11 experiments + 169 workflows)` (one line), or (b) the operator scopes the gate. Out of F1–F5 scope; introduced by the earlier followups wave. |

---

## 3. What passed (clean-sweep re-verification of the load-bearing claims)

These are the claims an adversarial review must actually re-verify, and each held:

- **e1 write side is genuinely wired, not merely testable.** `_emit_phase_evidence` (`workflow_runner.py:931`, invoked `:3363`) → `PhaseEvidence` → `make_phase_evidence_recorder` (`run_workflow.py:565`) → `record_phase_evidence` (`control/phase_evidence.py:40`) → the db's own `start_attempt`/`finish_attempt`/`record_gate_result`. The strongest synthetic runs the full engine. **PASS** (subject to F1's live-db caveat).
- **e1 verify (b)-(e) all hold**: a failed phase records `failed` (never skipped); a retried phase records `attempt_no` 1 then 2; a control-db outage never fails the run (named warning); `--only-phase` (no run row) records nothing. **PASS** (`tests/test_phase_evidence.py`, 12/12).
- **e2 drain command exists + works**: `agentic-dynamics control drain-outbox` → `control_drain_outbox.py`, drains through the same `OutboxPublisher`, reports `drained` + `outbox_before/after` honestly, never creates the db (exit 3), and a stream outage leaves rows `pending` (never lies). **PASS** (`tests/test_control_drain_outbox.py`, 8/8).
- **e2 zombie sweep cancels via the legitimate API**: `sweep_zombie_runs` → `db.transition_run(run, CANCELLED, ...)`; `running→cancelled ∈ ALLOWED_TRANSITIONS` (verified). A live run with a fresh heartbeat is untouched; an `unknown` (no heartbeat) run is reported, never guessed. **PASS** (`tests/test_run_lifecycle.py`, 12/12).
- **e3 hermeticity**: `write_receipt(receipt, db_path=...)` archives beside the tmp db, never the production `RECEIPT_DIR`; the publish-path test leaves the production dir byte-identical; the guard test + its negative control both hold. **PASS** (`tests/test_publish_release.py`, 12/12).
- **e4 epoch + packet**: `start_attempt`/`finish_attempt` bump the epoch (`control_db.py`); the packet's `active_runs`/`promotable_runs` entries carry `phases_completed`/`phases_total` derived from `step_attempts`; determinism and schema validation hold. **PASS** (subject to F2's granularity caveat).
- **e5 prove-mode guard**: deterministic, model-free (import graph audited by `test_guard_module_performs_no_model_calls`), and the README-drift claim was re-proven by running the guard live (base FAIL + head FAIL → `pre-existing`, exit 0). **PASS** (subject to F4's doc-mode/`--base` bypasses).

---

## 4. Release verdict

**Not merge-ready to `main` as-is.** The code deliverables e1–e5 are correct and well-tested
(all targeted suites green), and the load-bearing claims above re-verify clean. Two blockers
stand between this worktree and the permanence gate:

1. **The e7 harness gate is red** — `test_doc_lifecycle.py::test_readme_spec_counts_match_index`
   (F5). Pre-existing, out of scope, but mechanically fail-closed.
2. **The history purge is unresolved** — the deadbeef receipts are out of the tree but still in
   the two waves' history (F3).

**P0 actions the operator must take after merge (named, not done by this wave):**

1. **The history-purge decision.** The 13 deadbeef/operator-test receipts remain in the pushed,
   shared history of both waves (8 commits). The e3 author chose the deletion-commit (tree
   purge). Excising them from history is a **filter-repo rewrite of shared `origin/main`** —
   a P0 permanence action the operator alone decides (rewrite vs. accept the noise in history).
   *Not done.*
2. **The publication-gate arming.** Confirm the production `experiments/results/publication/`
   holds no `deadbeef`/`operator-test` artifacts and that the hermetic guard
   (`test_production_receipt_dir_is_hermetic`) is live in the suite/CI so a test can never write
   into a production path again. The code exists; arming it in production is the operator's step.
   *Not done.*
3. **The README spec-count drift** (pre-requisite to a green gate, F5). Correct
   `README.md:96` (`178 (11+167)` → `180 (11+169)`, matching the 169 workflow YAMLs) or scope
   the e7 gate — an operator decision, since the drift is pre-existing and out of this wave's
   F1–F5 scope. *Not done.*

**Accepted limitations (recorded, not blocking the merge decision by themselves):**
F1 (the live db cannot self-evidence this run — architectural), F2 (epoch/progress granularity
is completion-only), F4 (doc-mode citation not bound to the claim; `--base` unvalidated —
small follow-ups).

---

## 5. Log

| Phase | Edge | Verdict |
|---|---|---|
| e1 | write side wired + synthetically proven; live db 0 rows (stale process) | PASS with recorded limitation (F1) |
| e2 | drain command + zombie sweep via legitimate API | PASS |
| e3 | hermeticity + tree purge; history purge named-not-done | PASS with recorded limitation (F3) |
| e4 | epoch + packet phase-progress | PASS with recorded limitation (F2) |
| e5 | prove-mode guard; doc-mode/`--base` bypasses | PASS with recorded limitation (F4) |
| e7 | harness gate | **FAIL** (1 pre-existing failure, F5) |

**Verdict: FAIL — merge-blocked on the e7 gate (pre-existing README drift) and the unresolved
history-purge P0 decision.** Findings: 5 (F1–F5); zero code defects in the e1–e5 deliverables,
three accepted limitations recorded, one merge-blocking gate failure, one named-not-done P0
decision.
