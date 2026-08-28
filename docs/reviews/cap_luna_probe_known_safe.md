---
status: accepted
---

# cap_luna_probe — known-safe list

**Campaign:** `cap_luna_probe` (`cap_luna_probe@0.1`). **Adversarial phase p4.**
Every item below was verified mechanically (commits, hashes, diffs, re-derivations) during the
adversarial review (`docs/reviews/cap_luna_probe_adversary.md`). Nothing in this list is assumed.

| # | item | evidence |
|---|---|---|
| K1 | Preregistration committed before any cell ran | `docs/designs/current/cap_luna_probe_preregistration.md` @ `1395a4e4e`; no `cap_luna_probe` results existed at that commit |
| K2 | Spec SHA pinned in the preregistration header (the ONLY edit) | `sha256sum workflows/repository/cap_luna_probe.yaml` = `e7220621d318a86d8be681a55fab3220a3a5e0f14c7f442c7b9ab1a1b9af1f54` matches the pinned header; the header pin is the only preregistration diff |
| K3 | Exactly the 8 pre-registered cells ran, nothing unlisted | p1 manifest @ `dbbba6d7d` (committed before any cell ran) lists exactly the 8 cell ids; `cells/luna_probe_*.json` = exactly those 8; p2 join-validation all 8 `ok` |
| K4 | Per-cell MESSAGE counts measured from transcripts, never estimated | re-derived `step-finish` recount matches the recorded value for all 8 cells (72/77/79/80/99/104/76/120), 5 sessions each, 0 parse errors (`p4_rederivation.json`) |
| K5 | Outcomes independent | unmodified `runtime.test_runner.run_suite` on each worktree matches the recorded `test_executed_success` for all 8 cells; the two Luna `static_site_gen` failures are genuine compile failures in the model-authored tests |
| K6 | Matched-cell pairing | both matched pairs are the same story + same condition; `notification_service` is the third-story check as pre-registered |
| K7 | Billing path is the OAuth subscription | `auth.json` openai `type=oauth`; all 8 cells' transcripts carry the OpenAI subscription response metadata; no API-key fallback |
| K8 | Window-fit arithmetic | median 79.5 × 30 = 2,385 msgs/5h; fits Plus 250? no; Pro 5x 1,250? no; Pro 20x 5,000? yes — identical to the p2 score |
| K9 | Treatment/measurement code untouched | `git diff 1395a4e4e..HEAD -- src/ scripts/ agent_config/` empty; TS cells re-verified by installing `node_modules` in the worktrees, runner unmodified |
| K10 | Generated surfaces untouched | no `.opencode/` / `.claude/` changes in the campaign |
| K11 | No secrets introduced | campaign-diff scan for key/secret/token material: clean |
| K12 | Budget within the $30 stop | 8 cells on the subscription window; per-cell estimated cost ≤ $0.10 (Luna) / $7.01 (Sol); total well under the $30 ceiling |
| K13 | Three-leg decision computed from recorded fields | p2 score JSON (`cap_luna_probe_score_20260828T213708Z.json`, sha `5b64ed02…`) traces every verdict number to a cell-record field; no imputation |

**Not known-safe** (deliberately flagged, see the adversary R1–R3): Luna's `static_site_gen`
(TypeScript) fails its own jest suite under both clean and late_degrade (genuine, model-authored
compile errors) — this is the measured REFUTE finding; the corpus's "100% (34 cells)" claim is
based on `all_successful`, not `test_executed_success`, and must not be carried into routing
without re-basing; the agent bash lacks `npm` on PATH, so TS story agents cannot self-run jest
(environment gap, handled by re-verification).

**LOG: PASS — commit.**
