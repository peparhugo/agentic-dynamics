# CAP Site Revamp 3: Operator Design Approval

**Campaign:** `cap_site_revamp3`
**Phase:** `p2_design_with_human_checkpoint`
**Design:** `docs/designs/current/cap_site_revamp3_design.md`
**Baseline:** `experiments/results/cap_site_revamp3/incumbent_census.json`

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
| ADD | Named question, field statement, origin-to-instrument bridge, provenance receipts, and honest-null states | `[ ] approved` | Editorial additions remain classed `[M]`, `[C]`, `[H]`, `[X]`, or `[P]` and use `data.js` as the only data door. |
| ADD | 2b verdict, escalation `E_x`, and calibration arc figures | `[ ] approved` | Each is scope-bound, names its evidence class, denominator/n, limitation, and authorization boundary. |
| ADD | Nine inventory figures, rule cards, and typography/color system | `[ ] approved` | Every addition cites the mapped historical local-example reference and preserves a static/accessibility fallback. |
| GATE | Continuous preservation census, feature-by-feature comparison, independent review, dual-host deployment verification | `[ ] approved` | A spec-complete build is not a pass; the candidate must survive against the incumbent census. |

## Operator Signature

```text
SIGNED-BY-OPERATOR: <required: operator name or unambiguous identity>
DATE: <required: YYYY-MM-DD>
APPROVED DESIGN REVISION: <required: commit SHA containing this signed file>
NOTES OR SPECIFIC WAIVERS: <required: "none" or each approved exception>
```

An implementation phase may start only after all relevant decisions are marked approved and the
four fields above are completed with non-placeholder values in a committed revision.
