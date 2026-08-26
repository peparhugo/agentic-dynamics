# DOM Verification Report

PASS/FAIL: PASS

Release-candidate pages are loaded from the working tree, then checked after local `data.js`, `app.js`, and the inline-SVG renderer execute. The report is committed only after this PASS run.

| Gate | Page | Selector | Result | Evidence |
| --- | --- | --- | --- | --- |
| inventory coverage | `index.html` | `[data-ad-diagram="cycle"] svg` | PASS | found 1 inline SVG node(s) |
| data wiring | `index.html` | `[data-ad-diagram="cycle"] svg` | PASS | summary.sessions_total -> 1,067 |
| data wiring | `index.html` | `candidate markup` | PASS | summary.sessions_total has no copied data literal |
| data wiring | `index.html` | `[data-ad-diagram="cycle"] svg` | PASS | summary.canonical_findings -> 64 |
| data wiring | `index.html` | `candidate markup` | PASS | summary.canonical_findings has no copied data literal |
| accessibility | `index.html` | `[data-ad-diagram="cycle"] svg` | PASS | role, aria-label, label reference, title, and description |
| inventory coverage | `framework.html` | `[data-ad-diagram="cycle"] svg` | PASS | found 1 inline SVG node(s) |
| data wiring | `framework.html` | `[data-ad-diagram="cycle"] svg` | PASS | summary.sessions_total -> 1,067 |
| data wiring | `framework.html` | `candidate markup` | PASS | summary.sessions_total has no copied data literal |
| data wiring | `framework.html` | `[data-ad-diagram="cycle"] svg` | PASS | summary.canonical_findings -> 64 |
| data wiring | `framework.html` | `candidate markup` | PASS | summary.canonical_findings has no copied data literal |
| accessibility | `framework.html` | `[data-ad-diagram="cycle"] svg` | PASS | role, aria-label, label reference, title, and description |
| inventory coverage | `story.html` | `[data-ad-diagram="nxm"] svg` | PASS | found 1 inline SVG node(s) |
| data wiring | `story.html` | `[data-ad-diagram="nxm"] svg` | PASS | summary.sessions_total -> 1,067 |
| data wiring | `story.html` | `candidate markup` | PASS | summary.sessions_total has no copied data literal |
| data wiring | `story.html` | `[data-ad-diagram="nxm"] svg` | PASS | summary.canonical_findings -> 64 |
| data wiring | `story.html` | `candidate markup` | PASS | summary.canonical_findings has no copied data literal |
| accessibility | `story.html` | `[data-ad-diagram="nxm"] svg` | PASS | role, aria-label, label reference, title, and description |
| inventory coverage | `framework.html` | `[data-ad-diagram="planes"] svg` | PASS | found 1 inline SVG node(s) |
| data wiring | `framework.html` | `[data-ad-diagram="planes"] svg` | PASS | summary.variants -> 7 |
| data wiring | `framework.html` | `candidate markup` | PASS | summary.variants has no copied data literal |
| accessibility | `framework.html` | `[data-ad-diagram="planes"] svg` | PASS | role, aria-label, label reference, title, and description |
| inventory coverage | `framework.html` | `[data-ad-diagram="engine"] svg` | PASS | found 1 inline SVG node(s) |
| data wiring | `framework.html` | `[data-ad-diagram="engine"] svg` | PASS | summary.sessions_total -> 1,067 |
| data wiring | `framework.html` | `candidate markup` | PASS | summary.sessions_total has no copied data literal |
| accessibility | `framework.html` | `[data-ad-diagram="engine"] svg` | PASS | role, aria-label, label reference, title, and description |
| inventory coverage | `framework.html` | `[data-ad-diagram="autonomy"] svg` | PASS | found 1 inline SVG node(s) |
| data wiring | `framework.html` | `[data-ad-diagram="autonomy"] svg` | PASS | summary.canonical_findings -> 64 |
| data wiring | `framework.html` | `candidate markup` | PASS | summary.canonical_findings has no copied data literal |
| accessibility | `framework.html` | `[data-ad-diagram="autonomy"] svg` | PASS | role, aria-label, label reference, title, and description |
| inventory coverage | `methodology.html` | `[data-ad-diagram="curves"] svg` | PASS | found 1 inline SVG node(s) |
| data wiring | `methodology.html` | `[data-ad-diagram="curves"] svg` | PASS | design_parameters.beta -> 0.0010 |
| data wiring | `methodology.html` | `candidate markup` | PASS | design_parameters.beta has no copied data literal |
| accessibility | `methodology.html` | `[data-ad-diagram="curves"] svg` | PASS | role, aria-label, label reference, title, and description |
| inventory coverage | `evidence.html` | `[data-ad-diagram="escalation"] svg` | PASS | found 1 inline SVG node(s) |
| data wiring | `evidence.html` | `[data-ad-diagram="escalation"] svg` | PASS | campaigns.escalation.baseline_cost_usd -> $0.008949 |
| data wiring | `evidence.html` | `candidate markup` | PASS | campaigns.escalation.baseline_cost_usd has no copied data literal |
| data wiring | `evidence.html` | `[data-ad-diagram="escalation"] svg` | PASS | campaigns.escalation.models[].escalation_model -> openai/gpt-5.6-sol, anthropic/claude-sonnet-5 |
| data wiring | `evidence.html` | `candidate markup` | PASS | campaigns.escalation.models[].escalation_model has no copied data literal |
| data wiring | `evidence.html` | `[data-ad-diagram="escalation"] svg` | PASS | campaigns.escalation.models[].escalation_fix_cost_usd -> $0.102619, $0.111982 |
| data wiring | `evidence.html` | `candidate markup` | PASS | campaigns.escalation.models[].escalation_fix_cost_usd has no copied data literal |
| data wiring | `evidence.html` | `[data-ad-diagram="escalation"] svg` | PASS | campaigns.escalation.models[].E_x -> 11.4671, 12.5134 |
| data wiring | `evidence.html` | `candidate markup` | PASS | campaigns.escalation.models[].E_x has no copied data literal |
| data wiring | `evidence.html` | `[data-ad-diagram="escalation"] svg` | PASS | campaigns.escalation.models[].n_model_cells -> n = 1, n = 1 |
| data wiring | `evidence.html` | `candidate markup` | PASS | campaigns.escalation.models[].n_model_cells has no copied data literal |
| accessibility | `evidence.html` | `[data-ad-diagram="escalation"] svg` | PASS | role, aria-label, label reference, title, and description |
| inventory coverage | `evidence.html` | `[data-ad-diagram="calibration"] svg` | PASS | found 1 inline SVG node(s) |
| data wiring | `evidence.html` | `[data-ad-diagram="calibration"] svg` | PASS | campaigns.calibration.rerun.hits -> 2 |
| data wiring | `evidence.html` | `candidate markup` | PASS | campaigns.calibration.rerun.hits has no copied data literal |
| data wiring | `evidence.html` | `[data-ad-diagram="calibration"] svg` | PASS | campaigns.calibration.rerun.n -> 3 |
| data wiring | `evidence.html` | `candidate markup` | PASS | campaigns.calibration.rerun.n has no copied data literal |
| data wiring | `evidence.html` | `[data-ad-diagram="calibration"] svg` | PASS | campaigns.calibration.rerun.wilson_95_ci -> [0.2077, 0.9385] |
| data wiring | `evidence.html` | `candidate markup` | PASS | campaigns.calibration.rerun.wilson_95_ci has no copied data literal |
| data wiring | `evidence.html` | `[data-ad-diagram="calibration"] svg` | PASS | campaigns.cap_2b.decision_rule.cpvo_ratio -> 0.7857 |
| data wiring | `evidence.html` | `candidate markup` | PASS | campaigns.cap_2b.decision_rule.cpvo_ratio has no copied data literal |
| data wiring | `evidence.html` | `[data-ad-diagram="calibration"] svg` | PASS | campaigns.cap_2b.decision_rule.cpvo_ratio_ci_95 -> [0.6842, 0.9105] |
| data wiring | `evidence.html` | `candidate markup` | PASS | campaigns.cap_2b.decision_rule.cpvo_ratio_ci_95 has no copied data literal |
| data wiring | `evidence.html` | `[data-ad-diagram="calibration"] svg` | PASS | campaigns.cap_2b.decision_rule.decision -> NON_INFERIOR |
| data wiring | `evidence.html` | `candidate markup` | PASS | campaigns.cap_2b.decision_rule.decision has no copied data literal |
| accessibility | `evidence.html` | `[data-ad-diagram="calibration"] svg` | PASS | role, aria-label, label reference, title, and description |
| inventory coverage | `framework.html` | `[data-ad-component="rules"] svg` | PASS | found 1 inline SVG node(s) |
| data wiring | `framework.html` | `[data-ad-component="rules"] svg` | PASS | campaigns.cap_2b.decision_rule.decision -> NON_INFERIOR |
| data wiring | `framework.html` | `candidate markup` | PASS | campaigns.cap_2b.decision_rule.decision has no copied data literal |
| data wiring | `framework.html` | `[data-ad-component="rules"] svg` | PASS | campaigns.escalation.models[].n_model_cells -> n = 1, n = 1 |
| data wiring | `framework.html` | `candidate markup` | PASS | campaigns.escalation.models[].n_model_cells has no copied data literal |
| accessibility | `framework.html` | `[data-ad-component="rules"] svg` | PASS | role, aria-label, label reference, title, and description |
| gallery wiring | `_design.html` | `autonomy` | PASS | referenced by an inventory page |
| gallery wiring | `_design.html` | `calibration` | PASS | referenced by an inventory page |
| gallery wiring | `_design.html` | `curves` | PASS | referenced by an inventory page |
| gallery wiring | `_design.html` | `cycle` | PASS | referenced by an inventory page |
| gallery wiring | `_design.html` | `engine` | PASS | referenced by an inventory page |
| gallery wiring | `_design.html` | `escalation` | PASS | referenced by an inventory page |
| gallery wiring | `_design.html` | `nxm` | PASS | referenced by an inventory page |
| gallery wiring | `_design.html` | `planes` | PASS | referenced by an inventory page |
| gallery wiring | `_design.html` | `rules` | PASS | referenced by an inventory page |
| interactivity | `framework.html` | `[data-ad-rules] .ad-rule__toggle` | PASS | found 10 keyboard buttons |
| interactivity | `framework.html` | `[data-ad-rules] .ad-rule__toggle` | PASS | Enter and Space activate all 10 card buttons |
| interactivity | `story.html` | `.ad-scroll-sequence .ad-scroll-sticky` | PASS | found 1 sticky narrative element(s) |
| interactivity | `evidence.html` | `.ad-scroll-sequence .ad-scroll-sticky` | PASS | found 1 sticky narrative element(s) |

## Remediated Initial Findings
- RESOLVED: Initial audit: SVGs relied on aria-labelledby but lacked literal aria-label attributes.
- RESOLVED: Initial audit: escalation SVG text omitted the full provider/model identifiers.
- RESOLVED: Initial audit: the rules inventory entry had no SVG overview and did not render its escalation cell counts.

## Deployed Gate Runs
- PASS: `https://ai-finops-rulebook.web.app` passed the complete inventory, data wiring, gallery, interaction, and accessibility suite.
- PASS: `https://agentic-dynamics.web.app` passed the complete inventory, data wiring, gallery, interaction, and accessibility suite.
