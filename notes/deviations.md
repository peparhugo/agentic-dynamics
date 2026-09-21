# Deviations — close the live-KB test-emission leak (test-seam fix)

**Verdict: no plan deviation. The world model's prediction held exactly — the leak is a
test-seam defect, the fix is test-only, and no production file changed.**

This file replaces the previous loop run's stale `notes/deviations.md` (the Item-4 /
stale-next-action record). The world model (`notes/world_model.md` §5) names this overwrite as
expected: the current run's execute/posterior/mint phases own these paths, and leaving the prior
prose would invite the posterior to mis-attribute it to this run.

## What the plan said vs. what was true

| # | Plan | Reality | Delta |
|---|---|---|---|
| 1 | Leak is a test-seam defect: `SPEC`'s explicit `rag.emit_self/emit_report: true` outranks the suite `FINFOPS_EMIT_SELF=0` disarm (`plan.md` §0). | Confirmed mechanically: `_finding_emit_enabled({"emit_self": True}, {})` returns `True` while `os.environ["FINOPS_EMIT_SELF"] == "0"` — asserted live in the new regression. | None. |
| 2 | ADD a module-local autouse fixture stubbing `knowledge_ingestion.emit_phase_finding` + redirecting `FINOPS_RESULTS_DIR` (§Files). | Implemented verbatim. Both `_emit_self_finding` and `_emit_research_report` import `emit_phase_finding` inside the function, so the module-attribute patch is honored; the redirect contains `_emit_research_report`'s direct `path.write_text`. | None. |
| 3 | ADD one regression driving the REAL emit routing and asserting (i) interception, (ii) live dirs unchanged (§Tests). | Implemented; both assertions are present and both were individually shown to fail under sabotage (see Verification). | None. |
| 4 | Do NOT touch production, `tests/conftest.py`, or the shared `SPEC`/`PLAN_GATE_SPEC` (§0, Out of scope). | `git diff --stat` touches only `tests/test_world_model_gates.py` (+ this note). | None. |
| 5 | Acceptance 2: with `FINOPS_RESULTS_DIR` unset, a module run creates no live `kb/` or `workflows/t_wml/` dirs. | Verified with `env -u FINFOPS_RESULTS_DIR`: both dirs absent before and after; `find` returns nothing. | None. |
| 6 | KB read degradation expected in this worktree (`plan.md` §Risks). | Not exercised — no fact needed. The world model already recorded the degradation; no new read was attempted. | None. |

## Implementation choices worth naming (not deviations)

- Added three imports the plan's snippets used implicitly: `os`, `pytest`, and
  `PROJECT_ROOT` (from `agentic_dynamics.core.paths`, the tier-0 path owner). Purely mechanical.
- The fixture's `monkeypatch.setattr` fits on one line (ruff's formatting), otherwise identical
  to the plan's shape.

## Verification (acceptance, run in this worktree with the suite disarm active)

1. `python3 -m pytest tests/test_world_model_gates.py -q -p no:cacheprovider` → **12 passed**
   (11 existing + 1 regression), 0 failed.
2. `env -u FINFOPS_RESULTS_DIR python3 -m pytest tests/test_world_model_gates.py -q
   -p no:cacheprovider` → 12 passed; `experiments/results/kb/` and
   `experiments/results/workflows/t_wml/` never created; `find` empty and unchanged.
3. Sabotage (throwaway copies under `tests/`, removed afterwards; the real file was never at
   risk):
   - removing the `ki.emit_phase_finding` stub → recorder empty → assertion (i) **failed**
     (`assert False`), no live-tree files;
   - removing the `FINOPS_RESULTS_DIR` redirect → assertion (ii) **failed** with a live
     `workflows/t_wml/reports/20260921181610_{prior,execute}.md` landing. The leaked dir was
     deleted; the live tree is clean again.
4. `ruff check tests/test_world_model_gates.py` → **All checks passed!**
5. `git diff --stat` → only `tests/test_world_model_gates.py` (+ this note).

## Out of scope (unchanged, per plan)

`_finding_emit_enabled`, the opt-in precedence, `emit_phase_finding`, the
`FINOPS_EMIT_SELF`/`FINOPS_RESULTS_DIR` contracts, and `tests/conftest.py` were not modified.
