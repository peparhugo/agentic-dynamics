---
status: accepted
kind: verification
spec: control_db_evidence
phase: e5_preexisting_guard
run: verification-rerun
run_id: run-5e31f69b4afa
author_model: deepseek/deepseek-v4-flash
generated_at: 2026-09-02T13:22:00Z
---

# e5 phase verification — the pre-existing-drift guard on merged main

**What this phase is.** The e5 mandate (spec `control_db_evidence`, phase `e5_preexisting_guard`)
says "pre-existing" must be PROVEN, not claimed: add a named guard that, given a failing test and
a merge-base, proves the failure exists at the merge-base (checkout the base in a temp worktree,
run the failing test, observe the same failure) BEFORE the author may call it pre-existing; wire
it so review phases and the operator's branch review can invoke it — a "pre-existing" claim in a
review doc must cite the guard's evidence (base sha, test, before/after outcome). The guard itself
is deterministic and fast (a single test, a temp worktree, no model calls). VERIFY (a)-(d): (a)
the guard passes when the failure genuinely exists at the merge-base; (b) the guard FAILS when the
failure is branch-introduced — the mislabeling pattern is caught mechanically; (c) no model calls,
deterministic, sub-minute; (d) a review doc citing the guard's evidence is accepted, one claiming
"pre-existing" without it is flagged.

On this VERIFICATION RE-RUN the phase executes against merged main (worktree HEAD `0bcae03c8`,
launched from main `a5ca7988f`), where the original run's e5 deliverable (`29f9d65f2`) is already
the launched code. All seven files that e5 touched are **byte-identical at this HEAD** —
`git diff 29f9d65f2 HEAD` over `scripts/check_preexisting.py`, `src/agentic_dynamics/runtime/
preexisting_guard.py`, `src/agentic_dynamics/runtime/__init__.py`, `src/agentic_dynamics/cli.py`,
`tests/test_preexisting_drift_guard.py`, `tests/test_cli_resolution.py`, `scripts/CONTEXT.md` is
empty, because no later commit (e6 or the merge) touched them. This branch's only differences from
main are the e0-e4 review documents and the runner's `run.log`. The mandate therefore reduces to
PROOF, not re-implementation: is the guard present and SHAPE-compliant, do the merged tests prove
both directions, does the wiring let a review invoke it, is it LIVE for this run? This document
records the proof. **No source or test file was modified in this phase** — the deliverable was
verified, and the scope fence held by construction.

---

## 1. The deliverable is present in the launched code, SHAPE-compliant

| SHAPE requirement | Where it holds (launched code at HEAD `0bcae03c8`, byte-identical to merged main's e5 `29f9d65f2`) |
|---|---|
| A named check that proves a failure exists at a merge-base BEFORE the author may call it pre-existing | `runtime/preexisting_guard.py` — `prove_preexisting` (`:200`): resolves `base` and `head` shas, checks each out into a **temporary git worktree** (`_worktree_at` `:167`, always cleaned up), runs the **SAME pytest node** on each tree through `runtime.test_runner.run_suite`, and classifies each outcome (`_classify` `:183`). The verdict is a pure function of the two pytest runs. CLI: `scripts/check_preexisting.py` (`agentic-dynamics validate preexisting`). |
| The claim is allowed iff the guard passes | Verdict gate (`:64-69`): `pre-existing` (base FAIL + head FAIL) is the ONLY verdict that lets the author call the failure pre-existing. `branch-introduced` (base PASS or ABSENT + head FAIL), `not-failing` (no head failure), and `unverifiable` (the base tree could not run the node) all REFUSE the claim — exit `1`; an unverifiable claim is fail-closed, never a pass. Exit codes in `check_preexisting.py`: `0` = proven pre-existing (author MAY cite), `1` = claim refused, `2` = usage/guard error. |
| Review-doc citation requirement — the claim "pre-existing" must cite the guard's evidence | The guard prints one machine line — `preexisting-guard-evidence: verdict=... base=<sha> head=<sha> test=<node> before=FAIL after=FAIL` (`EVIDENCE_MARKER` `:74`, `citation()` `:125`, round-trip parse `from_citation` `:133`). The doc-side of the rule is `flag_uncited_preexisting_claims` (`:287`): it reads a review doc's text and flags every line that makes a pre-existing CLAIM (token + a failure-context token on the same line, negation-aware — "not pre-existing" is a denial, never flagged) unless the doc embeds a valid `verdict=pre-existing` citation. CLI: `--doc <review.md>` (`check_preexisting.py:155`). |
| Deterministic, fast, no model calls | The import graph is audited by `test_guard_module_performs_no_model_calls` (the only `agentic_dynamics.*` dependency is the deterministic `runtime.test_runner` — never an adapter, never the control or knowledge plane). No LLM, no heuristic: two pytest exit classifications on two trees. |
| Wiring so the review phases and the operator's branch review can invoke it | `agentic-dynamics validate preexisting` (`src/agentic_dynamics/cli.py:96-100` maps `("validate", "preexisting")` → `check_preexisting.py`; usage line `:164`). The doc-mode is the review-rail surface — a review phase or the operator runs it on a review doc before accepting a "pre-existing" label. Exported from the runtime plane (`runtime/__init__.py:23,32`); classified in the script manifest (`scripts/CONTEXT.md`). |

## 2. VERIFY (a)-(d) — proven by the merged tests, run fresh, plus live invocation

All commands ran against this worktree at HEAD `0bcae03c8`, `-p no:cacheprovider`.

| Point | Test(s) / command | Result |
|---|---|---|
| (a) the guard PASSES when the failure genuinely exists at the merge-base (synthetic: a test that fails at base and on the branch) | `test_preexisting_drift_guard.py::test_guard_passes_when_failure_exists_at_base` — fixture `repo_base_fails_branch_fails` (base commits a failing test + a passing one; the branch adds an unrelated module, the failure stays): verdict `pre-existing`, `base_outcome=fail`, `head_outcome=fail`, and the machine citation round-trips. `test_guard_explicit_head_matches_default_head` — passing the branch tip explicitly equals the HEAD default. | pass |
| (a) LIVE on the real corpus | `scripts/check_preexisting.py --test tests/test_publication_singular_door.py::test_readme_figures_match_public_statistics --base a5ca7988f --head HEAD --repo /tmp/wt_evidence_verify` — the README-drift node that FAILS at this HEAD was checked at the wave's launch base (`a5ca7988f`, the main tip this re-run launched from): **exit 0, `pre-existing`, before=fail after=fail**, real citation (see §4). | pass |
| (b) the guard FAILS when the failure is branch-introduced (synthetic: a test that passes at base, fails on the branch) — the mislabel is caught mechanically | `test_guard_fails_when_failure_is_branch_introduced` — fixture `repo_base_passes_branch_fails` (the exact f4/f5 shape: base green, branch flips the assertion): verdict `branch-introduced`, `base_outcome=pass`, `head_outcome=fail`. `test_guard_fails_when_failing_test_is_absent_at_base` — a failing test that did not EXIST at base is branch-introduced by definition (`base_outcome=absent`). CLI twins: `test_cli_exit_zero_when_pre_existing` (exit 0 + the evidence line), `test_cli_exit_one_when_branch_introduced` (exit 1 + `branch-introduced`), `test_cli_json_carries_the_schema` (`preexisting-guard/v1`). | pass |
| (c) deterministic, sub-minute, no model calls | `test_guard_is_deterministic_and_sub_minute` — two runs over the same synthetic repo yield byte-identical evidence records in < 60s. `test_guard_module_performs_no_model_calls` — AST audit of the import graph: no `adapters`/`control`/`knowledge`, no `opencode`; only `runtime.test_runner`. LIVE: the §4 real-corpus prove run took **24.9s** wall (two git worktrees + one pytest node each) — well under the minute, zero model calls. | pass |
| (d) a review doc citing the guard's evidence is accepted; one claiming "pre-existing" without it is flagged | `test_review_doc_citing_guard_evidence_is_accepted` (`flag_uncited_preexisting_claims` → `[]`); `test_review_doc_claiming_preexisting_without_evidence_is_flagged` (1 flag); `test_review_doc_without_any_claim_is_accepted`; `test_negated_preexisting_mention_is_not_flagged` ("NOT pre-existing" is the correction, never flagged); `test_branch_introduced_citation_does_not_satisfy_a_preexisting_claim` (a citation whose verdict is `branch-introduced` proves the OPPOSITE — it licenses nothing). CLI doc-mode: `test_cli_doc_mode_accepts_cited_and_flags_uncited`. | pass |
| (d) LIVE through the wired CLI | `python3 -m agentic_dynamics.cli validate preexisting --doc <cited>` → **exit 0** accepted; `--doc <uncited>` (the same claim, no citation) → **exit 1**, `1 uncited pre-existing claim(s) flagged` (§4). The `("validate", "preexisting")` resolution is pinned by `tests/test_cli_resolution.py` (83 passed). | pass |

Command results (all run fresh this phase):

```
python3 -m pytest tests/test_preexisting_drift_guard.py -q -p no:cacheprovider
  → 17 passed in 11.87s    (the whole guard family — directions (a)-(d) above plus the CLI
                             surface, exit codes, JSON schema, and the error paths)
python3 -m pytest tests/test_cli_resolution.py -q -p no:cacheprovider
  → 83 passed in 0.14s     (the ("validate", "preexisting") → check_preexisting.py wiring)
```

## 3. The wiring is on the surfaces the original deliverable taught (verified present, in sync)

The merged e5 deliverable wired the guard into the command + review surface; all four are present
and resolve at this HEAD:

- `src/agentic_dynamics/cli.py:96-100` — `("validate", "preexisting"): "check_preexisting.py"` +
  the rationale comment naming the e5 drift guard; usage line `:164` (`validate session|tests|prereq|preexisting`).
- `src/agentic_dynamics/runtime/__init__.py:23,32` — `preexisting_guard` exported from the runtime plane.
- `scripts/CONTEXT.md` — classification row (`maintained: check_preexisting.py`) + the reference
  table entry: verdicts, exit semantics, `--doc` mode, zero-model determinism, CLI name.
- `tests/test_cli_resolution.py` — the resolution pin the e5 commit added (83 passed).

## 4. The deliverable is LIVE for this run — the guard ran on this branch's own real failure

Read from the live control db at `/home/drseuss/ai-finops-framework/experiments/results/control/control.db`
at `2026-09-02T13:22Z` (this phase's window), read-only:

```
runs:           run-5e31f69b4afa  control_db_evidence  running
step_attempts:  e0_pin_spec              1 ok  109832 tok  $0.0280
                e1_phase_evidence        1 ok  128397 tok  $0.0334
                e2_drain_and_lifecycle   1 ok  102097 tok  $0.0298
                e3_hermetic_publication  1 ok  116651 tok  $0.0273
                e4_phase_epoch           1 ok   91085 tok  $0.0230
gate_results:   0
run_heartbeats: run-5e31f69b4afa · beat 67 · actor orchestrator
control_epoch:  19
```

The e5 deliverable is not a db-writing feature, so its liveness is invocation, not rows: the guard
was **invoked on this branch, against this branch's own real failure**. The e0-e4 phases recorded a
standing pre-existing residual — a README "By the Numbers" corpus drift that reddens
`tests/test_publication_singular_door.py::test_readme_figures_match_public_statistics` at this
HEAD. Rather than take the label on trust, this phase ran the guard in prove mode with `base`
= `a5ca7988f` (the main tip this verification re-run launched from — the wave's merge-base) and
`head` = `0bcae03c8`:

```
check-preexisting: pre-existing
  test       tests/test_publication_singular_door.py::test_readme_figures_match_public_statistics
  base       a5ca7988f69f028fee59fe9b678d3b68576d3d2b
  head       0bcae03c8e0d1a21069b05a310676c3fd59f545f
  before     fail
  after      fail
  note       the failure exists at the merge-base — the author may call it pre-existing
  citation   preexisting-guard-evidence: verdict=pre-existing
             base=a5ca7988f69f028fee59fe9b678d3b68576d3d2b
             head=0bcae03c8e0d1a21069b05a310676c3fd59f545f
             test=tests/test_publication_singular_door.py::test_readme_figures_match_public_statistics
             before=fail after=fail
  -> the author MAY call this failure pre-existing (embed the citation above)
exit 0   (real 24.9s wall — two temp worktrees + one pytest node each, zero model calls)
```

That run is the pre-existing direction PROVEN on the real corpus, with the machine citation the
record now embeds (below). The doc-rail direction was then exercised through the WIRED CLI on the
same evidence: a review doc embedding the citation is **accepted** (exit 0), and the identical
claim without it is **flagged** (exit 1) — the exact accept/flag pair the review phases and the
operator's branch review invoke:

```
preexisting-guard-evidence: verdict=pre-existing base=a5ca7988f69f028fee59fe9b678d3b68576d3d2b head=0bcae03c8e0d1a21069b05a310676c3fd59f545f test=tests/test_publication_singular_door.py::test_readme_figures_match_public_statistics before=fail after=fail
```

The run-level accrual continues: e5 changes no source, so its own `step_attempts` row (the 6th,
written by the phase engine when this phase ends, moving the packet's progress line to 6/6) is the
only db change this phase causes. `gate_results` stays 0 for the correct reason — e0-e5 fire no
gate; the preregistered run-level criterion (`step_attempts >= 8`, `gate_results > 0` for
`run-5e31f69b4afa`) accrues as e6-e7 complete.

## 5. Residuals

- **R-1 (recorded-not-fixed, standing): the README "By the Numbers" drift.** The e0-e4 phases
  recorded it as a pre-existing residual; this phase upgraded that label from prose to PROOF by
  running the guard (§4): `pre-existing` at the wave's base `a5ca7988f`, machine citation issued.
  The failure is out of the e5 fence (guard + wiring only — correcting README corpus figures is
  the wave that owns corpus/README drift); the citation above is the evidence a reviewer requires
  if the claim is made again.
- **F4 (recorded at the merged adversarial review, standing): two accepted guard bypasses.**
  Main's e6 adversarial (F4) recorded two residual bypasses of the doc-side rail: the
  `verdict=pre-existing` citation is not bound to the SPECIFIC test it licenses (a citation for
  one node satisfies a claim about another), and `--base` is an unvalidated sha (the caller could
  pass an arbitrary earlier commit rather than the true merge-base). Both were RECORDED as small
  follow-ups, not blockers. The e5 fence is "the guard + its wiring ONLY — no changes to how
  findings are recorded beyond requiring the citation", so this verification phase does not fix
  them; they stand as recorded accepted limitations on main. The PROVE mode itself (the 
  load-bearing direction) is sound: it runs the SAME node at base and head and the mislabel fails
  mechanically when the true merge-base is supplied — re-confirmed live in §4.
- **A consequence of the citation rule worth recording:** the doc-rail flags the earlier-wave
  review documents — `control_db_evidence_adversarial.md` (7 lines), the e3 verify doc (3), the
  e4 verify doc (1) — because they record "pre-existing" claims (the README drift residuals, and
  the adversarial doc's F5 prose "the e5 guard confirms verdict=pre-existing") in prose WITHOUT
  embedding the machine `preexisting-guard-evidence` citation. That is the guard working as
  specified, not a defect: prose confirmation is not the citation, and these documents predate the
  strict citation discipline. It is recorded here so a reviewer running the rail on the merged
  corpus reads the flags as expected, not as new findings.

## 6. Scope fence

- **Changed:** `docs/reviews/control_db_evidence_e5_verify.md` (this verification record) — one
  file. No source, no tests, no spec, no workflow YAML were modified.
- **Not done, deliberately:** no re-implementation of the guard (it is the merged launch state,
  byte-identical to the original e5 commit `29f9d65f2`; editing it would undermine the run's
  premise), no new tests (the merged family covers every VERIFY point and runs green), no F4
  fix (the citation-to-claim binding and `--base` validation were RECORDED as follow-ups at the
  merged adversarial review — out of the e5 fence), no README drift correction (out of fence, R-1).
  No live control-db row was mutated: all live reads were read-only.

## 7. Verdict

**PASS.** The e5 deliverable — the pre-existing-drift guard — is present in the launched code,
matches the SHAPE point for point (`prove_preexisting` at `preexisting_guard.py:200` checks out
the base in a temp worktree and runs the SAME node there; `pre-existing` is the only passing
verdict; `branch-introduced`/`not-failing`/`unverifiable` refuse mechanically; the one-line
`preexisting-guard-evidence` citation is the currency a review doc must embed; `--doc` flags
uncited claims), is proven in BOTH directions by the merged unit tests run fresh (17 passed on the
guard suite + 83 on the CLI wiring), is deterministic/sub-minute/model-free (AST import audit +
24.9s real-corpus run), and is LIVE for this run: the guard was invoked on this branch's own real
failure and returned `pre-existing` with a real machine citation at the wave's merge-base, while
the doc-rail accepted the cited claim and flagged the identical uncited one through the wired CLI
(`agentic-dynamics validate preexisting`). The preregistered run-level criterion
(`step_attempts >= 8`, `gate_results > 0` for `run-5e31f69b4afa`) continues to accrue as phases
e5-e7 complete. No source or test file was modified, the scope fence held, and the standing
residuals (R-1 README drift — now guard-proven pre-existing — and the adversarial F4 bypasses)
are recorded-not-fixed for the waves that own them.
