---
status: proposed
---

# Control Room research campaign — design (dogfood of the research & synthesis layer)

**Mandate (controller, 2026-09-11).** Do not hand-describe "sleek and sexy". The system
research the open web at breadth (**200 high-quality sources**), derive its own UI/UX knowledge,
**categorize/split/reduce** it, and answer: *what would a sleek, sexy control room look like for
operating multiple CLI AI coding-agent sessions — what does the operator need to know, what is
present but in the wrong place, what is missing?* Then apply it to the Control Room first. All
visuals are in scope: layout, charts/graphs, SVG craft, motion, color, typography, accessibility.

**Egress:** open (controller-approved 2026-09-11; `egress_proxy` `*` mode, verified from a cell).

## Corpus (200 sources, five families)

| Family | Budget | Seeds (high quality, link-followed) |
|---|---|---|
| LLM/agent operations rooms | 40 | LangSmith, Langfuse, Braintrust, Helicone, AgentOps, W&B Weave, Arize Phoenix |
| Operational dashboards & design systems | 50 | Linear, Vercel, Grafana, Datadog, Sentry, PostHog, Railway, Fly.io, Modal, Supabase, Stripe |
| Charts & data-visualization craft | 40 | Observable/D3, ECharts examples, Vega-Lite, visx, Nivo, uPlot, Tremor, shadcn charts |
| Terminal/CLI aesthetics | 30 | Warp, Wave, Ghostty, Charm (bubbletea/gum), Textual, nvitop, asciinema |
| Craft, patterns, reference | 40 | MDN, web.dev, NN/g, Refactoring UI, Material/Apple HIG (density), Smashing, css-tricks SVG archive, SVG-Tutorial |

Every source enters through `scripts/research_fetch.py` (URI + final_url + fetched_at + sha256 +
title + text; content-hash dedup; append-only catalog). **Quality signals** recorded per source:
family, publisher authority, recency, and whether it demonstrates (not merely describes) the
technique. Sufficiency is agent-judged **with an obligation**: family budgets met ±20%, every
facet covered, and the stop reason recorded.

## Pipeline (the research workflow)

```
r0 audit      read apps/control_room (routes, panels, data feeds, refresh cadence) + current
              screenshots ──▶ what exists / misplaced / missing (operator's view)
r1 questions  mandate + audit ──▶ research questions, facet matrix, operator-needs list
r2 acquire    five family phases (a–e) ──▶ ≥200 sources + per-source facet/example records
              (fetch + distill inline, via research_fetch.py)
r3 taxonomy   cluster examples by facet; SPLIT heterogeneous clusters, MERGE thin ones;
              support per node ──▶ taxonomy artifact
r4 reduce     per-facet decision skills + catalogs: frameworks, IA/layout, chart selection,
              color/motion, SVG technique (each keeps citations + support)
r5 synthesis  one derived DIRECTION for the room + operator-needs answer + misplaced/missing
              list; rejected alternatives with reasons; all claims cited
r6 adversary  THREE independent passes (terra + a second model):
              (a) entailment/quality: every claim follows from its cited sources; no
                  single-source conclusions without a stated caveat; weak sources flagged
              (b) design critique: would a strong designer call this generic, dated, cluttered?
                  where the direction fails the mandate ("sleek/sexy", operator-first)
              (c) IA critique: does the direction answer what the operator needs to know first?
                  what is mis-ranked, buried, or absent?
r7 emit       ingest catalogs + skills into the KB via the verified retrieval path; verify
              retrieval by design-language query ("sleek dark dense multi-agent control room")
r8 brief      design brief + acceptance criteria for the facelift (layout, data hierarchy,
              chart set, SVG set, motion budget, accessibility bar)
r9 verify     independent check of corpus coverage, taxonomy support, emission, retrieval
```

## Application (facelift workflow, after the research brief is accepted)

```
a1 IA/layout   restructure the room around the operator-needs ranking (what is first?)
a2 charts      replace/augment hand-rolled sparklines with the derived chart set
a3 SVG craft   new diagram/visual set (architecture, routing, cost flows) to the brief
a4 styling     color/type/motion/accessibility to the derived direction
a5 render gate Playwright screenshots + gate-style checks (size/overflow/aspect/contrast/
               first-paint/console) at desktop + mobile breakpoints; no regressions
a6 adversary   design + IA critique against the brief; fix-or-justify findings
a7 controller   the controller reviews the screenshots; permanence decision on the branch
```

## Evaluation

- **Render gate** (new: `verify_control_room_rendering.py`, patterned on the website's
  `verify_svg_rendering.py`): zero failures at both breakpoints; per-page screenshots.
- **Rubric + controller review** for taste (the controller disposes, and no longer has to
  *describe* — only judge).
- **Research-quality audit:** every facet has ≥3 independent sources; every distinct claim
  carries citations; conflicts are recorded, not averaged; the "wrong place / missing" list is
  traceable to the audit.

## Risks

- **Open-web noise:** quality signals + the three adversarial passes, and single-source claims
  get caveats, not conclusions.
- **Corpus scale vs session budget:** five bounded acquisition phases, each with its own budget
  and stop reason.
- **Aesthetic subjectivity:** the direction must cite exemplars; the adversarial design critique
  attacks genericness before the controller sees it.
- **Facelift risk to a working portal:** the render gate + no-regression checks run before the
  controller reviews.
