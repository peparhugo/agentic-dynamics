---
status: accepted
---

# CAP Test-Runner Wiring — Sonnet-5 Adversarial Review (a4_review_test_runner)

**Reviewer:** claude-sonnet-5, `feature/cap-sonnet-adversary` phase `a4_review_test_runner`
**Target:** `feature/cap-test_runner_wiring` (spec names it `feature/cap-test-runner-wiring`;
same underscore/dash cosmetic mismatch as the other three branches — confirmed not missing).
**Target commits:** `98ad5b7d1` + `ce32306ec` (both `t1_map_the_path` — see note below),
`46519c265` (t2_wire_it), `3d4149664` (t3_document), on top of shared base `6cdefa102`.
**Method:** re-derived the diff surface with `git diff`/`git show` directly rather than trusting
the doc's own claims; spot-verified every file:line citation in the doc's heavily line-numbered
evidence style against the actual source at the branch tip; ran the new test file and the
broader affected test surface live in the branch's own worktree (`/tmp/wt_test_runner_wiring`,
checked out at `3d4149664`); independently confirmed the two claimed pre-existing test failures
reproduce identically on the base commit, unrelated to this branch's diff.

## Verdict: **PASS — no findings, clean sweep**

This branch's central claim — that a genuinely independent test-runner outcome, never a model
self-report, now flows into `phase_test_verified` for agent-kind phases with **zero** changes to
the reducer — holds up completely under direct code inspection, and the doc's file:line citation
style (unusually precise for this campaign) checked out exactly everywhere I sampled it.

## Findings

None. No mandatory fixes.

## Known-safe list (attacked, did not falsify)

| # | Attack attempted | Result |
|---|---|---|
| 1 | **`test_runner` is not actually the only source — a self-reported test result (from the model's own response) leaks into `test_executed_success` somewhere** | **Not falsified.** Grepped every assignment site of `test_executed_success` in `workflow_runner.py`: exactly two — the pre-existing `kind == "test"` branch (line 533, unchanged) and the new `_run_test_gate` (line 290) — both assign from `suite_succeeded(suite)` where `suite = run_suite(...)`, both imported from `agentic_dynamics.runtime.test_runner` at the top of the file (line 71). No third site exists. Separately confirmed `enforce_pytest` (the one other test-related knob touched by this branch's neighborhood) is purely a prompt-shaping kwarg (lines 604-606, feeds into the agent-call kwargs dict) with zero connection to `test_executed_success` — it never reaches the field. |
| 2 | **Defaulting `None` to `False` somewhere — a phase without a gate, or a gate that never ran, silently reports "failed" instead of "unknown"** | **Not falsified.** `PhaseResult.test_executed_success: bool \| None = None` (the pre-existing default, untouched) is never assigned to unless `_run_test_gate` actually runs, which itself is gated on `kind != "test" and phase_def.get("test_gate") and pr.status == "ok"` — an ungated phase, or an agent phase that already failed before the gate would run, leaves the field at its `None` default. Verified directly by `test_gate_skips_when_agent_phase_failed`, which asserts `calls == []` (the runner literally never invoked) and `test_executed_success is None` for a phase whose agent step failed, plus `test_agent_phase_without_gate_keeps_test_executed_success_none` for the no-gate case. |
| 3 | **The seam mapping (t1's file:line claims) doesn't match the actual code — stale references, off-by-N line numbers, or a claimed "kind-agnostic" reducer that actually isn't** | **Not falsified — checked at the line level, not skimmed.** Sampled 6 of the doc's most load-bearing citations against the real file at branch tip: `workflow_runner.py:116` (the `test_executed_success` field default) ✓, `:150` (its `to_dict()` serialization key) ✓, `:277-296` (the exact bounds of `_run_test_gate`) ✓, `:664-665` (the exact gate call site) ✓, `attempt_facts.py:226-230` (the exact bounds of the `isinstance(bool)` mint block) ✓ — every one matched byte-for-byte, including the doc's claim that the reducer's check is "not gated on `phase.get('kind')`" (confirmed: the guard is a bare `isinstance(phase.get("test_executed_success"), bool)` with no `kind` reference anywhere nearby). Also independently confirmed `zero diff to src/agentic_dynamics/control/` (the whole control plane, including `attempt_facts.py`) across all four phase commits — the "zero reducer changes" claim is not just asserted, it's structurally true. |
| 4 | **Additive-only is not actually true — some existing phase's behavior silently changes for specs that don't opt into `test_gate`** | **Not falsified.** The entire code diff against base is 34 insertions / 1 deletion in `workflow_runner.py` (the 1 deletion is a docstring-comment line being extended, not a behavior change) plus one new file (`_run_test_gate`, a wholly new function) plus one new 6-line call site gated on an opt-in flag that did not previously exist in any phase definition (`test_gate: true`) — so no pre-existing spec's phase dict can accidentally trigger it. Verified live: `test_agent_phase_without_gate_keeps_test_executed_success_none` runs the REAL `control_room_portal.yaml` production spec (unmodified) through `run_workflow` and confirms its `implement` phase (agent-kind, no `test_gate`) stays exactly as it always did — `test_executed_success is None`, and the pre-existing `verify` (test-kind) phase's fact is unchanged (`"true"`). |
| 5 | **Hermetic tests are absent, or present but shallow (mocks that don't actually exercise the real code path)** | **Not falsified.** `tests/test_test_runner_wiring.py` — 6 tests, ran live: 6/6 pass. Four are hermetic (fixture `run_suite` monkeypatched — present/absent/passing/failing/gate-skipped-on-prior-failure), one exercises the real git-commit-skip interaction in a real temp git repo, and the sixth (`test_real_re_derive_agent_phase_carries_bool`) is a genuine end-to-end integration test: a REAL `run_suite` executes a REAL pytest suite (two files written to a real temp git worktree) with only the LLM call stubbed, and the REAL `attempt_facts_v1` reducer is fed the result — not a hand-built fixture. Also ran the broader affected surface live (`test_workflow_runner.py` 29 tests, `test_context_plane_reducers.py`, `test_dependency_direction.py`, `test_data_flow.py`, `test_script_classification.py`): 111/111 pass. |
| 6 | **The re-derivation proof (one real phase now carries a bool where it was None) is fabricated or doesn't actually demonstrate the claim** | **Not falsified — this is exactly `test_real_re_derive_agent_phase_carries_bool` (attack #5's sixth test), read and re-run in isolation.** It asserts `implement.kind == "agent"` (so it is genuinely an agent-kind phase, the class the census found stuck at `None`) and `implement.test_executed_success is True` (a real bool, not a mock) after a REAL `run_suite` call against a REAL passing pytest suite, then feeds the real `WorkflowRunResult.to_dict()` through the real `attempt_facts_v1` and asserts `phase_test_verified == "true"` is minted — the exact end-to-end proof the workflow spec's t2 VERIFY step asked for, not a narrower or substitute claim. |
| 7 | **The "2 pre-existing failures, unrelated to this diff" claim is used to wave away a real regression this branch introduced** | **Not falsified.** Ran `tests/test_lab_contract.py` + `tests/test_lab_outputs_canonical.py` live: exactly 2 failures, both the exact `registry_version 'data-manifest/1.0+701rows' != current '...+736rows'` mismatch the doc names — confirmed this drift already exists at the shared base commit `6cdefa102` (`experiments/results/lab_cache_economics.json`'s `lab_contract.registry_version` is `data-manifest/1.0+701rows` there too, while the live registry has already grown well past 701 rows at base), so it predates all four flash branches and is not this branch's regression. |

## Notes for the record

- **Two `t1_map_the_path` commits exist** (`98ad5b7d1` then `ce32306ec`), not one. Diffed them:
  the second is a strict superset expansion of the first's doc content (adds the reproduced
  census table, the gate-placement rationale, and F1/auto-emit anchors) — zero code touched by
  either, and no contradictory claim between them. This is a benign within-phase self-correction,
  not a guard violation (hard rule 1 requires a commit per phase, not exactly one), and is
  recorded here only because a literal branch-state check should surface every commit, not just
  the ones matching the spec's phase count 1:1.
- No live full-corpus run was needed for this branch's verification the way it was for the other
  two (`pattern_minting`'s slow registry scan, `story_bridge`'s idempotency deep-dive) — the
  branch's own re-derivation test already exercises the real reducer end-to-end on a real (small,
  hermetic) corpus, and the "zero reducer/control-plane diff" structural guarantee makes a
  larger-scale re-verification lower-value here than it was on the branches that actually changed
  reducer code.
