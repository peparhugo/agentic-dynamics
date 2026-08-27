# CAP Site Revamp 4: Operator Design Approval

**Campaign:** `cap_site_revamp4`
**Phase:** `p2_design_with_human_checkpoint`
**Executor:** deepseek/deepseek-v4-flash
**Design:** `docs/designs/current/cap_site_revamp3_design.md`
**Baseline:** `experiments/results/cap_site_revamp3/incumbent_census.json` (verified p1, `40691ff0b`)

## Approval Status

**STATUS: APPROVED**

This committed template is intentionally unsigned. It does not authorize implementation,
comparison, review, deployment, or any removal. To approve, the operator must replace the
placeholder signature below, date it, commit the completed artifact, and leave the KEEP / REMOVE
/ ADD table intact or explicitly amend it.

| Delta | Scope | Operator decision | Reason / waiver |
|---|---|---|---|
| KEEP | All eight existing routes, shared `app.js` data hydration, persisted theme toggle, and floating ToC where currently present | `[x] approved` | The verified census is the minimum preservation contract. |
| KEEP | Framework's 14 sliders, two calculator modes, live outputs, chart host, chart controls, disclosures, tables, and handlers | `[x] approved` | The calculator is reframed as a transparent explorable; it is not removed. |
| KEEP | Evidence's five chart hosts, Grit controls and gated empty state, disclosures, 30 tables, analysis cells, and handlers | `[x] approved` | Field figures add scope and provenance without replacing evidence. |
| KEEP | Existing Home, Story, Methodology, Applications, Related Work, and Glossary content/data surfaces | `[x] approved` | Pages are augmented or recontextualized in place; no route/content surface is silently dropped. |
| REMOVE | None proposed | `[x] acknowledged` | No operator waiver is needed for this design. Any later removal requires a new row naming the feature, page, reason, and waiver. |
| ADD | Named question (new `question.html` route), field statement, origin-to-instrument bridge, provenance receipts, and honest-null states | `[x] approved` | Editorial additions remain classed `[M]`, `[C]`, `[H]`, `[X]`, or `[P]` and use `data.js` as the only data door. |
| ADD | 2b verdict, escalation `E_x`, and calibration arc figures | `[x] approved` | Each is scope-bound, names its evidence class, denominator/n, limitation, and authorization boundary. |
| ADD | Instrument cycle on Home AND Framework, N x M figure, eight planes, one-engine/two-modes, bounded-autonomy envelope, cost-curve explorable, ten rule cards, Applications reframe, Related Work scope labels, Glossary source anchors | `[x] approved` | Every addition cites the mapped historical local-example reference, preserves a static/accessibility fallback, and is verifiable as a present surface (the revamp3 review lesson). |
| ADD | Typography/color system in shared `base.css`, both themes | `[x] approved` | The system lives in `base.css`, not page-local-only styles; both themes honor it. |
| GATE | Continuous preservation census, feature-by-feature comparison (including ADD-surface presence), independent review, dual-host deployment verification | `[x] approved` | A spec-complete build is not a pass; the candidate must survive against the incumbent census and deliver every approved addition. |

## Operator Signature

```text
SIGNED-BY-OPERATOR: peparhugo
DATE: 2026-08-27
APPROVED DESIGN REVISION: 2f9844797
NOTES OR SPECIFIC WAIVERS: none
```

An implementation phase may start only after all relevant decisions are marked approved and the
four fields above are completed with non-placeholder values in a committed revision.
