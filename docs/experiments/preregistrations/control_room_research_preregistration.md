---
status: accepted
---

# Control Room research campaign — pre-registration (2026-09-11)

**Mandate.** Derive, not describe: research the open web at breadth and let the system answer
what a sleek, sexy control room for running many CLI AI-coding-agent sessions is — what the
operator needs to know, what is present but misplaced, what is missing. Design:
`docs/designs/proposed/control_room_research_campaign.md`. Egress: OPEN (controller-approved
2026-09-11).

**Corpus budget:** 200 high-quality sources (±20% per family): agent-ops rooms 40, operational
dashboards/design systems 50, charts/data-viz 40, terminal/CLI 30, craft/reference 40. Every
source enters through `scripts/research_fetch.py` (URI + final_url + fetched_at + sha256 +
title + text; dedup by content hash); each phase records its stop reason.

**Registered endpoints:**
1. **Corpus** — ≥160 stored sources with provenance and per-family stop reasons; no ad-hoc
   fetching.
2. **Taxonomy** — clusters with split/merge decisions, example refs, and support per node.
3. **Reduction** — decision skills + catalogs (frameworks, IA/layout, charts, color/motion,
   SVG technique) with citations; unsupported leaves dropped.
4. **Direction** — one cited design direction answering the operator-needs question and the
   misplaced/missing dispositions; alternatives rejected with reasons.
5. **Adversarial** — three independent passes (entailment/quality terra; design critique
   sonnet; IA critique sol), each with findings + required dispositions; dispositions
   addressed before the brief.
6. **Brief** — facelift brief with acceptance criteria (layout, chart set, SVG set, motion
   budget, accessibility bar, no regressions).

**Evaluation of the application (later):** Playwright render gate (desktop + mobile screenshots,
size/overflow/aspect/contrast/first-paint/console checks), rubric + controller review. The
controller judges the result; it is no longer required to describe the target.

**Spec pin:** `workflows/repository/control_room_research.yaml` (SHA256 prefix recorded in the
commit that added it). This is a derivation campaign — no statistical arms and no §4 decision
rule; the endpoints above are the acceptance contract.
