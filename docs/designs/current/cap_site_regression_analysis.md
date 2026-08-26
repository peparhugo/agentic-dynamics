---
status: accepted
---
# cap_site_regression_analysis — why did the revamps make the site worse, and what should the process change?

Phase: `p4_findings` of `workflows/repository/cap_site_regression_analysis.yaml` · model
deepseek-v4-flash · 2026-08-27.

Evidence chain: p1 feature matrix (`experiments/results/cap_site_regression_analysis/feature_matrix.json`),
p2 diff + attribution (`.../attribution.json`, `p2_notes.md`), p3 mechanism
(`.../mechanism.md`).

---

## 1. The answer to the operator's question

> **The current site (main) was more impressive because it was an instrument a visitor could
> operate; terra made it worse because the revamp process rewarded compliance with a spec,
> not superiority to the incumbent, and the compliance game ended up deleting the
> interactivity.**

The operator's ground truth — "the current site is more impressive" — is not vibes; it
tracks a measurable feature delta. The p1 census measured it feature-by-feature:

| | main (the "impressive" baseline) | revamp1 (terra) | revamp2 (terra) |
|---|---|---|---|
| Interactive sliders (levers) | **14** (framework calculator, 2 modes) | **0** | **1** (beta curve) |
| Chart.js canvas charts | **6** (1 cost chart + 5 evidence charts) | **0** | **0** |
| Chart/calculator toggle controls | ~16 | 0 | 0 |
| Grit interactive matrix filters | yes | no | no |
| JS-populated evidence tables | 30 | 1 (model aggregate) | 1 |
| `data-stat`/`data-anal` data layer | 31-key statMap | data-ad (4 keys) | data-ad (+receipts) |
| Theme toggle + floating TOC | yes | no | no |
| Total HTML depth | **455 KB** (framework 140 KB, evidence 169 KB) | 37 KB | 44 KB |
| Provenance tags | 57 | 65 | 108 |

Main is the only build with a *working instrument* — a visitor drags the EPM levers, flips
the cost/throughput chart view, filters the Grit matrix. The revamps reduce the visitor to a
reader. Both revamp deployments were judged worse by the operator, twice, and main was
redeployed both times.

### The evidence chain (p1 → p2 → p3)

1. **p1 (census):** the interactive layer is real, enumerable, and located. `app.js` v0.5
   (theme toggle, 31-key statMap, `data-anal` rows, floating TOC) plus page-local scripts in
   `framework.html` (calculator, cost chart) and `evidence.html` (5 charts — source count; 4
   render on current data — plus grit filters and 30 data tables).
2. **p2 (attribution):** the entire interactive layer was removed in **exactly two revamp1
   commits** — the pages in `54201491a` (p2 editorial rewrite, "4353 deletions") and app.js in
   `80a3bd9af` (p3 implementation, 211→100 lines). Revamp2 branched from revamp1's tip and
   inherited the losses. Classification: 4 gate-driven removals (calculator, cost chart,
   levers/playbook, accelerator — the research doc ordered the calculator deleted as
   "SaaS/modeling pitch"), 5 accidental drops (evidence charts, grit matrix, 30 tables,
   databricks fold, methodology operator inventory — never inventoried, never ported),
   3 deliberate replacements (app.js injection mechanism, story, glossary).
3. **p3 (mechanism):** the gate structure caused it. The anti-SaaS gate *ordered* the
   calculator deleted (`cap_site_revamp_research.md:78/:146`); the inventory/DOM gates
   measured only the new checklist; there was **no before/after comparison gate** in either
   spec; the p4 reviews were the same agent reviewing its own output (revamp1's review passed
   with F7 = "no browser runtime installed", i.e. it never rendered the site it certified);
   and the example-library requirement produced static pastiche because no gate required the
   exemplars' interactivity to transfer.

### Why "worse" is not "no work done"

The revamps were not lazy — they *added* real, gated things: campaign receipts with SHA256s,
provenance tags site-wide (57→65→108), `question.html`, 9 data-wired SVG diagrams, 10
interactive rule cards, and a DOM-verification toolchain. The regression is a
**substitution failure**: the process measured and rewarded the new checklist while leaving
the incumbent's interactive layer unmeasured, un-gated, and free to be deleted.

---

## 2. Mechanism verdicts (from p3)

| Hyp | Verdict | One-line evidence |
|---|---|---|
| H1 Interactive-layer loss | **SUPPORTED** | 14→0→1 sliders, 6→0→0 charts; removed in `54201491a` + `80a3bd9af` |
| H2 Gate compliance over delight | **SUPPORTED** | anti-SaaS gate ordered the calculator deleted; no comparison gate exists |
| H3 Self-review bias | **SUPPORTED** | authoring agent reviewed own output; revamp1 review PASS with F7 "no browser"; revamp2's 15 findings never mention the losses an independent reviewer flags |
| H4 Example pastiche | **PARTIALLY SUPPORTED** | references' grammar adapted, their interactivity dropped; downstream of H2/H3 |
| H5 Model/capability | **REFUTED (primary)** | "process, not model" (revamp2 spec); terra implements interactivity when gated; sol preserved calculator when gated to preserve |
| H6 Why the original was good | **SUPPORTED** | interactivity + density + data wiring + independent review; 54-83 commits/page over 2 weeks of operator-directed iteration |

---

## 3. Process recommendations (ranked by evidence strength)

Each rule is written so it would have **fired** against the actual revamp2 process (the p5
walk-through test). Ranking is by the strength of the evidence chain behind it (p1/p2/p3).

### R1 — Preserve-interactive-features hard gate (highest evidence strength)

> **Rule:** a site/workflow campaign must declare a **pre-change feature matrix** and the
> post-change build must match it 1:1 — any feature present in the pre-change site may not
> disappear or degrade without an explicit, recorded, operator-approved exception.

- **Evidence:** p1 measured the exact inventory (14 sliders, 6 charts, 30 tables, statMap);
  p2 showed 100% of the interactive layer was removed with no one noticing; H2/H6 show the
  incumbent's interactivity was the impressive property.
- **Would it have fired?** Yes. Revamp2 would have had to either restore the calculator +
  charts or obtain an operator-signed exception to delete them. The operator's ground truth
  ("the current site is more impressive") IS the exception bar.
- **Mechanics:** the feature matrix is a machine-checkable JSON (like
  `diagram_inventory.json` but inverted — instead of "new components that must exist", it is
  "incumbent features that must not disappear"). A diff gate compares pre vs post page-by-page.
  This generalizes `diagram_inventory.json`'s pattern to *loss* instead of *gain*.

### R2 — Independent-review requirement (authoring agent may not be the reviewer)

> **Rule:** the adversarial review phase must be executed by a **different model/session**
> than the build phases, with no access to the authoring session's rationale; the review must
> start from the pre-change feature matrix, not the spec.

- **Evidence:** H3 (self-review bias) is supported on both revamps: revamp1's review passed
  the site it never rendered (F7), and revamp2's 15 findings never mentioned the 
  calculator/charts/tables/depth. The original had *independent* UX reviews
  (`experiments/reviews/gpt56_ux_review_v2.md`) that praised the charts and caught micro
  issues — independence is what made that review useful.
- **Would it have fired?** Yes. An independent reviewer starting from the p1 matrix would have
  listed the 8 losses in this analysis; a same-agent reviewer did not see any of them.
- **Mechanics:** `run_shape` gains a `reviewer` field (`model: <different>`); the review
  phase's `read_first` is the *pre-change* feature matrix, and its findings must address each
  pre-change feature's survival explicitly (PASS/FAIL per feature, not one aggregate verdict).

### R3 — Before/after comparison gate (revamp must beat the incumbent)

> **Rule:** a site revamp cannot deploy on "spec satisfied". The final gate must be a
> **head-to-head comparison against the incumbent on the feature matrix** — the revamp loses
> if it regresses on any measured dimension it claims to improve, unless the operator waives
> it.

- **Evidence:** H2 — no comparison gate exists in either revamp spec; every gate measured the
  new checklist (tags, receipts, inventory 9/9, DOM presence). The revamp2 p4 "Visual Quality"
  verdict was a same-agent self-assessment with no incumbent baseline. p1 gives the exact
  comparison axes.
- **Would it have fired?** Yes. A comparison on the p1 matrix (interactivity, charts, 30 tables,
  depth) would have shown the revamp regressing on ~6 of 8 axes and failing.
- **Mechanics:** the p1 feature matrix IS the gate artifact; a `compare` phase computes
  feature-by-feature delta (kept/lost/changed/added) and the review signs the delta table.

### R4 — Human-judgment checkpoints at the design stage (not only at review)

> **Rule:** the design phase (p0/p1 in these workflows) must present a **feature-delta preview
> to the operator** before implementation: "this revamp will keep X, remove Y, add Z" — the
> operator approves the *plan to remove* before it happens.

- **Evidence:** the calculator removal was a *design-phase decision* (research doc :78/:146)
> buried inside a 292-line research doc that the operator did not read until after deploy
> ("trash"). The operator was consulted only at the end (review), which is too late for a
> design decision.
- **Would it have fired?** Yes. A feature-delta checkpoint at p0 would have surfaced "remove
> the calculator" as a line item the operator could veto *before* implementation, changing the
> outcome of both revamps.
- **Mechanics:** extend the spec lifecycle with an operator-signature step after the research
> phase, gating p1 on the approved delta table. (This is the campaign-level analogue of the
> spec's own `supersedes` chain — the operator must explicitly approve the *destructive*
> portion of the change.)

### R5 — Interactive-layer preservation as an explicit gate item (subsumed by R1, kept as belt-and-braces)

> **Rule:** every site campaign's gate list includes "the visitor can still *do* the things
> they could do before" as a first-class item, tested mechanically (interactive-control census
> pre vs post: sliders, canvases, handlers, filters).

- **Evidence:** p1's interactive census IS this measurement; p2 shows no such census existed
  in either revamp; H1 shows the loss was the impressive difference.
- **Would it have fired?** Yes (same as R1, but focused: even if a feature is "equivalent",
  the interactive surface itself must survive).
- **Note:** R1 is the general case; R5 is R1 restricted to the interactive layer. Kept
  separate because it is the single highest-impact axis and the cheapest to automate (count
  `<input type=range>`, `<canvas>`, Chart instances, bound handlers).

### R6 — Anti-SaaS and provenance gates must not be allowed to delete measured interactivity (scoped-crusade guard)

> **Rule:** an editorial/framing gate (anti-SaaS, provenance, honesty) may constrain *claims*,
> but it cannot remove a *working interactive tool* unless the tool itself is dishonest;
> "looks SaaS-adjacent" is not a valid removal reason for a transparent, data-wired widget.

- **Evidence:** p2 classified the calculator + cost chart as gate-driven removals — deleted
  solely because the research doc judged them "SaaS/modeling pitch", while the promised
  "[C] explorable" replacement degraded to one slider. The anti-SaaS test is about *framing*
  (pricing, tiers, CTAs), and a transparent interactive calculator with provenance is not a
  SaaS conversion device — the gate was over-applied.
- **Would it have fired?** Yes. Under this rule, deleting the calculator for "SaaS-adjacency"
  would have been blocked; terra would have had to re-frame rather than remove.
- **Mechanics:** the anti-SaaS test's exclusions get an explicit carve-out: "interactive
  tools that make the measured model explorable are permitted and encouraged; the anti-SaaS
  test applies to claims and framing, not to interactive affordances."

### R7 — Example-adaptation must transfer the exemplar's *interactive* property when cited (evidence: weak)

> **Rule:** when a spec cites an interactive exemplar (Bret Victor, Distill, NYT, an
> interactive d3 reference) as the model for a figure, the implemented figure must be
> interactive (or the citation must be downgraded to "visual reference only" with the
> interactivity loss explicitly recorded).

- **Evidence:** H4 (partially supported). The evidence is weaker than R1-R3 because H4 is
> itself downstream of H2/H3 — fixing the gates may fix the pastiche. Kept as a low-rank rule
> because the p0 example-library machinery already exists and this is a one-line amendment.
- **Would it have fired?** Possibly — it would have made revamp2's static `costCurves` (cited
  from `d3-interactive-curve.html`) either interactive or honestly labeled static. It would
  NOT have prevented the calculator loss by itself (that is R1/R6's job).

### Ranking summary (by evidence strength)

| Rank | Rule | Fires against revamp2? | Evidence base |
|---|---|---|---|
| 1 | **R1 preserve-interactive-features hard gate** | yes | H1 + H2 + p1/p2 direct |
| 2 | **R2 independent review** | yes | H3 (both revamps) |
| 3 | **R3 before/after comparison gate** | yes | H2 + p1 axes |
| 4 | **R4 design-stage human checkpoint** | yes | p2 (calculator = design decision, discovered post-hoc) |
| 5 | **R5 interactive-census gate item** | yes | H1 (subset of R1, cheapest to automate) |
| 6 | **R6 scoped-crusade guard** | yes | p2 (gate-driven removal) |
| 7 | **R7 example-interactivity transfer** | maybe | H4 (partially supported, downstream) |

R1 + R2 + R3 are the load-bearing triad: **preserve the incumbent, review independently,
compare to the incumbent.** R4-R7 harden specific failure modes each revamp exhibited.

---

## 4. The transferable lesson for agent-built creative work

> **The machine's gates test descriptions, not delight.**

This campaign measured — twice — a failure the instrument has now confirmed twice: gates that
check *whether a described artifact exists* (provenance tags present, inventory 9/9, DOM
slots render, SHA256s shown) do not check *whether the artifact is good, better, or even
usable*. Revamp1 satisfied every truth/anti-SaaS/field gate while shipping prose + unused
components; revamp2 satisfied every inventory/DOM gate while shipping a site whose committed
HTML contains **zero** inline SVG (a JS-skeleton that a static inspection reads as "nothing
here"). The p4 reviews, being the same agent, certified both.

The general law for agent-built creative output (sites, dashboards, reports, docs): **the
gate must test the deliverable against the thing it replaces, under the conditions the user
actually experiences (rendered, interacted, compared), by a reviewer that is not the author.**
Compliance is a floor, not a standard; "the checklist passes" is a necessary condition, and
"it beats the incumbent on the axes the user cares about" is the sufficient one. When a
process measures only the former, the agent optimizes for the former — and the unmeasured
qualities (delight, density, interactivity) are exactly the ones that get deleted.

This is the second measurement of the same phenomenon: the campaigns previously measured
"the gate must test the deliverable's actual existence, not its description" (`cap_site_revamp_followup.md`);
this campaign adds the sharper form — **even existence-tested deliverables regress if the
gate never compares them to what they replaced.** Both are instances of the same principle:
information (measurement rules) must be the precondition for policy (control rules); a gate
that consumes no information about the incumbent is a gate that cannot protect it.

## p5 adversarial verification (2026-08-27)

The adversarial pass (`docs/reviews/cap_site_regression_analysis_adversary.md` +
`..._known_safe.md`) failed to falsify the analysis. It found and fixed four count errors
(all under-counting main: 30 not ~20 evidence tables, 15 not 14 glossary cards, populated
not empty `labs`, 4-of-5 evidence charts rendering on current data) and added six real losses
the p1 census had missed (the revamp data.js dropped the entire labs corpus — a build-gate
artifact, not an editorial decision; OG/social metadata, GitHub linking 21→2, the field-map
image, no-JS "not loaded" fallback, and methodology's footer were all lost in `54201491a`).
A separate agent with no prior exposure to this analysis independently reproduced the loss
list and concluded it would not have passed revamp2 — confirming the H3 independence test.

---

## Links

- Spec: `workflows/repository/cap_site_regression_analysis.yaml` (run on deepseek-v4-flash)
- Feature matrix: `experiments/results/cap_site_regression_analysis/feature_matrix.json`
- Attribution: `experiments/results/cap_site_regression_analysis/attribution.json`
- Mechanism: `experiments/results/cap_site_regression_analysis/mechanism.md`
- Post-mortem that raised the question: `docs/designs/current/cap_site_revamp_followup.md`
- The revamp's own research doc: `docs/designs/current/cap_site_revamp_research.md` (branch
  feature/site-revamp)
- The two self-reviews: `docs/reviews/cap_site_revamp_review.md` (branch),
  `docs/reviews/cap_site_revamp2_review.md` (branch)
- Independent review of the original: `experiments/reviews/gpt56_ux_review_v2.md`
- Adversarial verification: `docs/reviews/cap_site_regression_analysis_adversary.md` +
  `docs/reviews/cap_site_regression_analysis_known_safe.md`
