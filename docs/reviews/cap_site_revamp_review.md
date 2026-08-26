# CAP Site Revamp Adversarial Review

**Review status:** PASS with one accepted execution-environment limitation.

**Scope:** public pages deployed from `apps/website/`, generated publication data,
campaign score receipts, Firebase publish rules, and keyboard-first static markup.
The review follows the editorial ledger in
`docs/designs/current/cap_site_revamp_research.md`.

## Verdicts

### Truth

PASS. Campaign claims now flow from the score artifacts through
`scripts/build_data.py` into `apps/website/data.js`, then into named page slots.
The generated campaign records retain artifact paths, full SHA256s, evidence classes,
sample sizes, and the explicitly untriggered routing state.

The retained score receipts are:

| Campaign | Score artifact | SHA256 |
|---|---|---|
| Randomized 2b | `experiments/results/cap_2b/cap_2b_score_20260826T160018Z.json` | `5f24f5072f1bb0ab17769b8db3734680b83981c2506df3b57fffa529c42ed3d9` |
| Escalation measurement | `experiments/results/cap_escalation_measurement/cap_escalation_measurement_score_20260826T125726Z.json` | `6d3c7a7c48ba718b0ccd7d9e1f3a9898336ed89c83ba791274dca7330b890329` |
| Live routing | `experiments/results/cap_session_routing_prospective/cap_session_routing_prospective_score_20260826T160605Z.json` | `288e0486d684b4f5f8809f626297ce521848de47e233d9482600dd06ae1a4402` |
| Calibration rerun | `experiments/results/cap_2a_rerun2/cap_2a_rerun2_score_20260826T015846Z.json` | `ef42f8b0ae07704cc693c51243dc755807586b0b745365d606e76410b19dd1ec` |

The calibration graphic no longer recreates the unavailable predecessor score. It names
that missing artifact as `[NULL]`, while rendering the retained rerun and 2b values from
`data.js`. The routing claim preserves the score's qualification that the live CPVO is the
no-escalation-needed case, not an escalation premium.

### Anti-SaaS

> PASS - The deployed public site is not a SaaS pitch: it contains no pricing, tiers,
> package comparison, demo booking, conversion CTA, customer proof, implementation offer,
> or enterprise-service promise. Its calls to action are research navigation and source
> inspection only.

This was checked against the exclusions in
`docs/designs/current/cap_site_revamp_research.md:43-47`. The only matches to broad
sales-language search terms are method vocabulary (for example, `feature` as a linked-story
phase) or an explicitly bounded external appendix.

### Field Test

PASS. The public route establishes all required objects in order: the home field statement,
personal origin, named question, instrument, current evidence, policy boundary, and open
measurement problems. The 2b decision is limited to design review; it is not represented as
an armed routing regime. `index.html`, `question.html`, `methodology.html`, `evidence.html`,
`framework.html`, and `accelerator.html` provide that route without product conversion copy.

## Finding Log

| ID | Check | Initial state | Resolution | Final |
|---|---|---|---|---|
| F1 | Campaign receipt integrity | FAIL: 2b, escalation, and routing displayed mutable artifact paths without hashes. | `build_data.py` now computes and publishes `source_sha256`; `app.js` renders path plus full SHA256 beside each campaign claim. | PASS |
| F2 | Calibration arc provenance | FAIL: the SVG contained literal `0/3`, `2/3`, and Wilson values outside `data.js`. | Added the retained rerun score adapter. The diagram receives its values from `campaigns.calibration` and represents the unavailable predecessor as `[NULL]`. | PASS |
| F3 | Public demo surface | FAIL: Firebase exposed `_design.html` and `references/`, including stale demonstration numbers. | Added `_design.html` and `references/**` to `firebase.json` hosting ignores. The library remains in the repository as research material but cannot be deployed as evidence. | PASS |
| F4 | Evidence-class separation | FAIL: the 2b sentence combined measured inputs with a computed verdict under one `[C]` badge. | Evidence now displays separate `[M] INPUTS` and `[C] DECISION` labels; the authorization remains `[P]`. | PASS |
| F5 | Historical session claim | FAIL: the Story reproduced an untraceable historical count. | Removed the count and named the missing ledger artifact; it remains neither current evidence nor a denominator. | PASS |
| F6 | Keyboard bypass and mobile receipts | FAIL: keyboard readers had no bypass for repeated navigation, and full SHA strings could overflow narrow screens. | Added one skip link and one `main` target to every public page; source receipts now use `overflow-wrap:anywhere`. | PASS |
| F7 | Rendered browser and assistive-technology test | LIMITATION: no Chromium, Firefox, Node runtime, or screen-reader runtime is installed in this environment. | Accepted for this review only. Static checks confirm responsive breakpoints, reduced-motion handling, visible focus, semantic SVG title/description, native rule-card buttons, and skip navigation. A deployed-browser and screen-reader pass remains required before release promotion. | ACCEPTED LIMITATION |

## Updatability Walkthrough

The 2b decision is the exercised new-finding path:

1. `cap_2b_score_*.json` is selected by `_load_latest_campaign_score()` in
   `scripts/build_data.py`; the adapter reads its arm data and decision rule and calculates
   the score-file SHA256.
2. `build_data.py` writes the provenance-tagged object to
   `window.DYNAMICS_DATA.campaigns.cap_2b` in `apps/website/data.js`.
3. `apps/website/app.js` formats only those published fields and fills
   `data-ad-cap2b-summary` and `data-ad-cap2b-source`.
4. `evidence.html` and `framework.html` expose those slots beside the authorization boundary.

This path was exercised by rebuilding `data.js`, then verifying the generated decision,
E_x values, per-model denominators, and all four score-file SHA256s.

## Known-Safe Checks

| Check | Why it passed |
|---|---|
| Data build and manifest generation | `python3 scripts/build_data.py` and `python3 scripts/generate_manifest.py` completed with the campaign adapter and immutable receipts. |
| Generator regression suite | `python3 -m pytest tests/test_build_data.py -q` passed all 32 tests. |
| Score-file integrity | A SHA256 check compared every generated campaign receipt with its on-disk score artifact; all four matched. |
| Public HTML and asset references | All nine deployable HTML pages parse and every relative asset/link target exists. |
| Campaign rendering contract | Generated data contains `NON_INFERIOR`, E_x values `11.4671` and `12.5134`, per-model `n=1`, and routing `n=6` with its untriggered qualification. |
| Anti-SaaS search | No prohibited sales language occurs in deployable public pages. Reference examples are excluded from Firebase. |
| Keyboard and reduced motion | All deployable pages contain one skip-to-main link; CSS supplies `:focus-visible`, a 720px single-column layout, receipt wrapping, and `prefers-reduced-motion` suppression. |

## Release Gate

The branch is safe for a static deploy after the final regression pass. Before promotion,
perform the accepted F7 browser pass at desktop and 320px width, tab through the rule cards,
that pass without rebuilding `data.js` and refreshing its receipt.
