---
status: accepted
---

# cap_luna_probe — adversarial review

**Campaign:** `cap_luna_probe` (spec `cap_luna_probe@0.1`). **Adversarial phase p4.**
The task of this review is to **falsify** the probe. Every claim below was re-derived
mechanically from the immutable artifacts (`experiments/results/cap_luna_probe/`), the
worktree transcripts, and the git trails — never from the agent's narrative. The re-derivation
output is `experiments/results/cap_luna_probe/p4_rederivation.json`, SHA256
`986e53af41e0fd25ac38634fa4bd68b2b0e81250706379c6d5bc655c5135ac79`. Known-safe items are in
`docs/reviews/cap_luna_probe_known_safe.md`.

## Findings

| # | adversarial probe | result | evidence |
|---|---|---|---|
| F1 | **Preregistration adherence** — the 8-cell table, the three-leg rule, the window math, the message-count requirement, the $30 stop | **CLEARED** | `cap_luna_probe_preregistration.md` committed at `1395a4e4e` BEFORE any cell ran (no `cap_luna_probe` results existed at that commit). The spec SHA `e7220621…` is pinned in its header (commit `8845ce489`); the header pin is the ONLY diff to the preregistration. The 8-cell table (6 Luna incl. 3 late_degrade + 2 matched Sol late_degrade), the three-leg rule (SUPPORT ⟺ all three), the window-fit math (median × 30 vs Plus 250 / Pro 5x 1,250 / Pro 20x 5,000), the message-count recording requirement, and the $30 stop (`stop.budget_usd: 30.0`, `max_attempts: 1`) all match the spec. **No deviation.**
| F2 | **Message counts re-derived from the transcripts** (never estimated) | **CLEARED** | Independent recount of `step-finish` events across each cell's 5 session transcripts (`worktree/.instrument/session_{n}.jsonl`): all 8 cells match the recorded values exactly (72/77/79/80/99/104/76/120), 5 sessions found per cell, 0 parse errors. `p4_rederivation.json.message_counts_all_match = true`. The recorded field is a measured transcript count, never a token estimate. |
| F3 | **Success determinations independent** (the test_runner evidence, not the agent narrative) | **CLEARED** | `run_suite` (the unmodified `runtime.test_runner`) re-run per worktree matches the recorded `test_executed_success` for all 8 cells. The two Luna `static_site_gen` failures are genuine: the model-authored tests/code do not compile under jest (suite `0 passed / 1 failed / 0 total`, compile error in the model's own test file). Sol clears the same story: `static_site_gen` 22/22, `task_manager_api` 43/43. `success_determinations_all_match = true`. |
| F4 | **Matched-cell pairing** (the matched cells really are the same stories) | **CLEARED** | Both matched pairs — (`task_manager_api`, late_degrade) and (`static_site_gen`, late_degrade) — are the same story + same condition on both arms. `pairing.ok = true`. The `notification_service` late_degrade cell is the third-story check, exactly as pre-registered. |
| F5 | **Billing path** (the cells ran on the OAuth subscription; an API-key fallback is a FAILED finding) | **CLEARED** | `auth.json` openai entry is `type: oauth`; all 8 cells' transcripts carry the OpenAI subscription response metadata (openai itemId blocks); the runs went through opencode's OAuth path. `billing_path.all_oauth = true`. No API-key fallback occurred. |
| F6 | **Window-fit arithmetic** (median × 30 vs the cited tier table) | **CLEARED** | Re-computed: median 79.5 messages/cell × 30 = 2,385 messages/5h. Versus the cited lower bounds — Plus 250: **no**; Pro 5x 1,250: **no**; Pro 20x 5,000: **yes**. Identical to the p2 score. Only Pro 20x carries the full grid. |
| F7 | **Treatment/measurement code untouched** | **CLEARED** | `git diff 1395a4e4e..HEAD -- src/ scripts/ agent_config/ .opencode/ .claude/` is empty. No measurement-apparatus edits during the campaign. (The TypeScript cells' `node_modules` were installed *in the worktrees* for re-verification; the runner itself was not modified.) |
| F8 | **Exactly the 8 pre-registered cells, nothing unlisted** | **CLEARED** | The p1 manifest (committed `dbbba6d7d`, before any cell ran) lists exactly the 8 cell ids; `cells/luna_probe_*.json` = exactly those 8; join-validation in the p2 score: all 8 `ok=true`. |
| F9 | **No secrets introduced** | **CLEARED** | Campaign diff scan for `sk-ant`, `sk-7e`, `api_key`, `password`, `secret`, private-key material: clean. |
| F10 | **No generated-surface edits** | **CLEARED** | `.opencode/` / `.claude/` unchanged in the campaign. |
| F11 | **Budget within the $30 stop** | **CLEARED** | 8 cells on the subscription window (per-cell estimated cost $0.07–$0.10 for Luna, $2.52/$7.01 for Sol; total estimated ≈ $12.5, and the subscription window is the billable surface — far under the $30 ceiling). |

## Real findings (the probe's substance, not integrity issues)

- **R1 — Luna's `static_site_gen` (TypeScript) weakness is consistent across conditions:** Luna
  fails its own jest suite under BOTH clean (72 msgs) and late_degrade (80 msgs); Sol passes the
  same story under late_degrade (120 msgs, 22/22). The clean `static_site_gen` failure makes the
  pre-registered baseline leg fail on the pinned `test_executed_success` semantics.
- **R2 — corpus "100% (34 cells)" is measured on `all_successful`, not `test_executed_success`:**
  the luna corpus rows' `test_executed_success` is `None`/`False` for most cells (esp.
  TypeScript). The probe's 3 clean cells are 3/3 on `all_successful` but 2/3 on the pinned
  semantics. Any routing claim must re-base on `test_executed_success`.
- **R3 — the agent's bash environment has no `npm` on PATH**, so TS story agents cannot run
  jest; without installing `node_modules` the fixed runner reports `jest.js not found`. This is
  an environment gap, handled by re-verification with deps installed (the runner is unchanged).
- **G1 (governance) — a stale score artifact** (`cap_luna_probe_score_20260828T213601Z.json`, an
  obsolete pre-validation emit) was swept into the p1 re-commit from the index during a
  `reset --soft`; it is removed in this phase. No scored number referenced it.

## Verdict on the probe

The probe is **adversarially intact**: preregistration adherence, measured message counts,
independent outcomes, pairing, billing path, and the window arithmetic all re-derive clean.
The three-leg computation REFUTES Luna-first routing (stress parity 1/2 vs 2/2; window fit on
Pro 20x only; baseline 2/3 pinned). The REFUTE verdict stands.

**LOG: finding table F1–F11 cleared, real findings R1–R3 + G1 recorded; PASS — commit.**
