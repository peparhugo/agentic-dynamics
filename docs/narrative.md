# Evidence Page Narrative Design

## 1. Golden-Circle Thesis

`firebase/public/evidence.html` should tell one chronological discovery story about two distinct corpora. It should use Simon Sinek's Golden Circle explicitly, moving from the center outward:

1. **WHY, the center: the unmeasured gap.** A successful coding session does not reveal how a model responds to degraded information, how much recovery costs, how thoroughly the model verifies its own work, or what happens when that work becomes the next session's starting point. The research began because those dynamics were invisible, not because the project needed a product page.
2. **HOW, the ring: the instrument and its N x M scaling.** The first instrument varied perturbations across single-session runs and measured search dynamics. The current instrument scales the same question across linked story sessions and multiple independent measurement angles. `N x M` means many observations multiplied by many ways of examining each observation, not one composite score and not a larger benchmark leaderboard.
3. **WHAT, the outside: the findings and the field.** The two corpora expose recovery, verification, cost, quality, and compounding behavior as separate dimensions. Together they motivate AI FinOps Dynamics as a field of measurement. They do not become one pooled dataset, and the page must not imply that either corpus is a subset of the other.

The page should name the circle in the hero and then enact it. A short WHY opens the page, the chronological experiment record shows HOW the measurement evolved, and the findings from each stage form the WHAT. This order makes the instrument evidence of discovery rather than the object being sold.

### Thesis copy

The hero may use the following framing, with the two live corpus summaries immediately below it:

> **WHY / HOW / WHAT.** We began with an unmeasured gap: a passing result could not tell us how a model searched, recovered, verified, or changed the cost of the next session. We first built controlled single-session perturbation experiments to make search dynamics visible. Those experiments discovered the operators and recovery signals that the current multi-session story instrument reuses. What emerged is a field view of agentic work across cost, verification, quality, recovery, and time.

The design decision is to mention both corpora before showing either one. Readers should understand from the first screen that they are about to see a chronology, not a single homogeneous sample.

## 2. Corpus Boundary And Chronology

The current page leads with the story corpus and relegates the earlier work to a section titled "Legacy." Reverse that order. "Archived precursor" is the preferred label because it states status without implying that the evidence is obsolete or part of the current story matrix.

### Full-corpus ledger

Place two adjacent scope cards under the hero. Do not add their observations together or use a shared label such as "total sessions."

| Corpus | Status and time | Scope to show | Measurement role | Provenance rule |
|---|---|---|---|---|
| Single-session perturbation corpus | **Archived precursor, first** | Approximately 227 classified single-session runs, 224 game reports where that is the relevant denominator, 201 Grit-matrix sessions where that is the relevant denominator, 8 model variants, and 10 perturbation operators | Controlled degradation revealed Grit, basin escape, recovery cost, flail behavior, strategy archetypes, and the seven recovery signals | Keep each existing denominator and its existing `[M]`, `[C]`, `[H]`, or `[X]` tag. Do not rewrite 227, 224, and 201 as if they counted the same artifact. |
| Multi-session story corpus | **Current instrument, second** | 1,097 sessions, 221 executed stories, 210 unique cells plus 11 reruns, 7 models, $288.6909 total story cost, 3 codebases, 2 tiers, 2 codebase qualities, and the existing conditions | Linked five-session builds measure natural verification behavior, review and static quality, solution dynamics, and compounding cost | Preserve the live `data-stat` bindings and their current formatting, including `1,097`, `221`, `7`, and `$288.69` on the rendered page. |

The ledger is a boundary device, not a new aggregate. It should include this sentence prominently:

> These are two distinct measurements. The 227 single-session perturbation runs came first; the 1,097 story sessions came later and reuse the precursor's operators and recovery signals. They are presented together as a chronology, not merged into one denominator.

### Chronological acts

1. **Prologue, WHY: what a passing result concealed.** Introduce the inability to observe search, recovery, verification disposition, and downstream cost from one successful output. Keep this conceptual and short so evidence, not manifesto, dominates the page.
2. **Act I, HOW began: archived single-session perturbation experiments.** Present the perturbation design, 10 operators, model coverage, limitations, and provenance legend before any perturbation finding. Replace "Legacy" with "Archived Precursor" while retaining `id="perturbation"`.
3. **Act I, WHAT was discovered.** Keep the entire perturbation evidence corpus in its existing internal order: Grit, flail rate, cost efficiency, AST and Sonar analysis, constraints, token cost, perturbation response, rollup, profiles, exploratory trajectory measures, operator impact, modeled energy, strategy distribution, sources, and independent validation.
4. **Bridge, WHY the instrument changed.** State that controlled single sessions made operators and recovery signals measurable, but could not show whether effects persist when one model output becomes the next session's codebase. That limitation motivated the linked story design.
5. **Act II, HOW now scales: current multi-session story instrument.** Introduce the `3 codebases x 2 tiers x 2 qualities x conditions` matrix, 5-session arcs, 7 models, 221 stories, and 1,097 sessions. Explicitly say that the story instrument reuses the precursor's perturbation operators and recovery signals rather than presenting the story corpus as an unrelated replacement.
6. **Act II, WHAT is visible now.** Present verification behavior first, then second-model reviews, AST/Sonar diagnostics, model dynamics, and the five-session cost arc. The natural-behavior caveat belongs at the start of the verification finding, not in a distant limitations footer.
7. **Epilogue, WHAT became a field.** Close by distinguishing observed evidence from open control questions. AI FinOps Dynamics is the outside of the circle: the study of how cost, verification, quality, recovery, and long-horizon value move together and where they separate.

This structure satisfies chronology without flattening the Golden Circle. The page moves outward once overall, while each experimental act contributes a HOW followed by its own measured WHAT.

## 3. Full-Overview Structure

Implementation should move existing DOM blocks rather than recreate their content. Moving a section with its tables, tooltips, provenance labels, and nearby inline script preserves the literal numbers and avoids accidental changes in rounding or denominator.

### Page outline

| Order | Proposed section | Existing material to move intact | Narrative purpose and design decision |
|---:|---|---|---|
| 1 | **The Evidence: WHY / HOW / WHAT** | Current hero shell, rebuilt as a two-corpus ledger | Establish the unmeasured gap and announce that the page covers the full corpus in chronological order. Do not use the current story-only hero sentence. |
| 2 | **WHY: The Gap A Passing Result Could Not Measure** | New prose only; no new metric | Name search dynamics, recovery, verification disposition, and compounding context as the reason measurement was required. |
| 3 | **Act I: Archived Precursor** | Current `#perturbation` introduction, perturbation TL;DR, provenance legend, and limitations | Put experimental design and caveats before findings. Retain all counts and tags exactly. |
| 4 | **Grit And Recovery** | `#grit-spectrum`, generated manifold/semantic heading, `#flail-rate`, `#grit-model-filters`, `#gritMatrixChart`, `#narration-tbody`, and `#narrationChart` | Show the first measurements that made degraded-input behavior legible. |
| 5 | **Economic And Code Outputs** | `#cost-efficiency`, `#cost-ranking`, `#cost-ranking-tbody`, `#costBarChart`, `#ast-analysis`, `#ast-metric-head`, `#ast-metric-body`, `#ast-insight`, generated Sonar heading, `#sonar-quality-body`, `#constraint-detection`, `#token-costs`, and `#token-cost-tbody` | Preserve the complete precursor overview rather than reducing it to Grit alone. |
| 6 | **Perturbation Response And Rollup** | `#perturbation-response`, `#perturbation-split`, `#cross-model-rollup`, `#rollup-tbody`, and `#locVsCostChart` | Keep per-class response and cross-model summaries within the archived corpus boundary. |
| 7 | **Scope, Profiles, And Research Notebook** | Generated current-scope heading, `#model-profiles`, `#model-cards-root`, `#tool-profiles`, `#tool-profile-body`, Research Notebook notice, `#reasoning-coherence`, `#rvs-body`, `#semantic-drift`, `#drift-body`, `#perturbation-recovery`, `#recovery-body`, `#think-do-coupling`, `#coupling-body`, `#cluster-stability`, `#stability-body`, `#divergence-cascades`, and `#cascade-body` | Preserve lower-confidence exploratory analyses, but keep their existing warning visibly above them so they are not promoted to primary evidence by the reorder. |
| 8 | **Quality, Operators, And Modeled Extensions** | `#sonar-impact`, `#sonar-impact-body`, `#operator-impact`, `#operator-impact-body`, Modeling Extensions notice, `#energy-ranking`, `#energy-ranking-cards`, `#drift-trajectories`, `#strategy-distribution`, `#data-sources`, and independent validation | Complete the archived corpus before crossing into the current instrument. `[C]` and `[X]` modeled material remains visibly distinct from measured billing and filesystem evidence. |
| 9 | **Bridge: What The Precursor Made Possible** | New transition copy | State the causal chronology plainly: the perturbation runs discovered reusable operators and recovery signals; the story instrument applies them across linked sessions to observe persistence and compounding. |
| 10 | **Act II: The Current Story Instrument** | Current story TL;DR, rewritten only for chronology and corpus scope | Introduce 3 codebases, 2 tiers, 2 qualities, existing conditions, 5 linked sessions, 221 stories, 1,097 sessions, 7 models, and $288.6909 without importing any perturbation denominator. |
| 11 | **Natural Verification Behavior** | `#story-models` section and its complete table, footnote, and findings | Lead the current-state evidence with the verification result. Insert the exact caveat from section 4 before interpreting Luna/Sonnet test-count differences. |
| 12 | **Independent Review And Static Quality** | `#reviews`, generated reviewer-flags heading, `#static-analysis`, and every `data-anal-model` row | Separate authored test volume from what a second model, AST analysis, SonarQube, conventions, and diagnostics observe. |
| 13 | **Solution Dynamics** | `#dynamics` and every `data-anal` cell | Show how the precursor's solution, basin, and strategy measurements carry into the current story instrument. |
| 14 | **The Five-Session Arc** | `#arc`, generated seed-perturbation heading, `#snowballChart`, and its inline chart script | End the current corpus with the longitudinal result that the precursor could not measure: cost and context compound as the codebase is inherited. |
| 15 | **WHAT: The Field Now Visible** | New synthesis plus existing source/CTA/footer elements as appropriate | Close with dimensions and open questions, not a purchasing recommendation. Keep both corpus names in the synthesis and keep the footer's live story bindings unchanged. |

### Bridge copy

Use this transition between the corpora:

> **The precursor found the signals; the story instrument followed them through time.** The archived runs showed how to perturb a specification and measure Grit, basin escape, recovery, flailing, and strategy in one session. They could not show whether those effects survived the handoff into the next task. The current instrument reuses those operators and recovery signals across five linked sessions, where each model inherits the code and context produced before it.

The bridge is necessary because visual order alone does not establish methodological inheritance. It must explicitly state that the second corpus was motivated by and reuses the first.

## 4. Exact Natural-Behavior Caveat

Place the following callout verbatim immediately below the `#story-models` lead and before the tests-per-story table or its first interpretive insight:

> **We never instructed the models how many tests to write.** Every model was asked to build the same system, but the number of tests and the edge cases covered were left entirely to the model. The difference between Luna at about 7 tests per story and Sonnet at about 122 is therefore natural, emergent behavior, not a failure to follow instructions. The verification gap measures the models' own unguided disposition toward verification, not instruction-following compliance.

This wording is deliberately plain. It establishes the experimental protocol before readers encounter the largest test-count contrast, prevents "fewer tests" from being misread as disobedience, and limits the finding to observed model behavior. Do not weaken it to a footnote, tooltip, or methodology link.

The surrounding finding should distinguish these quantities rather than treating them as synonyms:

- **Tests authored or counted:** how many tests the model chose to create.
- **Tests executed:** how many tests the apparatus actually ran.
- **Self-test pass rate:** whether those authored tests passed.
- **Independent review or correctness evidence:** what a second evaluator or another measurement method observed.

That distinction preserves the main result: the count difference is natural behavior, while the adequacy of those tests remains a separate question.

## 5. Number, Binding, And Provenance Preservation

This redesign changes order and explanatory prose only. It must not re-derive a number, pool corpora, alter displayed rounding, change a denominator, or move a claim from one provenance class to another.

### Provenance contract

| Tag | Existing meaning | Preservation rule |
|---|---|---|
| `[M]` | Measured from provider/session data, executed tools, or generated artifacts | Keep the tag and source boundary with the number. Reordering does not make a measurement universal. |
| `[C]` | Computed from measured values | Keep operands, denominator, rounding, and tag unchanged. Do not restate a ratio as directly measured. |
| `[H]` | Heuristic estimate, threshold, or classification | Keep the limitations text adjacent enough that readers cannot mistake the value for an executed test or direct observation. |
| `[X]` | External constant, estimate, projection, or cited source | Preserve the citation and do not imply that the corpus measured the external quantity. |

No `[P]` provenance tag currently appears on the page. The Golden-Circle narrative must use only the existing `[M]/[C]/[H]/[X]` legend unless the site's provenance system is changed separately.

### Live `data-stat` bindings that must remain byte-for-byte

The following supported bindings occur on the page and must survive the reorder with their current fallback text and formatting:

- `stories_total`
- `story_sessions`
- `variants`
- `story_total_cost`
- `reports`
- `sessions`

The cross-model rollup also contains these current bindings, which must not be renamed or dropped even where `app.js` presently leaves the fallback text in place:

- `rollup-ds-cost`, `rollup-g56-cost`, `rollup-claude-cost`, `rollup-all-cost`
- `rollup-ds-pass`, `rollup-g56-pass`, `rollup-claude-pass`, `rollup-all-pass`
- `rollup-ds-think`, `rollup-g56-think`, `rollup-claude-think`, `rollup-all-think`
- `rollup-ds-loc`, `rollup-g56-loc`, `rollup-claude-loc`, `rollup-all-loc`
- `rollup-ds-constraint`, `rollup-g56-constraint`, `rollup-claude-constraint`, `rollup-all-constraint`

Generated cost rows may emit `data-stat="ci95"`; preserve that attribute as part of the renderer contract. Do not add a new formatter or silently convert fallback literals during a narrative-only reorder.

### Analysis bindings that must remain intact

Keep all current `tr[data-anal-model]` values and all child `data-anal` fields unchanged. The model keys are `deepseek-v4-flash`, `gpt-5.6-luna`, `deepseek-v4-pro`, `claude-haiku-4-5`, `gpt-5.6-terra`, `claude-sonnet-5`, and `gpt-5.6-sol`. The bound fields are:

- Story static analysis: `commits`, `lines_added`, `functions_added`, `sonar_smells_delta`, `sonar_complexity_delta`, and `avg_convention`.
- Story dynamics: `solution_correctness`, `solution_constraints`, `solution_quality`, `solution_novelty`, `basin_escape`, and `lsp_errors_per_cell`.

These rows are populated by shared `app.js`. Copying table text while dropping the attributes would leave plausible-looking fallbacks and silently disconnect the page from rebuilt data.

### Movement rule

For each existing evidence block, move the opening section/comment, all prose, tables, tooltips, provenance markers, chart containers, and any immediately associated inline script as one unit. Leave the large footer script after all target elements. This guarantees that immediate IIFEs still run after their table bodies exist and that `DOMContentLoaded` renderers can still find every target regardless of narrative order.

## 6. Chart And Script Integrity Register

Every ID below is a DOM contract. Preserve spelling and case exactly. If implementation intentionally removes a target, guard its script lookup first; the preferred design is to retain every target so all charts and tables continue to render.

### Canvas and interactive controls

| Required ID | Element | Consumer | Why it must survive |
|---|---|---|---|
| `snowballChart` | `canvas` | Story-arc inline `DOMContentLoaded` handler | Renders current five-session average cost; the handler is guarded but deleting it would remove a required finding. |
| `grit-model-filters` | `div` | Large footer script | Receives generated model and perturbation-class filter buttons for the precursor Grit matrix. |
| `gritMatrixChart` | `canvas` | Large footer script | Renders and rebuilds the 201-session interactive precursor scatter plot. |
| `narrationChart` | `canvas` | Large footer script | Renders narration penalty by model. |
| `costBarChart` | `canvas` | Large footer script | Renders average cost per session by model. |
| `locVsCostChart` | `canvas` | Large footer script | Renders the code-output-versus-cost bubble chart. |

### Script-populated tables and containers

| Required ID | Element | Consumer and behavior |
|---|---|---|
| `narration-tbody` | `tbody` | Cleared and rebuilt by the large footer script. |
| `cost-ranking-tbody` | `tbody` | Cleared and rebuilt from model records. |
| `ast-metric-head` | `thead` | Its child `tr` receives generated model headers. |
| `ast-metric-body` | `tbody` | Receives generated AST metric rows. |
| `ast-insight` | `div` | Receives the generated AST summary. |
| `sonar-quality-body` | `tbody` | Receives generated Sonar rows. |
| `token-cost-tbody` | `tbody` | Cleared and rebuilt with token-cost rows. |
| `model-cards-root` | `div` | Receives model-card HTML and currently has no null guard, making preservation mandatory. |
| `tool-profile-body` | `tbody` | Receives the eight tool-profile rows from its adjacent IIFE. |
| `rvs-body` | `tbody` | Receives reasoning-volatility rows. |
| `drift-body` | `tbody` | Receives semantic-drift rows. |
| `recovery-body` | `tbody` | Receives perturbation-recovery rows. |
| `coupling-body` | `tbody` | Receives think/do coupling rows. |
| `stability-body` | `tbody` | Receives cluster-stability rows. |
| `cascade-body` | `tbody` | Receives divergence-cascade rows. |
| `sonar-impact-body` | `tbody` | Receives perturbation quality-impact rows. |
| `operator-impact-body` | `tbody` | Receives computed operator-impact rows. |
| `energy-ranking-cards` | `div` | Receives computed energy-ranking cards. |
| `strategy-distribution` | `div` | Receives the computed strategy bar and tags. This must be the unique renderer target. |

### Structural IDs to preserve

These IDs are not all directly queried today, but they are part of the page's table, loading-state, styling, or anchor contract and should survive a reorder:

- `no-data-row`
- `sonar-quality-tbl`
- `rollup-tbody`
- `tool-profile-tbody`
- `sonar-impact-tbody`
- `operator-impact-tbl`
- `data-sources`

### Duplicate-ID correction

The current HTML assigns `strategy-distribution` to both the heading and the renderer `div`. `document.getElementById('strategy-distribution')` can therefore select the heading and inject the chart into it. During the eventual HTML restructure:

- Keep `id="strategy-distribution"` on the renderer `div`, preserving both script lookup and the public fragment.
- Give the heading the explicit ID `strategy-distribution-heading`.
- Point the generated/manual TOC item at `strategy-distribution-heading` while leaving `#strategy-distribution` as a valid fragment target immediately below it.

This is the only ID split required by the narrative design. It fixes invalid DOM without deleting the existing public anchor or changing the renderer lookup.

## 7. Anchor And Link Integrity Register

Shared `app.js` builds the floating table of contents from every `h2` and `h3`, inventing a slug only when a heading has no ID. Reordering headings is safe; changing text-derived slugs is not. Make current runtime slugs explicit before changing heading copy.

### Public and authored anchor contract

- `#story-models` must remain on the verification section. `index.html` links directly to `evidence.html#story-models`.
- `#perturbation` must remain on the archived-precursor introduction.
- The current in-page `href="#story-models"` must remain valid. After reversing chronology, change only its visible direction from "Back to the story evidence" to a forward transition such as "Continue to the current story evidence."
- `#data-sources` must remain on the data-sources disclosure.
- `#strategy-distribution` must remain valid through the unique renderer target described above.

### Existing explicit heading anchors to retain

`story-models`, `reviews`, `static-analysis`, `dynamics`, `arc`, `perturbation`, `grit-spectrum`, `flail-rate`, `cost-efficiency`, `cost-ranking`, `ast-analysis`, `constraint-detection`, `token-costs`, `perturbation-response`, `perturbation-split`, `cross-model-rollup`, `model-profiles`, `tool-profiles`, `reasoning-coherence`, `semantic-drift`, `perturbation-recovery`, `think-do-coupling`, `cluster-stability`, `divergence-cascades`, `sonar-impact`, `operator-impact`, `energy-ranking`, and `drift-trajectories`.

### Current runtime-generated anchors to make explicit

- `what-the-reviewer-flags`
- `does-perturbing-the-seed-change-the-whole-arc`
- `manifold-vs-semantic-grit-deepseek-vs-claude`
- `code-quality-sonarqube-static-analysis`
- `current-scope-whats-next`

Making these IDs explicit decouples links from punctuation or title changes. Keep all existing navigation, GitHub, methodology, `data.js`, BGE-M3, CTA, and footer `href` values working. Narrative reordering does not justify changing destinations.

## 8. Implementation Acceptance Checks

The later `evidence.html` implementation is complete only when all of the following are true:

1. The hero names Simon Sinek's WHY/HOW/WHAT model and displays two visibly separate corpus summaries.
2. The archived perturbation corpus appears before the current story corpus.
3. The bridge states that the story instrument reuses operators and recovery signals discovered by the perturbation runs.
4. No sentence pools 227 perturbation runs with 1,097 story sessions or calls the result one session total.
5. Every existing number, tooltip number, `data-stat`, `data-anal`, and `[M]/[C]/[H]/[X]` marker remains present with the same corpus and denominator.
6. The exact natural-behavior caveat appears prominently beside the verification finding.
7. Every ID in the chart and script register exists exactly once, except `no-data-row`, which may be replaced by its renderer as it is today.
8. `strategy-distribution` is no longer duplicated, and the strategy bar renders into its `div` rather than its heading.
9. Every current explicit and generated fragment resolves after load, including the inbound `evidence.html#story-models` link.
10. All five canvases render, all generated tables populate, model cards appear, Grit filters work, and the browser console has no null-target or duplicate-ID errors.
11. Desktop and mobile retain readable corpus boundaries; chronology must not depend on a side-by-side layout that collapses ambiguously on narrow screens.
12. `firebase/public/data.js` remains generated and untouched. Any future correction to measurements must flow through `scripts/build_data.py`, not this narrative restructure.

The smallest safe implementation is a DOM reorder plus focused bridge and caveat copy. New charts, new calculations, and schema migration are outside this narrative change because they would create evidence rather than re-narrate the rebuilt corpus.
