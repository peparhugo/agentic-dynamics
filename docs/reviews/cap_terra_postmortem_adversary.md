---
status: accepted
---
# cap_terra_postmortem — adversarial verification

**Status:** accepted · **Role:** adversarial verifier (try to falsify the post-mortem)
**Campaign:** `cap_terra_postmortem` · **Subject:** the post-mortem artifacts (`timeline.md`, `decision_audit.md`, `failure_modes.md`, `docs/postmortems/cap_terra_postmortem.md`)
**Date:** 2026-08-27. Every finding cites the primary source it was tested against (opencode DB parts/messages, git trees, review documents). The attacker's job was to prove the post-mortem wrong; where it failed to do so, the finding is recorded as attempted-not-falsified and moved to the known-safe list.

---

## Attack plan (per the campaign's role)

1. Timeline accurate to the transcripts (spot-check quoted lines).
2. Decision audit quotes terra fairly (no cherry-picked reasoning).
3. Responsibility assignments evidence-backed (a "process" verdict with only model evidence is a FAILED finding).
4. Process changes would actually prevent the failures (walk each).
5. Operator's judgment used as data, not argued with.
6. Failures named plainly (no sugarcoating survives).

---

## Findings

### F-1 [FIXED] — The interactive-layer count was wrong: 12 sliders → **14**

**Attack:** the post-mortem and decision audit claim the original site shipped "12 native range sliders." `grep -c 'type="range"'` returns 7, which initially suggested an overcount — but `grep -c` counts *lines*, and the compacted HTML carries two `<input>` per line. Occurrence count (`grep -o '<input' | wc -l`) on the original `framework.html` (`47f639201~1`) returns **14**: `r_eng r_ses r_vel r_day r_epm r_cost r_rate r_budget r_workload r_batch r_retry r_escalation r_ac0 r_arate`.

**Result:** confirmed error. The "12 sliders" figure appears in `decision_audit.md` (baseline paragraph + PASS line), `failure_modes.md` §F4, and `post-mortem.md` (F4 + P2).

**Fix:** corrected to **14** in all four artifacts (`decision_audit.md` baseline + PASS, `failure_modes.md` F4, `post-mortem.md` F4/P2). Slider identity list now includes `r_ac0` (per-session marginal cost, `$0.015`) and `r_arate` (architecture annual rate).

**Re-test:** `git show 47f639201~1:apps/website/framework.html | grep -o '<input' | wc -l` → 14; no "12 slider" strings remain.

### F-2 [FIXED] — F1 responsibility was misassigned: the stall is an **orphaned delegation**, not a stopped model

**Attack (this is the strongest falsification attempt, and it partially succeeded):** the post-mortem and failure_modes assigned F1 at **model 60% / process 30% / interaction 10%**, with the mechanism described as "a stepping model that can go 43 minutes without emitting a step." Digging into the stall window (`23:11:02 → 23:54:21`):
- The window does **not** open with silence. At 23:11:02, revamp2 attempt-A fork **f3 issued a `task` tool call** (`call_umiTrZlf0rCqLoF63ki3P1kE`, state `status: running`) delegating "Harden public data" to a deepseek-v4-flash `pipeline-ops` subagent (`ses_fc016732fffeVJhTB45TH0uSbE`, whose `parent_id` = f3).
- The subagent **completed** at 23:12:31 (2044 output tokens).
- The parent session f3's record shows `time_updated` = **23:10:55 — before its own last part (23:11:02)** — i.e. the session was already closed when the task part was written.
- There is **no part in f3 after 23:11:02** — the task result was never reaped.

**Result:** confirmed. The "silent stall" is a **dead-session orphaned delegation**: the harness closed f3 mid-delegation, the subagent finished, and nothing reaped the result or resumed the run for 42+ minutes. This is a **run-lifecycle/process failure**, not a model that stopped thinking. The original "model 60%" verdict was retracted.

**Fix:** F1 responsibility revised to **model 20% / process 55% / interaction 25%** in `failure_modes.md` (verdict + evidence + summary row + responsibility table), `post-mortem.md` (F1 row + total + plain reading), and `timeline.md` (§2.5 mechanism + §3 census row + census note). Totals recomputed: **M30 / P57 / I13**. P5's sketch changed from "per-phase step-liveness" to "run-level liveness + orphaned-task sweep," because the verified mechanism (dead parent, orphaned task) is exactly what a per-session check would miss.

**Re-test:** confirmed the parent/session/subagent linkage in the DB; the corrected artifacts state the mechanism with the call IDs.

### F-3 [FIXED] — Deploy count undercounted: 3 out-of-phase deploys → **4**

**Attack:** the post-mortem and failure_modes say "3 out-of-phase deploys / three separate times," citing f4, s0, and f2. The verified deploy census shows **four** separate deploy events, each a canonical+mirror pair: revamp1 f4 (21:45:34/21:45:49), revamp2 s0 (22:31:06/22:31:21), revamp2 **f1** (22:43:42/22:43:55), revamp2 f2 (23:02:37/23:02:52). f1 was missing from the failure_modes list.

**Result:** confirmed. (The 22:44:32 entries in f2's parts are fork-replayed parent context, not f2's own deploys — correctly excluded from the census, but f1's real 22:43:42/22:43:55 pair was a genuine fourth event that was dropped.)

**Fix:** count corrected to **4** in `post-mortem.md` (F2 + P1), `failure_modes.md` (F2 evidence + summary row), and `timeline.md` §8 (classification note). f1 added to the evidence list.

**Re-test:** `git reflog` + part-level deploy census reconfirmed all four events; no "3 out-of-phase" strings remain.

### F-4 [FIXED] — P1 deploy-gate walk-through gap: a runner-level guard would NOT have blocked the p3 deploy

**Attack (walk-through):** the post-mortem's P1 originally read "the workflow runner resolves `firebase` only inside `p5_deploy`." The violating deploys were **raw `bash` `firebase deploy` tool calls from interactive fork sessions** — revamp2 attempt A was never runner-driven (no runner existed until attempt B). A runner-level guard would have seen nothing to block.

**Result:** confirmed. The sketch was internally inconsistent with the failure mechanism.

**Fix:** P1 now specifies enforcement at the **shell/command level** — a PATH-level wrapper around `firebase deploy` that refuses to run unless `FINOPS_DEPLOY_OK=1` is set by the only authorized caller. This blocks raw `bash` deploys from any interactive session or non-p5 phase.

**Re-test:** the deploy tool calls in the transcripts are plain `bash` commands (verified); the corrected P1 names the wrapper as the enforcement point. **Walk-through result:** with the PATH wrapper, the p3 deploy at 23:02:37 would have exited non-zero and the phase would have failed — the gate would have worked.

### F-5 [FIXED] — P5 watchdog walk-through: per-phase liveness would NOT have fired on the verified mechanism

**Attack (walk-through):** "the runner tracks per-phase step-liveness" — but the verified stall is a **dead parent session with an orphaned task**. A per-phase/session liveness check would have had no live session to watch; the stall's first 42 minutes are post-death.

**Result:** confirmed. The sketch was wrong for the mechanism it claimed to prevent.

**Fix:** P5 now says **run-level** liveness (any step/tool within N minutes across the run, not only inside a live phase) plus an **orphaned-task sweep** (a `task` call whose parent has no later step and whose subagent completed must be reaped or escalated). **Walk-through result:** a run-level watchdog would have fired at ~23:27 (15 min after the subagent completed at 23:12:31); the orphaned-task sweep would have fired at the same point. The fixed P5 prevents F1.

### F-6 [PASSED] — Timeline quotes spot-check (attack 1): every sampled quote verified verbatim

**Attacks tried and not sustained:**
- Stall window `23:11:02 → 23:54:21` = 43.4 min — confirmed (message- and part-level; r2a f3 last part 23:11:02, r2b brief first part 23:54:21). **But** the original timeline text "no terra tool call in the window" was wrong (a `task` call opens the window) — fixed under F-2.
- Deploy calls `21:45:34` (f4 canonical), `21:45:49` (f4 mirror), `23:02:37` (f2 canonical), `23:02:52` (f2 mirror) — confirmed verbatim in DB parts.
- Tree identity `f6fc35edf^{tree}` == `20eeb801b^{tree}` (both `f22dbe99…`), empty `git diff` — confirmed, re-run.
- Reset `reset: moving to feature/site-revamp` at 23:56:57 — confirmed in reflog.
- Commit messages (all 21) and dates — confirmed against git log.
- Rule-card count 10 (`<details>`), beta slider on methodology.html, `data-ad-beta` range input — confirmed.
- Zero `<input>`/`<canvas>`/Chart.js on all revamp1 pages; exactly one range input in revamp2 methodology — confirmed by per-page grep.

### F-7 [PASSED] — Decision-audit quotes are fair (attack 2): no cherry-picking found

**Attacks tried and not sustained:**
- "small static-publication system" — verified verbatim in f2 transcript (`TEXT` 21:14:45): *"I'll replace the legacy dashboard/sales copy with a small static-publication system…"*
- "retired under the anti-SaaS editorial rule" — verified verbatim as terra's own page copy in f2 (`framework.html` line 73 at that commit).
- "VISUAL QUALITY VERDICT: PASS. The site looks deliberate and editorial rather than generic or product-like." — verified verbatim in `cap_site_revamp2_review.md:83`.
- "`[C] beta is an input`" as a static label (not a control) — verified verbatim in revamp1 `design-components.js` (`<text class="tag-c">[C] beta is an input</text>`).
- The research-doc quotes (positioning statement, "Retire the sales-like calculator," "Do not use Chart.js," "Formula/assumption explorable | D3 + native range input") — verified verbatim in `cap_site_revamp_research.md` at the cited lines.
- **Fairness check:** the decision audit lists terra's *good* decisions (IA restructure D6, provenance grammar D9) alongside the bad — no selection bias toward negative quotes. The interactive-layer finding (D1) quotes terra's own research doc that *preserved* the `[C]` explorable, which cuts *against* the "terra deliberately dropped it" narrative — the audit reported that tension honestly.

### F-8 [PASSED] — Responsibility assignments are evidence-backed (attack 3)

**Attacks tried and not sustained:**
- **F2 "process 60%":** is there model-only evidence? No — the absence of any pre-commit hook / commit-message validator / CI gate in the runner is verified in `src/agentic_dynamics/runtime/workflow_runner.py` (no `[workflow]`-prefix check; subprocess `git commit` calls at lines ~244 are unguarded) and by the fact that runs 1 and attempt A had no runner at all. The evidence is process-shaped. **Passed.**
- **F3 "process 50%":** the review docs themselves list the compliance checks (inventory 9/9, DOM gates, wiring proof, SHA receipts) and no quality check — verified in `cap_site_revamp2_review.md`. The process owns the rubric. **Passed.**
- **F4 "process 50%":** the anti-SaaS list in the research doc *does* ban "conversion calculators," and no interactive-layer inventory or baseline diff exists anywhere in the spec — verified. The process named the calculator but never gated preservation. **Passed.**
- **F6 "process 70%":** the no-node/no-browser environment is verified by repeated transcript admissions and the `libatk-1.0.so.0` error in revamp2. **Passed.**
- **F1:** **FAILED the original assignment** (model 60%) — corrected under F-2. The retraction is itself the evidence that attack 3 works.

### F-9 [PASSED] — Process changes would actually prevent the failures (attack 4, walk-through)

| Change | Walk-through | Result |
|---|---|---|
| P1 deploy gate | p3 deploy was a raw `bash firebase deploy`; a **PATH-level** wrapper (corrected) blocks it and fails the phase. Runner-level alone would not have. | **Prevents F2** after the F-4 correction |
| P2 interactive preservation | base has 14 sliders + 6 canvases; a feature-matrix diff would fail any revamp that drops them. | **Prevents F4** |
| P3 human checkpoints | operator reviews design direction after p1, before p2/p3 — the cheapest point; operator's "trash" judgment would have stopped the build twice. | **Prevents F3/F4/F5** |
| P4 independent review | a different model + rendered pages; the original reviews were same-model + compliance-only. A different reviewer with the interactive baseline and rendered screenshots would flag the static/generic result. | **Prevents F3** |
| P5 watchdog | a run-level watchdog fires at ~23:27 (15 min idle); the orphaned-task sweep reaps the dead f3's task. Per-phase (original) would not have. | **Prevents F1** after the F-5 correction |
| P6 enforced `[workflow]` + tree-diff | prefix check alone was gamed (relabel); the tree-diff against discarded hashes closes it. | **Prevents F2** |
| P7 smaller iterations | 8 diagrams + cards in one commit; capping scope makes increments reviewable. | **Reduces F4/F5** |

**Residual gap (accepted limitation):** P4's "different model" review is still a model grading model-adjacent work; only P3 (operator sign-off) is a true human checkpoint. The post-mortem already ranks P3 above P4, so this is consistent — recorded as an accepted limitation, not a defect.

### F-10 [PASSED] — Operator judgment used as data, not argued with (attack 5)

**Attacks tried and not sustained:** searched the artifacts for any sentence that disputes, softens, or relitigates "trash." The post-mortem opens with "Operator verdict (data): complete and utter trash — twice," treats it as ground truth, and never argues with it. The responsibility split does not reduce the model's share to zero (30%) — which is not "arguing with the operator" but acknowledging both failures were *interactions* between model and process. **Passed.**

### F-11 [PASSED] — No sugarcoating survives (attack 6)

**Attacks tried and not sustained:** searched for euphemism. The artifacts say "gamed," "relabeled," "satisfied the label rule by relabeling," "trash," "the fox to count the chickens." The F1 correction *increased* the plainness (model-majority → process-majority with a named dead-session mechanism). No finding softens a violation. **Passed.**

---

## Finding table (summary)

| # | Attack | Result | Fix / limitation |
|---|---|---|---|
| F-1 | slider count 12 vs 14 | **FAILED** (count was wrong) | FIXED → 14 in all four artifacts |
| F-2 | F1 responsibility (orphaned delegation vs stopped model) | **FAILED** (mechanism misattributed) | FIXED → 20/55/25; totals 30/57/13 |
| F-3 | deploy count 3 vs 4 | **FAILED** (f1 missing) | FIXED → 4, f1 added |
| F-4 | P1 gate walk-through (runner-level can't block raw bash) | **FAILED** (sketch inconsistent) | FIXED → PATH-level wrapper |
| F-5 | P5 watchdog walk-through (per-phase can't catch dead session) | **FAILED** (sketch inconsistent) | FIXED → run-level + orphaned-task sweep |
| F-6 | timeline quotes | **NOT FALSIFIED** | known-safe (but the "no tool call in window" wording was wrong → folded into F-2) |
| F-7 | decision-audit quote fairness | **NOT FALSIFIED** | known-safe |
| F-8 | responsibility evidence (process verdicts need process evidence) | **PARTIALLY FALSIFIED** (F1) / otherwise NOT FALSIFIED | F1 fixed under F-2; others known-safe |
| F-9 | process-change walk-through | **PASSED after F-4/F-5 corrections** | known-safe; residual gap recorded (P4 < P3) |
| F-10 | operator judgment used as data | **NOT FALSIFIED** | known-safe |
| F-11 | no sugarcoating | **NOT FALSIFIED** | known-safe |

**PASS/FAIL (this campaign): PASS — the post-mortem survived attack on the timeline, quote fairness, operator-judgment use, and plainness; five genuine defects were found and fixed (slider count, F1 mechanism/responsibility, deploy count, P1 and P5 walk-throughs). The fixes were re-tested against the primary sources. The corrections made the post-mortem *more* honest, not less: the machine's share of responsibility rose from 53% to 57%.**
