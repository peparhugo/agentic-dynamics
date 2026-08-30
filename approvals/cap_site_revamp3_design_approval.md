# CAP Site Revamp 4: Operator Design Approval

**Campaign:** `cap_site_revamp4`
**Phase:** `p2_design_with_human_checkpoint`
**Executor:** deepseek/deepseek-v4-flash
**Design:** `docs/website/cap_site_revamp3_design.md`
**Baseline:** `experiments/results/cap_site_revamp3/incumbent_census.json` (verified p1, `40691ff0b`)

## Approval Status

**STATUS: AWAITING OPERATOR APPROVAL**

This committed template is intentionally unsigned. It does not authorize implementation,
comparison, review, deployment, or any removal. To approve, the operator must replace the
placeholder signature below, date it, commit the completed artifact, and leave the KEEP / REMOVE
/ ADD table intact or explicitly amend it.

| Delta | Scope | Operator decision | Reason / waiver |
|---|---|---|---|
| KEEP | All eight existing routes, shared `app.js` data hydration, persisted theme toggle, and floating ToC where currently present | `[ ] approved` | The verified census is the minimum preservation contract. |
| KEEP | Framework's 14 sliders, two calculator modes, live outputs, chart host, chart controls, disclosures, tables, and handlers | `[ ] approved` | The calculator is reframed as a transparent explorable; it is not removed. |
| KEEP | Evidence's five chart hosts, Grit controls and gated empty state, disclosures, 30 tables, analysis cells, and handlers | `[ ] approved` | Field figures add scope and provenance without replacing evidence. |
| KEEP | Existing Home, Story, Methodology, Applications, Related Work, and Glossary content/data surfaces | `[ ] approved` | Pages are augmented or recontextualized in place; no route/content surface is silently dropped. |
| REMOVE | None proposed | `[ ] acknowledged` | No operator waiver is needed for this design. Any later removal requires a new row naming the feature, page, reason, and waiver. |
| ADD | Named question (new `question.html` route), field statement, origin-to-instrument bridge, provenance receipts, and honest-null states | `[ ] approved` | Editorial additions remain classed `[M]`, `[C]`, `[H]`, `[X]`, or `[P]` and use `data.js` as the only data door. |
| ADD | 2b verdict, escalation `E_x`, and calibration arc figures | `[ ] approved` | Each is scope-bound, names its evidence class, denominator/n, limitation, and authorization boundary. |
| ADD | Instrument cycle on Home AND Framework, N x M figure, eight planes, one-engine/two-modes, bounded-autonomy envelope, cost-curve explorable, ten rule cards, Applications reframe, Related Work scope labels, Glossary source anchors | `[ ] approved` | Every addition cites the mapped historical local-example reference, preserves a static/accessibility fallback, and is verifiable as a present surface (the revamp3 review lesson). |
| ADD | Typography/color system in shared `base.css`, both themes | `[ ] approved` | The system lives in `base.css`, not page-local-only styles; both themes honor it. |
| GATE | Continuous preservation census, feature-by-feature comparison (including ADD-surface presence), independent review, dual-host deployment verification | `[ ] approved` | A spec-complete build is not a pass; the candidate must survive against the incumbent census and deliver every approved addition. |

## Operator Signature

```text
SIGNED-BY-OPERATOR: <name>
DATE: <YYYY-MM-DD>
APPROVED DESIGN REVISION: <git sha of the committed design doc>
NOTES OR SPECIFIC WAIVERS: none
```

An implementation phase may start only after all relevant decisions are marked approved and the
four fields above are completed with non-placeholder values in a committed revision.
