# p2 — Diff + attribution: the loss/add classification table

Campaign: `cap_site_regression_analysis` · phase `p2_diff_and_attribution` · model
deepseek-v4-flash · 2026-08-27

## How the attribution was done

For every feature in the p1 feature matrix, I ran `git log -p` on `feature/site-revamp`
(revamp1, base `0c8c734f1`, tip `edeb2a7e5`) and `feature/site-revamp2` (revamp2, base =
revamp1 tip, tip `f13161f3b`), mapped each changed file to the workflow phase that touched it,
and classified each loss as (a) deliberate replacement, (b) accidental drop, or (c) gate-driven
removal. The classification table + full evidence is in
`experiments/results/cap_site_regression_analysis/attribution.json`; this note is the readable
summary.

## Phase map (which commit was which phase)

**Revamp1** (7 commits, phases inferred from content — the spec's hard_rule 1 `[workflow]`
prefix was NOT used):

| Phase | Commit | What it did |
|---|---|---|
| p0 research | `47f639201` | example library (14 references/) + research doc (editorial ledger, diagram inventory, anti-SaaS exclusions) |
| p1 visual system | `564641ffc` | `_design.html` gallery + `design-components.js` (10 components) + 85 lines base.css |
| p2 editorial rewrite | `54201491a` | **REWROTE ALL PAGES** (4353 deletions) — calculator, charts, levers, tables, narrative depth removed here |
| p3 implementation | `80a3bd9af` | **REWROTE app.js v0.5 → v2** (211→100 lines) — theme toggle, statMap, data-anal, TOC removed; data-ad wiring added; build_data.py campaign adapter |
| p4 truth review | `2b2257d15` | review doc + source_sha256 receipts + firebase.json ignores |
| p5 deploy | `b57e27595` | data.js refresh |
| p5 deploy | `edeb2a7e5` | deploy verification doc |

Note: at p2 the pages were rewritten to `data-ad-*` slots while app.js was still v0.5
(`renderDiagrams` count = 0 at `54201491a`) — the intermediate tree was a broken shell. app.js
v2 landed only in p3.

**Revamp2** (7 phases, all properly prefixed `[workflow]`): p1 `b1996109c` implemented the
diagram inventory + beta slider + sticky scroll; p2 `dfe371072` figure-copy reconciliation;
p3 `20eeb801b` made app.js/design-components data-aware + DOM verification; p4 `6550334f0`
review fixes (receipt family, lsp_available); p5 deploy. Revamp2 inherited all of revamp1's
losses (branched from its tip) and its gates never required the original layer to survive.

## The loss classification table

| # | Feature (page) | Removed in | Phase | Class | Why |
|---|---|---|---|---|---|
| L1 | Calculator — 14 range sliders, 2 modes (framework) | revamp1 `54201491a` | p2 editorial | **(c) gate-driven** | Research doc :78/:146 classified it "sales-like / SaaS/modeling pitch"; anti-SaaS exclusion names "conversion calculators" (:45). "Preserve as labeled [C] explorable" — not delivered in revamp1 |
| L2 | Cost chart — Chart.js `#costChart`, 3 views (framework) | revamp1 `54201491a` | p2 editorial | **(c) gate-driven** | Same research-doc ruling (:146); the intended `[C]` cost-curves SVG was in the diagram inventory but NEVER wired in revamp1 |
| L3 | 5 canvas charts (evidence) | revamp1 `54201491a` | p2 editorial | **(b) accidental drop** | Never inventoried by the research doc's diagram inventory (which listed only NEW diagrams); no gate asked for them; silently replaced by 2 js-injected SVGs |
| L4 | Grit interactive matrix (evidence) | revamp1 `54201491a` | p2 editorial | **(b) accidental drop** | Filter buttons + quadrant chart never ported |
| L5 | ~20 JS-populated data tables (evidence) | revamp1 `54201491a` | p2 editorial | **(b) accidental drop** | arc/grit/cost/AST/sonar/token/model-cards/RVS/drift/recovery/coupling tables all removed; only a 5-column model-aggregate table remains |
| L6 | app.js shared layer (theme toggle, statMap, data-anal, TOC) | revamp1 `80a3bd9af` | p3 implementation | **(a)+(b)** | Deliberate replacement of the data-injection mechanism (data-ad); theme toggle + TOC accidentally dropped with no v2 equivalent |
| L7 | Framework levers section + provider playbook + rule cards | revamp1 `54201491a` | p2 editorial | **(c)+(a)** | Research doc :260 "remove business calculator, provider playbook, unvalidated prescriptions"; rules resurrected as js cards in revamp2 |
| L8 | Accelerator enterprise page (maturity ladder, projections, WFM) | revamp1 `54201491a` | p2 editorial | **(c) gate-driven** | Research doc :148/:261 — explicitly retired as "the SaaS/enterprise-acceleration surface"; repurposed to "Open questions" |
| L9 | Databricks 4-lever comparison grid | revamp1 `54201491a` | p2 editorial | **(b) accidental drop** | Fold into evidence was PLANNED (research doc :259) but a 2,610-byte stub shipped and evidence never absorbed the content |
| L10 | Methodology instrument depth (10 operators, 7 signals, matrix) | revamp1 `54201491a` | p2 editorial | **(b) accidental drop** | "Keep as Method" (research doc :258) but the operator inventory never ported; 14 h2 → 3 h2 |
| L11 | Story 4-part narrative | revamp1 `54201491a` | p2 editorial | **(a) deliberate** | Rewritten per R2 positioning + editorial ledger (research doc :149) |
| L12 | Glossary 14 → 6 cards | revamp1 `54201491a` | p2 editorial | **(a) deliberate** | Rewrite as provenance-sourced definitions (research doc :150) |

**Tally:** 12 losses — 4 gate-driven (c), 5 accidental drops (b), 3 deliberate (a) (2 mixed).

## What the revamps ADDED (not a one-sided regression)

| # | Feature | Build / phase | Evidence |
|---|---|---|---|
| A1 | `question.html` (new page) | revamp1 p2 | research doc R4 IA (narrative spine) |
| A2 | Provenance tags site-wide | revamp1 p2 | 57 → 65 → 108 total tags across main→r1→r2 |
| A3 | Campaign receipts (artifact path + SHA256, decision-rule numbers) | revamp1 p3 | build_data.py campaign adapter → `data.js.campaigns.*`; app.js renderCampaignSlots |
| A4 | `data-ad` stat layer | revamp1 p3 | replaces `data-stat` |
| A5 | 9 js-injected SVG diagram slots | revamp1 p1 (components) → revamp2 p1/p3 (implemented+verified) | diagram_inventory.json 9/9 implemented; DOM gates pass |
| A6 | 10 interactive rule cards + rulesOverview SVG | revamp1 → revamp2 | framework `data-ad-rules`; rulesComponent(campaigns, summary, generatedAt) |
| A7 | Beta curve control (1 range input) | revamp2 p1/p3 | methodology `data-ad-beta`; bindCostCurveControl |
| A8 | Sticky-scroll narrative (story/evidence) | revamp2 p1 | `.ad-scroll-sticky` |
| A9 | DOM-verification tooling | revamp2 p1/p2/p3 | verify_dom_gates.py, verify_visual_system.py, verify_figure_copy.py |
| A10 | data-ad-receipt family + computed lsp_available | revamp2 p4 | app.js renderStats |

## Key findings

1. **The interactive layer died in exactly two revamp1 commits**: pages in `54201491a`
   (p2 editorial rewrite), app.js in `80a3bd9af` (p3 implementation). Revamp2 inherited and
   never restored them.
2. **The calculator + cost chart were GATE-DRIVEN removals (c)** — the p0 research doc,
   authored by the same model (terra), classified them as SaaS-adjacent and ordered deletion.
   This is the strongest evidence for the "gate compliance over delight" mechanism: the
   anti-SaaS gate (spec hard_rule 2) was applied so aggressively it deleted the site's most
   distinctive feature, and the promised `[C]` explorable replacement degraded to exactly one
   slider in revamp2.
3. **The evidence charts, grit matrix, data tables, methodology inventory, and databricks
   fold were ACCIDENTAL DROPS (b)** — no research-doc decision ordered them; the revamp's
   diagram inventory simply listed only NEW diagrams, so no gate checked for the existing
   ones. The p4 review's F7 (no browser runtime) meant even the deployed visuals were never
   actually rendered during review.
4. **"Deployed site had zero visuals" (followup) is a static-source-inspection artifact**:
   revamp1's committed HTML has zero inline `<svg>` because every diagram is JS-injected at
   runtime (renderDiagrams → AgenticDesign). A grep of the source finds nothing; a rendered
   page would show the slots. The wiring exists at revamp1 tip — but the review that passed
   it never rendered the page, so nobody could tell.
5. **What the revamps added is real and gated**: receipts with SHA256s, provenance, a
   verified diagram system, interactive cards. The regression is a substitution failure —
   the process moved the gate from "what the user can do" to "what the spec checklist says
   exists" — not an absence of new work.

## DELIVERABLES

- `experiments/results/cap_site_regression_analysis/attribution.json` (committed)
- This notes file (committed)

## LOG

- Classification table: 12 losses (4 c / 5 b / 3 a, 2 mixed) + 10 additions; each loss maps
  to commit + phase with evidence.
- **PASS**
