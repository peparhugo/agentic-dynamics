---
status: accepted
---

# cap_luna_probe — verdict: is Luna a good choice for the machine's story-cell volume?

**Source revision:** `881261863230a0dcc78351e712efa009daeabcfe`
**Spec:** `workflows/repository/cap_luna_probe.yaml` v0.1, SHA256
`e7220621d318a86d8be681a55fab3220a3a5e0f14c7f442c7b9ab1a1b9af1f54`
**Preregistration:** `docs/designs/current/cap_luna_probe_preregistration.md`
(committed BEFORE any cell ran; spec SHA pinned in its header on commit `8845ce489`).
**p1 manifest:** `experiments/results/cap_luna_probe/p1_manifest.json`, SHA256
`53e530c55b13af9d2816af1349bd7d6c5304ae83b70d24e61a5fe65f15bef0a2` (execution manifest
committed at `dbbba6d7d`, before any cell ran). **p2 score:** `cap_luna_probe_score_20260828T213708Z.json`,
SHA256 `5b64ed022f4fbaf0df2234f65377762e25e0fb9e7ffa4fb543cf42692614d517`.
**Every number below cites that p2 JSON; no post-hoc redefinition of the legs.**

## VERDICT: **REFUTE** (not SUPPORT)

The pre-registered three-leg rule requires ALL THREE legs. Two of three fail, and the
window-fit leg passes on only one of the three cited tiers. **Luna-first routing for the
story-cell volume is NOT authorized by this probe.** No routing-recommendation update is made.

## 1. The run (p1 — exactly the 8 pre-registered cells, 4-wide)

Backend: opencode on the OAuth subscription path (`auth.json` openai `type=oauth` — the cells
billed to the ChatGPT window, never an API key). Per-cell MESSAGE counts are MEASURED from the
transcripts (sum of `step-finish` events across the cell's 5 session transcripts —
`worktree/.instrument/session_{n}.jsonl`; the subscription's scarce unit). TypeScript cells
could not be verified by the agent (its bash has no `npm` on PATH — the agent documented this),
so the fixed runner re-verified them after installing `node_modules` with the nvm npm; the
runner itself is unmodified and remains the sole source of truth for `test_executed_success`.

| cell_id | model | story | condition | messages | test_executed_success | all_successful | success* |
|---|---|---|---|---|---|---|---|
| luna_probe_luna_task_manager_api_clean_r1 | luna | task_manager_api | clean | 77 | True | True | ✅ |
| luna_probe_luna_static_site_gen_clean_r1 | luna | static_site_gen | clean | 72 | **False** | True | ❌ |
| luna_probe_luna_notification_service_clean_r1 | luna | notification_service | clean | 104 | True | True | ✅ |
| luna_probe_luna_task_manager_api_late_degrade_r1 | luna | task_manager_api | late_degrade | 79 | True | True | ✅ |
| luna_probe_luna_static_site_gen_late_degrade_r1 | luna | static_site_gen | late_degrade | 80 | **False** | True | ❌ |
| luna_probe_luna_notification_service_late_degrade_r1 | luna | notification_service | late_degrade | 99 | True | True | ✅ |
| luna_probe_sol_task_manager_api_late_degrade_r1 | sol | task_manager_api | late_degrade | 76 | True | True | ✅ |
| luna_probe_sol_static_site_gen_late_degrade_r1 | sol | static_site_gen | late_degrade | 120 | True | True | ✅ |

\* success = `test_executed_success` on the final commit (independent `runtime.test_runner`)
AND the 5 sessions completed — the pre-registered pinned semantics (spec hard rule 4b).
Per-cell records + story-result SHA256s: `experiments/results/cap_luna_probe/cells/`, indexed
by `p1_artifact_index.json`.

## 2. The three legs (n in parens; from the p2 JSON)

**Leg 1 — STRESS PARITY (the unmeasured axis): FAIL.**
Luna late_degrade 1/2 vs Sol late_degrade 2/2 on the matched cells
(task_manager_api + static_site_gen). Not both at ceiling. The Luna late-degrade failure is
`static_site_gen` — a failure **Sol does not share** (Sol passed 22/22 on the same story under
the same condition). Per the pre-registered rule, a Luna late-degrade failure that Sol does not
share → **the stress envelope refutes Luna-first.** Luna's late_degrade failures are
story-consistent (it fails `static_site_gen` under clean too), i.e. a TS-codebase weakness, not
a stress-response difference — but the rule is blind to mechanism: Sol clears the same cell.

**Leg 2 — WINDOW FIT: median 79.5 messages/cell × 30 = 2,385 messages per 5h.**
The fit is reported for all three cited tiers (Luna window lower bound / upper bound per 5h):

| Tier | Luna window per 5h (cited) | grid need 2,385 | fits lower bound? |
|---|---|---|---|
| Plus | 250–2,000 | 2,385 | **NO** (9.5× over) |
| Pro 5x | 1,250–10,000 | 2,385 | **NO** (1.9× over) |
| Pro 20x | 5,000–40,000 | 2,385 | **YES** |

A full 30-cell grid at the measured median fits **only Pro 20x**. SUPPORT requires fit on the
operator's tier; the operator's tier is not named in the preregistration, so this leg is
reported per tier and cannot pass on Plus or Pro 5x.

**Leg 3 — BASELINE INTACT: FAIL under the pinned semantics.**
Clean cells 2/3 on `test_executed_success` (`task_manager_api` ✅, `static_site_gen` ❌,
`notification_service` ✅). The `static_site_gen` clean failure is a **genuine model-output
failure** (the model-authored tests do not compile under the independent jest run — verified
with deps installed), **not a runner regression**. Note the corpus's "100% (34 cells)" claim was
measured on `all_successful` (5 sessions completed), where the clean cells are 3/3 — the
pinned `test_executed_success` re-check is the stricter, pre-registered measure, and it breaks.

## 3. The two unknowns, answered

1. **The stress envelope:** Luna does NOT hold the unmeasured `late_degrade` condition at parity
   with Sol on the matched cells (1/2 vs 2/2); the corpus had zero late_degrade coverage, and
   the probe's two matched Luna late_degrade cells include one failure Sol clears.
2. **The window math:** measured median 79.5 messages/cell (range 72–120); a full 30-cell grid =
   2,385 messages/5h — inside only the Pro 20x window lower bound of the three cited tiers.

## 4. Routing recommendation + tier viability

- **Luna-first routing for the story-cell volume: NOT authorized** (REFUTE — legs 1 and 3 fail,
  leg 2 fails on Plus/Pro 5x). The routing recommendation stays as-is; nothing activates.
- **Which tier makes the full grid viable:** only **Pro 20x** (5,000-message lower bound) fits a
  30-cell grid at the measured median. Plus and Pro 5x cannot carry the full grid on Luna's
  window. Even on Pro 20x, the REFUTE verdict means the machine should not route story cells to
  Luna-first on window capacity alone.
- **Follow-up implied (not part of this probe):** the Luna `static_site_gen` (TypeScript)
  weakness is the binding failure on both the stress axis and the baseline; the machine's next
  campaign should measure whether it is a Luna-wide TS weakness or a story-specific gap before
  any routing change, and the corpus's "100%" success claim should be re-based on
  `test_executed_success`, not `all_successful`.

**LOG:** p1 ran EXACTLY the 8 pre-registered cells at 4-wide on the OAuth path, recording
per-cell MESSAGE counts from the transcripts; p2 scored the three legs + the tier-fit table from
the immutable p1 artifacts (join-validation all 8 cells ok); this verdict is REFUTE per the
pre-registered rule. **PASS (process) — REFUTE (decision).**
