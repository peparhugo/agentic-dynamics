# Visual approval — site revamp4 diagrams (repair + craft)

**Status: REJECTED by operator review (2026-08-27) — the craft still misses: "it's not really better, it has a lot of visual problems." No deploy.**

Hard rule 5: the repaired build is not deployed until the operator visually
approves it. Review the screenshots in this directory (and the per-figure table
in `index.md`), then sign below. Deployment targets BOTH Firebase hosts:
`ai-finops-rulebook` (canonical, never retire) + `agentic-dynamics` (mirror).

## What is being approved

- **Repair** — the collapsed OPERATING MODEL figure fixed at the root cause: the
  diagram container classes (`.system-figure`, `.diagram-scroll`, `.diagram-map`/
  `.workflow-map`, `.redesigned`) now have shared layout in `apps/website/base.css`
  (DIAGRAM SYSTEM), so a viewBox-only SVG can never collapse to 0x0 and nothing
  overflows. The dead 0x0 architecture-map was removed.
- **Craft** — label walls reduced on the two maps (OPERATING MODEL text 1176→1140,
  autonomy map 1149→1005); the cited example-library reference `svg-filter-focus.html`
  is now genuinely applied (planes control-plane glow, envelope PROPOSED-cell glow);
  wide-aspect figures keep a readable size on mobile via scroll wells.
- **Gate** — `apps/website/verify_svg_rendering.py` PASSES on every inline SVG:
  SIZE >100px both axes, zero OVERFLOW, ASPECT-correct, text/shape BALANCE
  (text ≤ 1.5× shape markup), PAINT (first-paint visibility, opaque, laid out),
  CONSOLE clean. **22/22 PASS** across all 9 pages at 1440x900 and 390x844, exit 0.

## Screenshots (operator-visible output)

| page | 1440x900 | 390x844 |
|---|---|---|
| index | `revamp4_index_1440x900.png` | `revamp4_index_390x844.png` |
| framework | `revamp4_framework_1440x900.png` | `revamp4_framework_390x844.png` |
| question | `revamp4_question_1440x900.png` | `revamp4_question_390x844.png` |
| evidence | `revamp4_evidence_1440x900.png` | `revamp4_evidence_390x844.png` |
| methodology | `revamp4_methodology_1440x900.png` | `revamp4_methodology_390x844.png` |
| story | `revamp4_story_1440x900.png` | `revamp4_story_390x844.png` |
| accelerator | `revamp4_accelerator_1440x900.png` | `revamp4_accelerator_390x844.png` |
| databricks | `revamp4_databricks_1440x900.png` | `revamp4_databricks_390x844.png` |
| glossary | `revamp4_glossary_1440x900.png` | `revamp4_glossary_390x844.png` |

Per-figure rendering table and before/after: `index.md` · gate data: `gate_report_full.md` /
`gate_report_full.json`.

## Signature

I have visually reviewed the repaired build's screenshots and the per-figure
rendering table, and I approve deploying this build to BOTH Firebase hosts.

```
Decision (check one):
  [ ] APPROVE  — proceed to deploy (firebase deploy --only hosting
                 and firebase deploy --only hosting --project agentic-dynamics)
  [x] REJECT   — do not deploy; changes requested below

Operator name:   ______________________________________
Role / title:    ______________________________________
Date (YYYY-MM-DD): ______________________________________
Signature / token: ______________________________________
Approval ref (branch + commit): ______________________________________
Changes requested (if REJECT):
  1. ____________________________________________________
  2. ____________________________________________________
  3. ____________________________________________________
```

This template is the approval gate — the signed copy (or the signed decision line)
is required before any `firebase deploy` on this branch.
