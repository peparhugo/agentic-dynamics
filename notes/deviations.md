# Deviations — Item 4: the missing regression check for the stale next-action state

**Verdict: no plan deviation. The plan's central prediction held — the c15 gap is already
closed for the confirmed action wired today (a durable submit), so this phase lands the missing
regression check, not a source change. No production source file was modified.**

## What the plan said vs. what was true

| # | Plan | Reality | Delta |
|---|---|---|---|
| 1 | Gap closed for the submit path; land three named regression tests (`plan.md` §0–§2). | Confirmed mechanically by the tests themselves: the submit records over a non-empty stale `next_action`, the capsule renders the new binding value with precedence, and the stale text is absent from both the JSON slot and the rendered text. | None. |
| 2 | `notes/deviations.md` CREATED only if a deviation occurs (§1, §4.5). | No deviation in scope or behavior. The three named tests exist and pass; no fallback fix was needed. | This file is the honest record of that: created to state "no delta", per §4.5's "exists and records any delta". |
| 3 | Prefer the lighter `fm.main` argv over `_submit_fixture` (§5). | Used the light argv (`tests/test_fleet_manager.py:1034-1041` shape) for the real submit — no real git repo, hermetic and fast. | None; the plan preferred exactly this. |
| 4 | Reuse the `importlib` seam for `compose_capsule`, do not add a new import mechanism (§5). | Added `_load_session_open` to `tests/test_fleet_manager.py` using the same `importlib.util.spec_from_file_location` seam as `tests/test_session_binding.py:45-49`. | None. |
| 5 | KB read degradation expected in this worktree (`plan.md` §5; registry index absent). | `experiments/results/registry_index.jsonl` is absent and `python3 scripts/kb_read.py --query ... --scope agentic-dynamics` returned `hits=0` (ranked). | Anticipated by the plan; noted, not mistaken for an empty corpus. |

## Implementation choices worth naming (not deviations)

- The stale-instruction seeding update in `test_a_submission_supersedes_a_completed_next_action_in_the_capsule`
  passes `publish=False`, matching `_binding_store`'s `publish=False` — the test is hermetic
  (no real Redis stream), and the durable artifact/slot still land. The tested property
  (replace semantics + capsule precedence) is independent of the pointer publish.
- No `fast` marker was added: neither `tests/test_session_binding.py` nor
  `tests/test_fleet_manager.py` carries the marker today, and the fast-path parallel-safety
  audit governs modules that do.

## Out of scope (unchanged, per plan §6)

Residual: confirmed actions other than submit (e.g. `approve_workflow.py`) carry no session
identity and do not record — deliberately not covered by a test and not fixed here.
