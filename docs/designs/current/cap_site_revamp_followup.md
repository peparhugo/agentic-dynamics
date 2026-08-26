# cap_site_revamp — follow-up question: how do we gate visual craft?

**Status: open** · Raised: 2026-08-26, after `cap_site_revamp` (gpt-terra) deployed.

## What happened (the finding)

The campaign's research phase was genuinely good: the editorial audit (every number
tagged [M]/[C]/[H]/[X]/[P] with its source), the local example library (10 real-code
references collected from the web, hard gate passed), the visual language + diagram
inventory, and the editorial rewrite with the new evidence (2b verdict, measured E_x,
honest nulls). The p4 review passed its checks: truth, anti-SaaS, field test.

**The deployed site had ZERO of the visual system**: no `<svg>`, no canvas, no
scrollytelling, no interactive cards on any page. The "visual system" was 85 lines of
CSS + a components file + a design preview page — components built, never wired into
the pages. The operator's verdict: trash. Redeployed the pre-revamp site (main).

## Root cause (the process failure)

The spec demanded the research, the example library, and the copy — and gated them —
but **nothing gated the visual output itself**:

1. The diagram inventory was a *research deliverable*, not an *implementation checklist*.
2. The review criteria were truth/anti-SaaS/field — a DOM-level check of whether the
   diagrams exist on the pages was absent.
3. A component gallery counted as "the visual system" without being wired to pages.

The agent could satisfy every gate while shipping prose + components-never-integrated.
This is the same class of failure the campaigns repeatedly measured: **the gate must
test the deliverable's actual existence, not its description**.

## The open question

> **How do we gate visual craft in agent-built artifacts?** What measurable gates force
> an agent to deliver an implemented visual system (diagrams wired to data, cards
> interactive, narrative structured) rather than prose + unused components? Candidates:
> a per-diagram inventory checklist with DOM-level verification, data.js-wiring
> requirements (no hardcoded numbers that exist in data.js), gallery components all
> referenced by pages, and rendered-page evidence in the review. Which of these hold for
> other agent-built surfaces (reports, docs, dashboards)?

## The fix (cap_site_revamp2)

Authorized: `workflows/repository/cap_site_revamp2.yaml` — the same research + example
library + copy as its starting point, with the gates above made hard and measurable:
inventory checklist committed per diagram (page, file, data.js field, reference
citation), DOM-level verification, gallery-to-page wiring proof, and a review that
FAILS unless the inventory is 100% implemented on the deployed pages.

## Links

- Spec: `workflows/repository/cap_site_revamp.yaml` (superseded by cap_site_revamp2)
- Research: `docs/designs/current/cap_site_revamp_research.md` (branch feature/site-revamp)
- Review that passed the trash: `docs/reviews/cap_site_revamp_review.md` (branch)
