# p1 — Inventory both sites: the interactive layer and the original's builders

Campaign: `cap_site_regression_analysis` · phase `p1_inventory_both_sites` · model
deepseek-v4-flash · 2026-08-27

## What the ORIGINAL app.js interactive layer contains (per CONTEXT.md: "app.js — Interactive UI, levers, calculator, charts")

CONTEXT.md's one-line description is accurate but understated: the interactive layer is
NOT all in `app.js`. It is shared machinery in `app.js` plus page-local chart/calculator
scripts in the HTML. Main (the live baseline) carries, site-wide:

| Feature | Where | What it does | Inputs -> Outputs |
|---|---|---|---|
| Theme toggle (☾/☀) | `app.js:4-20` | light/dark persisted to localStorage | click -> `.light` class |
| `data-stat` / `data-stat-fmt` injection | `app.js:22-125` | 31-key `statMap` reads `window.DYNAMICS_DATA` and fills `[data-stat]`/`[data-stat-fmt]` spans (sessions, cost, WOC, per-model cost/narration/penalty, registry counts, tombstones…) | DYNAMICS_DATA -> text nodes |
| `data-anal` row population | `app.js:127-152` | fills `<tr data-anal-model>` analysis tables from `D.analysis.models` | model aggregates -> table cells |
| Floating TOC (☰ panel) | `app.js:156-211` | auto-enables on pages with ≥3 h2/h3, smooth-scroll nav | click -> scrollTo |
| **Calculator — Augmented Workforce mode** | `framework.html:743-746` (inline) | 8 range sliders (team size, sessions/day, velocity, work days, energy scenario, eng cost, EPM rate, budget cap) | sliders -> per-model monthly cost, annual savings vs Claude, labor-cost equiv, budget runway |
| **Calculator — Autonomous Workloads mode** | `framework.html:749-751` | 6 range sliders (workload, batch %, retry rate, escalation tier, baseline cost/job, EPM rate) | sliders -> cost/job, max jobs/day, monthly spend, WOC ratio |
| **Cost chart** | `framework.html:711` + Chart.js CDN | line chart; horizon 3/10/25yr, baseline vs DS-scenario, cost vs throughput views | chart-mode buttons -> Chart.js redraw |
| **5 evidence charts** | `evidence.html` canvases: snowballChart, gritMatrixChart, narrationChart, costBarChart, locVsCostChart + Chart.js CDN | story-arc snowball, interactive Grit quadrant (model + perturbation-class filter buttons), narration penalty, cost ranking, code-vs-cost bubble | filters/buttons -> Chart.js redraw |
| `D.calculator.model_costs` + `escalation_tiers` | consumed by framework calculator | 8 model cost/pass entries, 8 escalation tiers | DYNAMICS_DATA -> calculator output |

Total on main: **14 range sliders, 6 Chart.js canvas instances, ~16 toggle/button controls,
theme toggle, floating TOC, dynamic Grit filters.**

## Survival in the revamps — the census verdict

| Original feature | revamp1 (feature/site-revamp) | revamp2 (feature/site-revamp2) |
|---|---|---|
| Calculator (14 levers) | **GONE** (0 sliders site-wide) | **GONE except 1**: a single beta-curve slider on methodology.html (`data-ad-beta`) |
| Cost chart + 4 evidence chart canvases | **GONE** (0 canvas, 0 Chart.js) | **GONE** (0 canvas, 0 Chart.js) |
| `data-stat`/`data-stat-fmt`/`data-anal` layer | **GONE** (replaced by `data-ad-stat`, 4 keys only) | **GONE** (replaced by `data-ad-stat` + `data-ad-receipt` + `data-ad-lsp-available`) |
| Floating TOC + theme toggle | **GONE** | **GONE** |
| Site-wide interactive controls | 10 js-injected rule-card expand buttons (framework) | 10 rule-card buttons + 1 beta slider + CSS sticky-scroll |
| **ADDED** | provenance tags, `question.html`, campaign receipts (source_sha256), 2 diagram slots (js-injected, never rendered on the deployed revamp1 — see followup: "no <svg>, no canvas, no scrollytelling, no interactive cards on any page") | 9 implemented + DOM-verified diagrams, campaign receipts, provenance tags site-wide, sticky narrative |

Key finding: **every** interactive feature of the original disappeared in BOTH revamps; the
only interactive affordance the revamps re-added is the rule-card expand (revamp2) and a
single scenario slider (revamp2). The revamp1 p4 review passed while its deployed site
contained zero implemented visuals — the gates measured compliance, not the deliverable.

## Content depth collapse

| Page | main bytes | revamp1 bytes | revamp2 bytes | revamp1/main |
|---|---|---|---|---|
| index | 18,699 | 5,666 | 5,672 | 30% |
| framework | 140,003 | 3,617 | 7,862 | 2.6% |
| evidence | 169,049 | 6,848 | 7,761 | 4.0% |
| story | 22,331 | 4,134 | 4,438 | 19% |
| methodology | 40,281 | 3,910 | 5,170 | 9.7% |
| accelerator | 36,954 | 3,648 | 4,096 | 9.9% |
| databricks | 17,365 | 2,610 | 2,610 | 15% |
| glossary | 9,904 | 3,649 | 3,800 | 37% |
| **all pages** | **454,586** | **36,873** | **44,302** | **8.1%** |

The revamps shipped ~8-10% of the original HTML volume, and the two deepest pages
(framework 140KB, evidence 169KB) collapsed to ~4-8KB stubs. The interactive layer lived
in that collapsed depth.

## Who built the ORIGINAL site (git provenance)

**The original interactive layer was built by operator-directed agent sessions
(ChaosClaw, then Pepar Hugo) from 2026-07-30 to 2026-08-13 — BEFORE the workflow runner
existed (first workflow commit 08-14).** The workflow era then FACELIFTED the pages and
PRESERVED the interactive layer:

1. **ChaosClaw (direct sessions, 07-30 → 08-07):** original `firebase/public/`; framework
   calculator + Chart.js (2a169e934 08-02), calculator sliders + budget runway
   (badf25dca 08-03), EPM slider + how-computed toggle (a6203f2ce 08-03), dual-mode
   calculator (4a4460760 08-06), 10 rules + autonomous workloads (5ab6a1277 08-06), shared
   CSS/JS (e6b22b748 08-06).
2. **Pepar Hugo (direct sessions, 08-08 → 08-13):** evidence Grit Matrix bubble chart
   (6938576b3 08-07), dynamic tables (8597072d4 08-10), scatter chart + sonar deltas
   (1780cea76 08-11), golden-circle reframe + architecture diagrams + audits.
3. **gpt-5.6-sol workflows (08-14/15):** `site_golden_circle`, `evidence_narrative`,
   `framework_facelift`, `evidence_redesign`, `agentic_dynamics_rebrand`. These rewrote
   copy and added the architecture SVGs, but the framework_facelift spec explicitly
   required the calculator to keep reading `D.calculator.model_costs/escalation_tiers`
   and evidence_redesign preserved all 5 chart canvases — verified: range-input count and
   `#costChart` canvas survive on main HEAD.
4. **deepseek-v4-pro workflows (08-17 → 08-22):** `website_registry_repoint`,
   `website_repoint`, `consolidation_stage_5+6`, `semantic_integrity_release`,
   `canonical_publication_closure`, `public_truth_closure`,
   `measurement_contribution_closure`, `finding_economics_closure`. Data.js/page
   repointing and canonical-data sweeps; the interactive layer survived intact (only
   `move_apps` ee2f35ec8 and the static-narrative sweep f4eafabc2 touch framework.html in
   apps/website history).
5. **gpt-5.6-terra (08-26 → 08-27):** `cap_site_revamp` (revamp1) + `cap_site_revamp2`
   (revamp2) — the regression under study. These are the ONLY site-touching workflows
   that REMOVED the interactive layer; neither merged to main.

So the operator's framing holds: the original was agent-built too, but the builders who
created the interactive layer worked in an un-gated, iterative, operator-directed loop
(dozens of small commits with immediate feedback), and the gpt-5.6-sol/deepseek-v4-pro
workflows that touched it later were constrained to preserve it. Terra's revamp workflow
was the first that was both (a) allowed to delete the calculator ("delete calculator/
enterprise scenario as SaaS/modeling pitch" — cap_site_revamp_research.md:78,146,260) and
(b) gated on compliance rather than on the interactive layer's survival.

## DELIVERABLES

- `experiments/results/cap_site_regression_analysis/feature_matrix.json` — the three-build
  feature matrix (committed).
- This notes file (committed).

## LOG

- Feature matrix summary: built — 3 builds × 9 pages × {interactive, data slots,
  diagrams, content depth, provenance}; interactive-layer census complete; survival
  verdict: every original interactive feature disappeared in both revamps.
- Original-builders list: complete — ChaosClaw/Pepar Hugo (direct sessions, interactive
  layer), gpt-5.6-sol (facelifts, preserved it), deepseek-v4-pro (repoint closures,
  preserved it), gpt-5.6-terra (revamps, removed it).
- **PASS**
