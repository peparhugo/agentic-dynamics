# Agentic Dynamics Rebrand Implementation Brief

> **SUPERSEDED (2026-08-15):** the "keep the existing Firebase host, do not acquire a new domain" decision in this brief is reversed. The site is now served from **two** Firebase projects — `ai-finops-rulebook` (canonical; the URL already shared with peers) and `agentic-dynamics` (mirror, forward-looking identity). Both serve the same `firebase/public/` and must be deployed together. See `AGENTS.md` → "Firebase dual-host (keep both synced)".

## Purpose

Rebrand the public repository identity and Firebase website from **AI FinOps Dynamics** to **Agentic Dynamics** without changing the instrument, its evidence, or its infrastructure.

The implementation is a naming and editorial change only. It must not become a technical rename, a data refresh, an evidence rewrite, or a hosting migration.

## Canonical Identity

- Field name: **Agentic Dynamics**
- Definition: **Agentic Dynamics is the empirical study of how AI agents behave, adapt, interact, recover, and produce outcomes across changing tasks, environments, workflows, and time.**
- Intended GitHub repository slug: `agentic-dynamics`
- Intended future repository URL: `https://github.com/peparhugo/agentic-dynamics`
- Public website URL: `https://ai-finops-rulebook.web.app`

The future GitHub URL retains the current owner, `peparhugo`, because the requested change specifies a slug rename rather than an ownership transfer. Do not substitute a different user or organization.

The canonical definition should appear verbatim in `README.md` and on the home page. Other pages should use shorter, page-specific descriptions that remain consistent with it.

## Scope Contract

### Files to change

The implementation file allowlist is:

1. `README.md`
2. `firebase/public/index.html`
3. `firebase/public/framework.html`
4. `firebase/public/evidence.html`
5. `firebase/public/story.html`
6. `firebase/public/methodology.html`
7. `firebase/public/accelerator.html`
8. `firebase/public/databricks.html`
9. `firebase/public/glossary.html`
10. `firebase/public/app.js`
11. `firebase/public/base.css`
12. `firebase/public/og-image.png`

This is the complete implementation allowlist. A rebrand patch should not modify files outside it.

### Audited files that do not need changes

- `scripts/build_data.py` does not emit the old public brand into `data.js`. Its only public identity-like output is the compatibility global `window.DYNAMICS_DATA`, which must remain unchanged. The old name in its module docstring and CLI help at current lines 2 and 1167 is operator-facing source text outside the strict public scope.
- `firebase/public/data.js` is generated evidence. Do not edit or regenerate it for this rebrand.
- `firebase/public/robots.txt` and `firebase/public/sitemap.xml` contain only the retained `https://ai-finops-rulebook.web.app` host. They are correct as-is.
- `firebase/CONTEXT.md` documents the retained Firebase project and the website. Its current line 16 contains the old name, but this internal context file is outside the requested README and `firebase/public/` implementation scope.
- `firebase/.firebaserc` and `firebase/firebase.json` describe the existing Firebase project and hosting configuration. They must not change.

### Explicit exclusions

Do not rename or rewrite:

- The Python distribution, import namespace, source modules, scripts, or package paths.
- Environment variables, Redis keys, Redis ports, Docker services, queue names, or Firebase project identifiers.
- Experiment directories, worktrees, reports, transcripts, reviews, generated inventory, generated data, superseded plans, or Git history.
- Data contracts such as `window.DYNAMICS_DATA`.
- Persisted browser keys such as `ai-finops-theme`.
- Measurements, formulas, thresholds, model names, provider names, provenance classes, or generated values.
- External proper names, including the FinOps Foundation.
- Old internal identifiers or historical path strings outside the allowlist.

Do not acquire, configure, propose, or mention a new custom domain in public copy. The `ai-finops-rulebook.web.app` hostname is intentional infrastructure, not a missed rebrand string.

## Repository Rename Coordination

Changing GitHub itself is a manual follow-up and is not part of this implementation workflow.

1. Merge or prepare the public-file changes using the intended future URL.
2. Manually rename the GitHub repository slug from `ai-finops-framework` to `agentic-dynamics` in GitHub settings.
3. Confirm `https://github.com/peparhugo/agentic-dynamics` resolves publicly.
4. Publish the README and Firebase update in coordination with that rename so clone commands do not point to a nonexistent repository.
5. Do not rename the local package, imports, modules, Firebase project, or any other technical identifier after the GitHub rename.

The public link mapping is:

| Use | Current | Intended |
|---|---|---|
| Browser link | `https://github.com/peparhugo/ai-finops-framework` | `https://github.com/peparhugo/agentic-dynamics` |
| Clone URL | `https://github.com/peparhugo/ai-finops-framework.git` | `https://github.com/peparhugo/agentic-dynamics.git` |
| Checkout directory | `ai-finops-framework` | `agentic-dynamics` |

## Exact Passage Plan

Line numbers below describe the audited pre-implementation files. They will shift as edits are made.

### `README.md`

- Line 1, `# AI FinOps Dynamics`: change to `# Agentic Dynamics`.
- Lines 15-17, `## What This Is` and its opening paragraph: insert the canonical definition verbatim before the existing instrument description. Keep the controlled-perturbation description rather than reducing the repository to a general manifesto.
- Line 9, website badge: keep the link target `https://ai-finops-rulebook.web.app`, but change the visible Shields label from `ai-finops-rulebook.web.app` to `Agentic Dynamics`. A suitable source is `https://img.shields.io/badge/website-Agentic%20Dynamics-%236366F1`.
- Lines 171-172, clone command and directory: change the repository URL to `https://github.com/peparhugo/agentic-dynamics.git` and the directory to `agentic-dynamics`. Keep `pip install -e .` unchanged.
- Lines 264-265, BibTeX identity: change citation key `ai-finops-dynamics-2026` to `agentic-dynamics-2026` and title prefix `AI FinOps Dynamics:` to `Agentic Dynamics:`. Keep the author, year, Firebase URL, version, corpus counts, and subtitle `An experimental instrument for the economics of agentic AI` unchanged.
- Line 257, `The framework measures cost`: optionally use `The instrument measures cost` to avoid treating the old repository noun as the new field name. Preserve the complete limitation and DeepSeek non-endorsement.
- Do not change `## Observed Dynamics`, the phrase `FinOps question` at line 42, the FinOps Foundation link at line 78, or economics terminology.

Design reason: the README should introduce a field first, then identify this repository as one measurement instrument within that field. That distinction prevents the rebrand from presenting one codebase as the full definition of Agentic Dynamics.

### Shared GitHub links in all HTML pages

Replace every public link to `https://github.com/peparhugo/ai-finops-framework` with `https://github.com/peparhugo/agentic-dynamics` at these current lines:

- `firebase/public/index.html`: 59, 125, 184, 192
- `firebase/public/framework.html`: 244, 913
- `firebase/public/evidence.html`: 81, 518, 958
- `firebase/public/story.html`: 47, 223
- `firebase/public/methodology.html`: 39, 66, 204, 283
- `firebase/public/accelerator.html`: 104, 435
- `firebase/public/databricks.html`: 51, 203
- `firebase/public/glossary.html`: 28, 121

On `methodology.html` lines 66 and 204, also change each visible `cd ai-finops-framework` to `cd agentic-dynamics`. Keep all install and run commands after that directory change byte-for-byte unchanged.

Six footers currently use `Framework` as the label for `href="/"`. Change only those labels to `Home` at `evidence.html:959`, `story.html:224`, `methodology.html:284`, `accelerator.html:436`, `databricks.html:204`, and `glossary.html:122`. Keep each `/` destination unchanged. The `framework.html` page and its `Operational Framework` title remain valid.

Design reason: these are public navigation and reproduction instructions, so they should follow the intended public slug. No internal path or package rename follows from this URL change.

### `firebase/public/index.html`

- Line 5, `<title>`: `AI FinOps Dynamics — Success Is Not Value` becomes `Agentic Dynamics — Success Is Not Value`.
- Line 7, `og:title`: apply the same brand-only replacement.
- Line 63, `Why — AI FinOps Dynamics`: change to `Why — Agentic Dynamics`.
- Line 172, `A measurement question became AI FinOps Dynamics.`: change to `A measurement question became Agentic Dynamics.`
- Line 173, field definition paragraph: begin with the canonical definition verbatim. Follow it with the existing evidence-grounded explanation of cost, verification, maintainability, recovery, long-horizon value, and controlled policy arms. Do not imply that routing has already been validated.
- Line 190, footer: change only `AI FinOps Dynamics` to `Agentic Dynamics`; retain `v0.9` and `August 2026`.
- Keep lines 6 and 8 factual metadata intact unless adding the field name without changing `1,097 sessions`, `7 models`, or `10,535 tests`.
- Keep the canonical URL and social-image URL on the `ai-finops-rulebook.web.app` host.

Narrative: define the field, establish the durable-value measurement gap, show how linked sessions and multiple measurement angles expose it, then present the instrument-to-policy cycle. Cost is one observed dimension, not the definition of the field.

### `firebase/public/framework.html`

- Line 5, `<title>`: `Operational Framework — AI FinOps Dynamics` becomes `Operational Framework — Agentic Dynamics`.
- Line 6, meta description: change only `derived from AI FinOps Dynamics` to `derived from Agentic Dynamics`. Preserve `10 rules`, `1,097 story sessions`, and `227 perturbation experiments`.
- Line 7, `og:title`: apply the title replacement.
- Line 687, table heading `AI FinOps Concept`: change to `Agentic Dynamics Concept`. The rows can continue to describe financial, routing, SLA, and workforce-management applications.
- Line 911, footer: change the brand only; retain `v0.9` and `August 2026`.

Narrative: present the page as an operating model for converting events into information and information into testable control policies. FinOps remains an economics application lens, while Agentic Dynamics is the umbrella field.

### `firebase/public/evidence.html`

- Line 5, `<title>`: `The Evidence — AI FinOps Dynamics` becomes `The Evidence — Agentic Dynamics`.
- Line 7, `og:title`: apply the same replacement.
- Line 361, the Databricks comparison insight: replace `Our experiments support what Databricks found` with neutral wording such as `Databricks and this instrument examine related operational concerns`. Replace `map directly to principles in AI FinOps Dynamics` with wording that says the four levers overlap with questions this instrument can measure or test; do not call them established principles of the field. Replace `We call it Grit` with wording that identifies Grit as a complementary stress-integrity measure rather than another name for the Efficiency Frontier. Preserve the date, attribution, four levers, both concept names, `10` operators, and `227` experiments.
- Line 509, `the first open instrument for AI FinOps Dynamics`: change the field name to `Agentic Dynamics`. Preserve `v0.5` and the roadmap qualification.
- Line 513, `The framework does not judge`: change only `The framework` to `The instrument` so the limitation names this repository rather than the field. Preserve the full caveat and every value.
- Line 949, field-defining paragraph: replace the old field name with `Agentic Dynamics` and align the sentence with the canonical definition. Preserve the separation between the archived precursor and current story corpus, and preserve the qualification that future control rules still require testing.
- Line 956, footer: change the brand only; retain `v0.9` and `August 2026`.
- Line 233, `A FinOps model that prices session 5 like session 1`: retain unchanged because it refers to financial-operations modeling rather than the retired project name.

Narrative: lead with the current linked-story corpus, keep each measured dimension separate, and identify the 227-run perturbation corpus as a historical precursor rather than merging datasets. The page should demonstrate the field through evidence without changing or strengthening any claim.

### `firebase/public/story.html`

- Line 5, `<title>`: `The Story — AI FinOps Dynamics` becomes `The Story — Agentic Dynamics`.
- Line 7, `og:title`: change `AI FinOps Dynamics` to `The Story — Agentic Dynamics` for page-specific social context.
- Line 81, `the Dynamics corpus`: change to `the Agentic Dynamics corpus` so the public reference is unambiguous.
- Line 177, field-of-inquiry paragraph: replace the old field name and incorporate the canonical definition. Keep `not a product` and retain the immediate-cost, durable-verification, maintainability, recovery, routing, and long-horizon-economics distinctions.
- Line 221, footer: change the brand only; retain `v0.9` and `August 2026`.

Narrative: retain the first-person origin from a `$20` API key through controlled perturbation and linked sessions. The conclusion should be the discovery of a broader empirical field, not a product launch or a cheaper-model verdict.

### `firebase/public/methodology.html`

- Line 5, `<title>`: `The Instrument — AI FinOps Dynamics` becomes `The Instrument — Agentic Dynamics`.
- Line 6, meta description: change `behind AI FinOps Dynamics` to `for Agentic Dynamics`. Preserve all four corpus counts in the sentence.
- Line 7, `og:title`: apply the title replacement.
- Line 173, visible card title `finops`: change only the visible title to `Cost Measurement`. Keep its USD-cost methodology and all derived measures. Do not rename a class, selector, data key, or source module.
- Line 250, CTA `Explore AI FinOps Dynamics`: change to `Explore Agentic Dynamics`.
- Line 255, `The concepts in AI FinOps Dynamics`: change the field name to `Agentic Dynamics`. Do not change external research names or coined metric names.
- Line 263, literature row mapping Grit directly to `Efficiency Frontier for Coding Models`: qualify the relationship as complementary rather than equivalent. Preserve `Grit (Ground-Truth Integrity)`, the Databricks title/link/attribution, and the evidence values elsewhere on the page.
- Line 281, footer: change the brand only; retain `v0.9` and `August 2026`.

Narrative: explain this repository as an instrument for observing behavior and economics under degraded information. Preserve the boundaries among the historical perturbation corpus, trajectory corpus, and current linked-story corpus.

### `firebase/public/accelerator.html`

- Line 6, meta description: change `derived from AI FinOps Dynamics` to `derived from Agentic Dynamics`.
- Line 7, `og:title`: change to `Applications — Agentic Dynamics`.
- Line 14, `<title>`: `Applications — AI FinOps Dynamics` becomes `Applications — Agentic Dynamics`.
- Line 166, `powered by precision AI FinOps`: change to `powered by Agentic Dynamics measurement and precision FinOps`. Preserve `249 experiment sessions`.
- Line 168, `Precision FinOps Measurement`: retain as an application capability, not the field name.
- Line 300, table heading `AI FinOps Concept`: change to `Agentic Dynamics Concept`.
- Line 371, `AI FinOps Dynamics isn't theory. It's a calibrated instrument`: replace the subject with `This Agentic Dynamics instrument` so the field is not equated with one repository. Preserve `249 sessions`, `10 perturbation operators`, and `7 recovery signals` and do not strengthen the implementation claims.
- Line 413, `The framework is Apache 2.0 licensed`: change `The framework` to `The instrument`; preserve `34 configs`, `249 sessions`, the license, and the surrounding reproducibility claims.
- Line 419, `The framework measures what that reasoning costs`: change `The framework` to `The instrument`; preserve the complete cost and routing statement.
- Line 421, link text `Framework Overview`: change to `Agentic Dynamics Overview`. Keep the `/` destination unchanged.
- Line 433, footer: change the brand only; retain `v0.9` and `August 2026`.

Narrative: label this page clearly as applications and future work. FinOps, routing, workforce management, verification, planning, and bounded autonomy are candidate applications of Agentic Dynamics. Enterprise projections and unexecuted control policies must remain labeled modeled, directional, hypothetical, or not independently validated as they are now.

### `firebase/public/databricks.html`

- Line 5, `<title>`: `Related Work — AI FinOps Dynamics` becomes `Related Work — Agentic Dynamics`.
- Line 7, `og:title`: change to `Related Work — Agentic Dynamics`.
- Line 8, `FinOps Foundation`: retain unchanged as an external proper name. Correcting whether the metadata accurately summarizes the body is a separate editorial task.
- Line 57, `Databricks playbook · AI FinOps instrument`: change to `Databricks playbook · Agentic Dynamics instrument`.
- Line 58, `Two Methods, Same Answer`: change to `Two Methods, Convergent Questions` or equivalently cautious wording.
- Line 59, `We arrived at the same four conclusions` and the two validation sentences: rewrite to say that the sources reached related operational conclusions through different evidence. State that Databricks contributes enterprise survey evidence and this instrument contributes controlled stress-test evidence. Remove `Their industry data validates our methodology` and avoid claiming that this project validates Databricks.
- Line 65, `Framework source`: change to `Instrument source`.
- Line 72, `The Efficiency Frontier = Grit`: change to `The Efficiency Frontier and Grit`.
- Line 76, `Same concept, independently discovered`: replace with wording that calls the concepts complementary rather than identical. Efficiency Frontier concerns price for a level of intelligence; Grit concerns integrity under degraded input.
- Lines 85, 100, 116, 132, and 148, `This framework`: change to `This instrument`; do not alter adjacent evidence.
- Line 137, `Our framework adds forecasting`: change to `This instrument adds forecasting` without changing the Snowball or EPM claims.
- Line 160, `The FinOps Framework`: change to `The Agentic Dynamics instrument`.
- Line 191, bottom-line paragraph: retain the four areas of convergence, `227 controlled experiments`, provenance, and open-source reproducibility, but remove `Their production data validates our methodology` and `Our stress tests ground their findings`. Describe the sources as complementary evidence with different scopes.
- Line 201, footer: change the brand only; retain `v0.9` and `August 2026`.

Narrative: frame the page as related work with convergent operational conclusions from different methods. Databricks provides enterprise survey evidence; this instrument provides controlled measurements. Do not claim that either source validates the other's methodology, and do not collapse Efficiency Frontier and Grit into identical measures. These edits correct field-defining framing and evidence boundaries only; they must not alter any attributed finding, number, date, or provenance class.

### `firebase/public/glossary.html`

- Line 5, `<title>`: `Glossary — AI FinOps Dynamics` becomes `Glossary — Agentic Dynamics`.
- Line 6, meta description: replace `Every coined term in AI FinOps Dynamics, defined in one place.` with `Terms used in Agentic Dynamics, defined in one place.`
- Line 7, `og:title`: change to `Glossary — Agentic Dynamics`.
- Line 32, visible lead: use the same `Terms used in Agentic Dynamics, defined in one place.` wording.
- Line 119, footer: change the brand only; retain `v0.9` and `August 2026`.

Narrative: identify project-defined measures, established vocabulary, external frameworks, and hypotheses without implying that this project coined external terms such as GRPO, SFT, IEA, or the 4Ms Framework.

### `firebase/public/app.js`

- Line 1, public source comment: change `AI FinOps Dynamics — Shared JavaScript` to `Agentic Dynamics — Shared JavaScript`.
- Lines 6 and 17, `ai-finops-theme`: do not change. It is a persisted browser-storage key, and renaming it would discard user preference state for no functional benefit.
- Lines 22 and 25, `window.DYNAMICS_DATA`: do not change. It is the generated public data contract.

Design reason: the downloadable source comment is public identity, while storage and global names are compatibility contracts.

### `firebase/public/base.css`

- Line 1, public source comment: change `AI FinOps Dynamics — Shared Base Styles` to `Agentic Dynamics — Shared Base Styles`.
- Do not rename selectors, custom properties, classes, IDs, or design tokens. None encode the retired public field name.

### `firebase/public/og-image.png`

Replace the existing social image in place so all existing `og:image` links continue to work. The approved Agentic Dynamics artwork is retained as a source asset and its wide variant is resized to the existing 1200 x 630 Open Graph contract.

- Replace visible `AI FinOps Dynamics` with `Agentic Dynamics`.
- Use a concise instrument-specific subtitle consistent with the canonical definition.
- Do not embed changing corpus totals in the social image.
- Preserve the existing social-image path: `https://ai-finops-rulebook.web.app/og-image.png`.

Design reason: changing HTML alone would leave the old identity visible in link previews. Replacing the asset in place avoids URL churn and preserves cached metadata contracts.

## Page-Level Narrative

The site should read as one sequence:

1. **Home:** Define Agentic Dynamics, state the durable-value measurement gap, and introduce linked measurements.
2. **Instrument:** Explain how controlled perturbation, linked sessions, event capture, and analysis make agent behavior observable.
3. **Evidence:** Report current and historical evidence without merging corpora or changing confidence boundaries.
4. **Framework:** Show how measured information can support testable policies and controlled campaigns.
5. **Story:** Explain how a cost anomaly expanded into a field concerned with behavior, adaptation, recovery, interaction, outcomes, and time.
6. **Applications:** Present FinOps, routing, workforce management, and autonomy as applications and future experiments, not as already validated enterprise products.
7. **Related Work:** Compare methods and conclusions without overstating validation or equivalence.
8. **Glossary:** Define the field's vocabulary while distinguishing original terms from external ones.

Across all pages, use `Agentic Dynamics` as the field name and `the instrument`, `this project`, or `this repository` for the codebase. Do not use `framework` as a substitute proper name except in the page title `Operational Framework` or when discussing a genuine external framework. Review every generic `This framework`, `Our framework`, and `The framework` reference in the eight pages; in addition to the passages listed above, replace only references that clearly name this repository, and leave conceptual or external-framework uses intact.

## References That Must Remain

### Infrastructure identity

- Every `https://ai-finops-rulebook.web.app` URL, including Open Graph URLs, the README website link, `robots.txt`, `sitemap.xml`, and the citation URL.
- Firebase project ID `ai-finops-rulebook`.
- Existing page paths and the `og-image.png` path.
- The statement that no custom domain is being acquired or configured should remain an implementation constraint, not become public marketing copy.

### Generic FinOps and economics references

- `README.md` line 42: `the FinOps question` about durable value.
- `README.md` line 78: `FinOps Foundation: AI tools & services` and its external URL.
- `README.md` line 162: `FinOps Foundation` as related work.
- `firebase/public/evidence.html` line 233: `A FinOps model that prices session 5 like session 1...`.
- `firebase/public/accelerator.html` line 168: `Precision FinOps Measurement`.
- `firebase/public/databricks.html` line 8: `FinOps Foundation`, an external proper name.
- References to task economics, provider economics, cost per outcome, financial operations, budgeting, pricing, and energy economics.

These remain because FinOps is an economics subfield and an application area within the broader Agentic Dynamics identity. The rebrand must remove the old compound proper name, not erase the subject matter.

### Historical evidence and external attribution

Retain all references to Databricks, the FinOps Foundation, IEA, Google Cloud 4Ms, Zhuang et al., DeepSeek, Anthropic, OpenAI, provider pricing, Apache 2.0, and dates. Preserve labels that identify a corpus as archived, precursor, current, measured, computed, modeled, heuristic, external, directional, or hypothetical.

Do not reconcile differing corpus snapshots during the rebrand. Values such as `221 stories`, `1,097 sessions`, `227 experiments`, `224 reports`, `249 sessions`, `255 transcripts`, `347 sessions`, and `2,000+ sessions` refer to different views or historical snapshots. Their coexistence is not permission to rewrite them.

### Internal technical identifiers

Retain exactly:

- `window.DYNAMICS_DATA`
- `ai-finops-theme`
- `data.js`, `app.js`, and `base.css`
- `src/instrument/`, `scripts/`, `experiments/`, and `firebase/public/`
- `opencode.db`, `inventory.json`, `_results_summary.json`, `_trajectory_aggregate.json`, and `session.jsonl`
- Model IDs, provider IDs, backend names, CLI flags, config names, operator names, metric names, and function names
- All HTML IDs, anchors, SVG IDs, CSS classes, CSS custom properties, and `data-*` attributes
- `data-stat`, `data-stat-fmt`, `data-anal-model`, and `data-anal`
- The anchor `id="dynamics"`
- Grit, Ground-Truth Integrity, Explanation Tax, WOC, AI Value Efficiency, Snowball, EPM, and their existing symbols

## Evidence And Value Lock

This rebrand has a zero-data-change rule. In the implementation diff, every numeric literal, formula, unit, date, version, model/provider label, dynamic binding, and provenance label in the allowlisted text files must remain byte-for-byte unchanged unless this brief explicitly identifies that value as part of a brand-bearing URL or checkout directory. Confidence qualifiers also remain unchanged except for the exact qualitative overclaim corrections identified for `evidence.html:361`, `methodology.html:263`, and `databricks.html:58-59,72,76,191`; those corrections may narrow claims of equivalence or validation but must not alter underlying evidence or strengthen any claim.

This rule is the complete protected-value list. It includes fallback values in HTML and JavaScript, values rendered from `window.DYNAMICS_DATA`, calculator defaults, chart data, table cells, image statistics, release versions, and historical counts. CSS layout dimensions are not experimental values, but they also require no change.

### Provenance markers

Preserve these markers and meanings exactly wherever they occur:

- `[M]` and `[M] measured`
- `[C]` and `[C] computed`
- `[H]` and `[H] heuristic`
- `[X]` and `[X] external`
- `[P]` if introduced by generated data or existing contracts, even though no literal `[P]` appears in the audited eight pages
- Composite forms such as `[M/C]`, `[mixed]`, `[tests]`, and lowercase `design`
- Visible evidence labels including `Observed`, `Derived`, `Measured`, `Modeled`, `Controlled`, `Extension`, `Scenario input`, `Directional`, `hypothetical`, and `not independently tested`

Do not change capitalization or collapse one evidence class into another.

### Protected formulas and thresholds

Preserve all formulas exactly, including their HTML entity forms where applicable:

- `G(s) = P(test_executed_success | perturbation_strength=s)`
- `R(s) = Grit(s)/Grit(0)`
- `Delta C = C(successful perturbed)/C(successful baseline)` and the displayed `ΔC` form
- `c(t) = C0 x EPM(t) x (1 + beta x v x t)` and its displayed symbol/entity form
- `C(N,v) = C0 x EPM(N) x [N + beta x v x N(N-1)/2]`
- `CostPerOutcome(K,v) = C(K/P,v)/K`
- `Cmo = E x C0 x EPM(N) x [N + beta x v x N(N-1)/2]`
- `Cjob = C0 x EPM x (1-b x 0.5) x (1+r x Em)`
- `Cauto = W x Cjob`
- `Tmax = Budget/Cjob`
- `WOC = 1/(1+r)`
- `BVI = WOC/(Cjob+H/W)`
- `Ctotal = Caugmented+Cautonomous+H`
- `Gap = (A x Verbosity x (1+epsilon)) x EPM(N)`
- `Throughput = Budget / (cost_per_job x (1 + retry_rate))`
- `rounds = 1 + floor(strength x 3)`
- `N x M`, `G x N x M`, `N^2`, `beta x v x N^2`, and their displayed Unicode/HTML forms

Preserve associated fixed assumptions and thresholds, including `beta=0.001`, `r=0.115`, `WOC=0.90`, healthy/critical WOC boundaries, batch discounts, escalation ratios, energy projections, provider prices, cache thresholds, and calculator defaults.

### Protected values by public surface

- `README.md` and `og-image.png`: `249 sessions`, `224 game reports`, `8 model variants`, `3 provider families`, `34 configs`, `10 operators`, `$64.98`, `255 session.jsonl transcripts`, `13 plans`, `8 pages`, `21 cross-model runs`, `1.6%/yr`, `$20`, `v0.5`, and `Apache 2.0`.
- `index.html`: `1,097`, `7`, `221`, `$288.69`, `3 codebases`, `2 tiers`, five linked stages, three conditions, `41x`, `$0.09`, `$3.75`, `~10`, `2.9x`, `$1.59`, `$4.58`, `~120`, `10x`, `$0.16`, `$0.34`, `18.7K`, `34.9K`, `~2x`, `~47K`, `$0.07`, `98%`, `6.3K`, `85%`, `$1.48/story`, `88%`, test counts `7/9/13/34/34/117/122`, `10,535 tests`, `v0.9`, and `August 2026`.
- `framework.html`: `10 rules`, `1,097 sessions`, `227 experiments`, all calculator inputs/ranges, `$0.005-$1.01/session`, provider and cache prices, `72%`, retry/escalation rates and ratios, `1.6%/yr`, `2.5%/yr`, `0.8%`, all projection horizons, all routing ranges, all rule thresholds, and every chart fallback.
- `evidence.html`: all current-corpus counts and costs; all seven model rows; all review, static-analysis, LSP, trajectory, basin, narration, token, cache, energy, operator, quality, and strategy values; all historical `227`-experiment and `224`-report values; all table fallbacks; and known displayed distinctions such as `$42.52`, `$42.30`, and `$47.54`.
- `story.html`: `$20`, `$700/month`, `$2.04`, `$12.54`, `$12.73`, `$4.64`, `17x`, `249`, `347`, `224`, `8`, `3`, `227`, `11%`, `8%`, `14%`, `8.5%`, `11.5x`, `$10.00`, `$0.87`, `78%`, `35K`, `97-98%`, `6K`, `73 tests/$2.32`, `7 tests/$0.09`, `2,000+`, `1,097`, `221`, `911`, `700W`, `220%`, `6.7-12%`, `1.8x`, `2050`, and `2%`.
- `methodology.html`: `249`, `8`, `10`, `7`, `34`, `227`, `222`, `2,215`, `1024-dim`, all operator counts/classes/strengths, `18` patterns, `37` terms, all trajectory distances, `350W`, `700W`, `69x`, provider prices, `~11K`, `112.6%`, `25+` extensions, `6-50%`, `1.80x`, `2050`, and `$64.98`.
- `accelerator.html`: `249`, `8`, `3`, `10`, rule split `1-5` and `6-10`, `69x`, `$64.98`, all enterprise scenario inputs, WOC/retry/escalation values, maturity levels, time windows, SLA values, cascade tiers, budget/job tables, provider/cache prices, energy/modeling horizons, and footer data bindings.
- `databricks.html`: `August 7, 2026`, `July 2026`, `227`, `8`, `3`, `10`, four conclusions, all external estimates, `$0.02/session`, `$1.08/session`, `69x`, `~11K`, `95% at $0.12/session`, `17`, `14/17`, `3/17`, `0.90`, all narration/cache values, `94%`, `escape=0.76`, `50%`, and `72-hour`.
- `glossary.html`: every definition, score range, threshold, provider/cache price, generated narration value, and all formula constants, including `beta=0.001`, `1.6%/yr`, `2.5%/yr`, `r=0.115`, `WOC=0.90`, healthy `>=0.90`, critical `<0.70`, `2x`, and `10x`.
- `app.js`: all formatting behavior and formulas, including `toFixed`, `Math.round`, `toLocaleString`, fallback selection, totals, ratios, WOC rendering, narration calculations, generated heading IDs, 32-character TOC shortening, and the 300-pixel visibility threshold.

These grouped lists are reminders for review, not exceptions to the stronger zero-data-change rule.

## Implementation Sequence

1. Change README identity, canonical definition, badge label, clone path, and citation.
2. Change all eight HTML titles, brand-bearing metadata, field-defining prose, footers, and GitHub links according to the passage map.
3. Change only the public source comments in `app.js` and `base.css`.
4. Replace `og-image.png` in place with the approved Agentic Dynamics artwork and retain the field map as a source asset.
5. Search the allowlisted files for `AI FinOps Dynamics`, `AI FinOps`, and `ai-finops-framework`.
6. Classify every remaining `FinOps` or `ai-finops` match as retained infrastructure, generic economics, external proper name, or an error.
7. Confirm no generated data or technical identifier changed.
8. Run the focused spec and data-integrity tests plus a local static-site check before deployment. The full suite includes experiment and integration workloads unrelated to this content-only cutover.
9. Coordinate deployment with the manual GitHub slug rename.

## Acceptance Checks

### Identity and links

- `README.md` and the home page contain the canonical definition verbatim.
- Every page title, Open Graph title, visible field reference, and footer uses `Agentic Dynamics`.
- No visible HTML or social-preview asset presents `AI FinOps Dynamics` as the current field name.
- Every public repository link and clone command uses `peparhugo/agentic-dynamics`.
- The GitHub rename itself is recorded as a manual follow-up and is not attempted by repository code.
- Every website, canonical-like, Open Graph, robots, sitemap, and citation URL remains on `https://ai-finops-rulebook.web.app`.
- No custom domain is introduced.

### Technical and evidence integrity

- `git diff -- firebase/public/data.js scripts/build_data.py firebase/.firebaserc firebase/firebase.json` is empty.
- `window.DYNAMICS_DATA` and `ai-finops-theme` are unchanged.
- No import, package, environment variable, Redis key/service, Docker service, source path, experiment path, data contract, selector, ID, or generated artifact is renamed.
- A value-focused diff confirms no measurement, formula, threshold, date, version, provenance marker, or model name changed. Evidence qualifiers change only in the explicitly listed overclaim corrections, and only to narrow the claims.
- Historical corpora remain separate and all external attributions remain intact.
- Generic FinOps and FinOps Foundation references listed in this brief remain.

### Verification

- Open all eight pages at desktop and mobile widths and verify navigation, theme persistence, dynamic data injection, charts, calculator behavior, and internal anchors.
- Verify the new `og-image.png` is 1200 x 630, displays `Agentic Dynamics`, and remains reachable at the existing Firebase URL after deployment.
- Check all 21 website GitHub references plus the README clone URL after the manual slug rename.
- Run `python3 -m pytest tests/test_experiment_spec.py tests/test_data_integrity.py -q`.
- If generator validation is needed, run `python scripts/build_data.py --dry-run` so `data.js` is not rewritten. Do not run the writing mode or commit regenerated data as part of the rebrand.

## Completion Boundary

The code rebrand is complete when the README, eight website pages, public source comments, and social image consistently present **Agentic Dynamics**; the future repository links use `agentic-dynamics`; the existing Firebase host remains; and all evidence and technical contracts are unchanged. The actual GitHub repository rename remains an operational cutover step.
