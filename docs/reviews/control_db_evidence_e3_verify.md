---
status: accepted
kind: verification
spec: control_db_evidence
phase: e3_hermetic_publication
run: verification-rerun
run_id: run-5e31f69b4afa
author_model: deepseek/deepseek-v4-flash
generated_at: 2026-09-02T13:11:41Z
---

# e3 phase verification — hermetic publication + the deadbeef purge on merged main

**What this phase is.** The e3 mandate (spec `control_db_evidence`, phase `e3_hermetic_publication`)
says provenance must become provenance again: (a) the receipt directory is injectable end-to-end —
`write_receipt` (and `publish_release`'s call, cited at `:515`) honors the same override the `--db`
flag provides, so the receipt archive follows the db path's tmp override and never the production
`RECEIPT_DIR`; (b) the test suite is hermetic — operator-test receipts land in tmp dirs, and a guard
test asserts the production `experiments/results/publication/` holds NO deadbeef/operator-test
artifacts after the suite runs; (c) the 13 committed deadbeef/operator-test receipts are purged from
both waves' history by a rewrite or, at the operator's recorded preference, a documented deletion
commit — with the choice and its why recorded in the spec.

On this VERIFICATION RE-RUN the phase executes against merged main (`a5ca7988f…`, worktree HEAD
`d9a02194d…`), where the original run's e3 deliverable (`813a7de6c`) is already the launched code —
its diff is byte-identical at this HEAD, because this branch's only differences from main are the
e0-e2 review documents (`docs/reviews/control_db_evidence_{preregistration,e1_verify,e2_verify}.md`)
and the runner's `run.log`. The mandate therefore reduces to PROOF, not re-implementation: is the
receipt-path injection present and SHAPE-compliant, is the suite hermetic, is the purge real in the
committed tree and its decision recorded? This document records the proof. **No source or test file
was modified in this phase** — the deliverable was verified, and the scope fence (the receipt-path
injection + the hermetic tests + the purge ONLY) held by construction.

---

## 1. The deliverable is present in the launched code, SHAPE-compliant

| SHAPE requirement | Where it holds (launched code at HEAD `d9a02194d`, source identical to merged main) |
|---|---|
| **(a)** `write_receipt` honors the override the `--db` flag provides — the receipt archive follows the db path, never the production `RECEIPT_DIR` | `publication.py:1021` — `def write_receipt(receipt, *, directory=None, db_path=None)`; the body (`:1037`) resolves `target_dir = Path(directory) if directory is not None else receipt_dir_for_db(db_path)`, creates it (`:1038`), and writes the content-addressed `publication_<sha16>.json` there (`:1039-1040`). `directory=` wins when given (the raw injection); otherwise the archive is DERIVED from `db_path` via the new resolver `receipt_dir_for_db` (`publication.py:996`). |
| The resolver keys on the EXPLICIT `--db`, not the env override | `publication.py:996-1018` — with `db_path is None` (or resolving to the production `CONTROL_DB_PATH`) the archive is the production `RECEIPT_DIR` (unchanged behaviour); an explicit `--db` pointing the database elsewhere — a test's tmp db, an operator's restored copy — redirects the archive to a sibling `publication/` beside that db, NEVER the production archive. Deliberately NOT keyed on `FINOPS_CONTROL_DB` (`:1008-1011`): the env override redirects a containerized orchestrator's whole session without meaning "this is not a real publication". |
| `publish_release`'s call honors the same override end-to-end | `publish_release.py:436` — `receipt_path = pub.write_receipt(receipt, db_path=args.db)`. (The mandate's code anchor `:515` is stale — D-1, inherited from the original pin; the call is at `:436` in this 499-line file.) The step-7 emit tolerates an archive outside the repo root (`:437-442`), so a suite run's tmp-db redirect prints honestly instead of raising on `relative_to`. |
| **(b)** Operator-test receipts land in tmp dirs; a hermeticity GUARD test asserts the production dir holds no deadbeef/operator-test artifacts | `tests/test_publish_release.py:228-242` — `_operator_test_artifacts(directory)` flags any `publication_*.json` under a dir whose text carries `"deadbeef"` or `"operator-test"` (the suite's fingerprints: monkeypatched HEAD + fixture operator). The hermetic family: `test_write_receipt_honors_an_injected_directory` (`:245`), `test_write_receipt_follows_the_db_override` (`:255`), `test_publish_run_does_not_touch_the_production_receipt_dir` (`:271` — before/after snapshot of the production dir), the guard's NEGATIVE control `test_operator_test_guard_flags_a_deadbeef_receipt` (`:296`), and the GUARD itself `test_production_receipt_dir_is_hermetic` (`:316`). |
| **(c)** The 13 committed deadbeef receipts are purged — the operator's rewrite-vs-deletion choice made AND recorded | The purge is a **documented deletion commit** (`813a7de6c`): at its parent exactly **13** receipts were tracked under `experiments/results/publication/`; the commit deletes all 13 (the D entries) and records the approach + why in its body — the receipts' introducing commits (the p7 commits of the publication wave and the f1/f3/f4/f6 commits of the followups wave) are already merged into shared `origin/main`, so a filter-repo excision of pushed, shared, multi-worktree history is a **P0 permanence action that belongs to the controller at the permanence gate**, not to an implementation phase; the deletion commit removes the noise from the tree going forward, the hermetic guard makes re-commitment a test failure, and the deeper rewrite stays named-not-done. The choice is re-recorded in the preregistration Edge 3 (`control_db_evidence_preregistration.md:280-284`) and re-recorded in §3 below — the spec's "record which and why" is satisfied three times over. |

## 2. VERIFY (a)–(d) — proven by the merged tests, run fresh

All commands ran against this worktree at HEAD `d9a02194d`, `-p no:cacheprovider`.

| Point | Test(s) / command | Result |
|---|---|---|
| (a) running the publish_release suite leaves the production receipt dir untouched (before/after `ls` identical) | `test_publish_run_does_not_touch_the_production_receipt_dir` asserts a full non-dry-run publish path leaves `RECEIPT_DIR` byte-identical AND lands its receipt beside the tmp db (`assert len(list((tmp_path / "publication").glob(...))) == 1`). Fresh run: the production dir at this tree (`experiments/results/publication/`, = `pub.RECEIPT_DIR` via `core.paths.PROJECT_ROOT` → `publication.py:80`) was **absent before the suite ran and absent after** — `ls` before == `ls` after (both empty); the full `test_publish_release.py` run grew no file there. | pass |
| (b) `write_receipt` honors the injected directory | `test_write_receipt_honors_an_injected_directory` (`directory=archive` → `path.parent == archive`) and `test_write_receipt_follows_the_db_override` (`db_path=<tmp>/control.db` → `path.parent == <tmp>/publication`, and `_operator_test_artifacts(pub.RECEIPT_DIR) == []`). Both fresh-ran green. | pass |
| (c) the guard test fails if a deadbeef receipt appears in the production dir | `test_operator_test_guard_flags_a_deadbeef_receipt` — the guard's negative control: it plants a `repo_sha deadbeef / operator operator-test` receipt into a FAKE production dir, points `pub.RECEIPT_DIR` at it, and asserts the SAME assertion the guard test uses raises `AssertionError` (match "operator-test artifacts"). It passes because the guard is load-bearing. | pass (guard proven non-vacuous) |
| (d) after the purge, no committed receipt carries deadbeef/operator-test (grep the history) | See §3 — `git ls-files` and `git grep` over the committed tree return zero; the deep-history ADD commits remain reachable by deletion design, which is the operator's recorded choice. | pass (tree clean; deep rewrite recorded as the controller's named-not-done) |

Command results (all run fresh this phase):

```
python3 -m pytest tests/test_publish_release.py -q -p no:cacheprovider
  → 12 passed in 0.49s          (the full publish_release suite: operator guard, candidate
                                 identity, missing-db exit 3, stale-projection refusal, HTML
                                 consistency, dry-run full sequence, failed-deploy recording,
                                 and the five e3 hermeticity tests incl. the guard + its negative)
python3 -m pytest tests/test_publication_singular_door.py -q -p no:cacheprovider
  → 6 passed, 1 failed          (see §5 — the one failure is a pre-existing README drift,
                                 unrelated to hermeticity, out of e3's scope fence)
```

## 3. The purge is real in the committed tree; the production dir is clean at both checkouts

*Method (the exact greps the preregistration pins).*

```bash
git ls-files experiments/results/publication/ | wc -l
git grep -l "deadbeef\|operator-test" -- experiments/results/publication/
git log --all --diff-filter=A --format='%h %s' -- 'experiments/results/publication/*.json'
git log --all --diff-filter=D --format='%h %s' -- 'experiments/results/publication/*.json'
```

*Evidence (at HEAD `d9a02194d`).*

```
0                                            # files tracked under experiments/results/publication/
(no output)                                  # no committed file carries deadbeef|operator-test
813a7de6c                                    # the ONLY deletion — the e3 purge commit (13 D entries)
ADD commits (7, both waves — all pre-purge):
  2d6692d52 edd0e928d  [workflow] p7_adversarial        (the publication wave)
  3c5ecb885            [workflow] f1_resume_repoint
  16bf26eeb 72b0ec504  [workflow] f3_dry_run_no_touch   (the followups wave)
  63682849a            [workflow] f4_portal_repoint
  756c3d4ab ca0248992  [workflow] f6_adversarial
```

- **The committed tree is clean.** At the e3 purge commit's parent exactly **13** deadbeef receipts
  were tracked (`publication_17cd5d52…`, `…310ad8c4…`, `…4f84ef30…`, `…53573b19…`, `…5671b189…`,
  `…68b8d9a1…`, `…83afead5…`, `…8c69db1a…`, `…90cb2cf2…`, `…9b981d32…`, `…b086c747…`,
  `…b6b1d31c…`, `…d7392b69…` — all carrying `"repo_sha": "deadbeef", "operator": "operator-test"`).
  `813a7de6c` deleted all 13. Zero receipts are tracked at this tree and `git grep` finds no
  deadbeef/operator-test file content under the directory. Re-commitment is now a guard-test
  failure (`test_production_receipt_dir_is_hermetic`).
- **The deep-history ADD commits remain reachable — by the operator's recorded design.** A
  deletion commit preserves history: the 7 introducing commits above are still in `main`'s reachable
  history. The e3 purge chose deletion over a filter-repo rewrite and recorded why (P0 permanence
  action on shared `origin/main`, controller-owned; recorded in `813a7de6c`'s body and the
  preregistration's Edge 3). The full rewrite therefore remains **named-not-done for the controller
  at the permanence gate** — this verification re-run does not change that standing decision; it
  re-confirms it is the launch state and is recorded.
- **The production dir is physically clean at both checkouts.** `experiments/results/publication/`
  does not exist at this worktree NOR at the main checkout
  (`/home/drseuss/ai-finops-framework/experiments/results/publication/`): no real publication has
  re-created it since the purge, and nothing in it carries the suite's fingerprints. The hermetic
  guard therefore asserts over a genuinely empty production archive, and the suite run proved it
  stays that way.

## 4. The deliverable is LIVE for this run — the hermeticity contract holds as the run writes rows

Read from the live control db at `/home/drseuss/ai-finops-framework/experiments/results/control/control.db`
at `2026-09-02T13:10Z` (this phase's window), read-only:

```
runs:           run-5e31f69b4afa  control_db_evidence  running
step_attempts:  [('e0_pin_spec', 1, 'ok'), ('e1_phase_evidence', 1, 'ok'),
                 ('e2_drain_and_lifecycle', 1, 'ok')]
gate_results:   0
run_heartbeats: run-5e31f69b4afa · beat 45 · actor orchestrator
control_epoch:  15
```

The run's own evidence continues to accrue on the merged engine — three fully-populated
`step_attempts` rows (`e0`/`e1`/`e2`, all `ok`), the heartbeat beating, the epoch moving per phase.
`gate_results` is 0 for the correct reason: the e0-e2 phases fired no gate, and a clean phase
produces no fabricated row. The preregistered run-level criterion (`step_attempts >= 8`,
`gate_results > 0` for this run_id) stays on track; e3's own row is appended when this phase ends.
None of this run's engine writes touches a production receipt path — the publication transaction is
not part of a workflow run, and the suite that exercises it is provably hermetic (§2).

## 5. Residuals

**R-1 (pre-existing, out of e3 scope, recorded not fixed):**
`test_publication_singular_door.py::test_readme_figures_match_public_statistics` fails — the README
"By the Numbers" row `| Experiment + workflow specs | 180 (11 experiments + 169 workflows) |`
(`README.md:96`) drifts from `public_statistics` in the committed `apps/website/data.js`
(`workflow_specs: 167` → the test's expected total `178 (11 experiments + 167 workflows)`). This is
spec-count corpus drift, the same class the original e3 commit recorded as a residual
(`test_doc_lifecycle` README spec count) — it is NOT a hermeticity defect and NOT touched by the
e3 mandate's fence. Proof it is pre-existing at this run's merge-base: `git diff main..HEAD --
README.md apps/website/data.js` is empty (the whole verification branch changed only
`docs/reviews/*` + `run.log`), so the failure is byte-identical at `a5ca7988f` — the e5 guard would
classify it `pre-existing`. It is left for the wave that owns corpus/README drift; e7's test gate
will record it independently.

## 6. Scope fence

- **Changed:** `docs/reviews/control_db_evidence_e3_verify.md` (this verification record) — one
  file. No source, no tests, no spec, no workflow YAML were modified.
- **Not done, deliberately:** no re-implementation of the receipt-path injection (it is the merged
  launch state; editing it would undermine the run's premise), no new hermetic tests (the merged
  family covers every VERIFY point and runs green), no history rewrite (the deletion-vs-rewrite
  decision was the operator's, was made at the original e3, and is recorded; the deeper filter-repo
  rewrite of shared `origin/main` history is a P0 permanence action for the controller at the
  permanence gate, named not done), no fix of R-1 (out of fence — corpus/README drift, not
  publication hermeticity). No live control-db row was mutated: all live reads were read-only.

## 7. Verdict

**PASS.** The e3 deliverable — the injectable receipt path, the hermetic publish_release suite, and
the purge — is present in the launched code, matches the SHAPE point for point (`write_receipt`
honors both `directory=` and `db_path=`; `publish_release.py:436` passes `db_path=args.db`, so an
operator-test run archives beside its tmp db, never the production `RECEIPT_DIR`; the guard + its
negative control pin the production dir clean), and is proven in BOTH directions by the merged unit
tests run fresh (12/12 `test_publish_release.py`). The purge is real in the committed tree: 0
tracked receipts under `experiments/results/publication/` at HEAD, the 13 deadbeef/operator-test
receipts removed by the single recorded deletion commit `813a7de6c`, the production archive
physically absent and untouched by the suite at both this worktree and the main checkout. The
rewrite-vs-deletion decision is recorded (deletion chosen; the deeper rewrite of shared history
remains the controller's P0 permanence action, named not done). The one red sibling test is
pre-existing README corpus drift, out of fence and recorded in §5. The preregistered run-level
criterion (`step_attempts >= 8`, `gate_results > 0` for `run-5e31f69b4afa`) continues to accrue by
the run's own engine writes as phases e3–e7 complete.
