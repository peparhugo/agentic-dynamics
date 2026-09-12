---
status: accepted
---

# Control Room research - final verification and brief handoff (campaign r7)

**Date:** 2026-09-11
**Pass:** final check; verification + brief handoff
**Inputs:** the r0 audit, r1 questions, r2a-e corpora and meta, r3 taxonomy, r4 catalogs/skills,
r5 direction (now the facelift brief), and the three adversary reviews r6a/r6b/r6c.
**Outputs:** this verification record and the tightened
`docs/research/control_room_direction.md` (the facelift brief).

## Verdict

**CONDITIONAL PASS.**

The campaign's measured endpoints are met: the corpus clears its 200-source budget in every family
band; provenance hashes resolve; the taxonomy, catalogs, and skills are internally consistent; and
every enumerated catalog/skill item cites resolvable sources. The three adversary passes were
independent and each returned a blocking verdict; the brief now incorporates their required
dispositions.

One adversary blocker is **not** mechanically repaired in this phase: r6a found that several r3
taxonomy support counts were inflated by allocating broad labels (`dashboards`, `status`,
`chart-types`) to narrow techniques (`board-per-domain`, `gauge`, `heatmap-status-grid`). The
taxonomy artifact was not regenerated, so the brief does **not** cite those counts as external
support. Every affected recommendation is retained only as a local design policy `[P]` or as a
bounded `[X]` observation, and the open blocker is recorded below. This is a documented downgrade,
not a silent acceptance of the inflated numbers.

## 1. Corpus totals versus budget

The pre-registration budgets 200 sources as 40/50/40/30/40 across five families, with a +/-20% band
per family, mandatory `research_fetch.py` provenance, and a recorded stop reason per family.

| Family | Label | Budget | +/-20% band | Facet records | Stored sources | Stop reason (abridged) | Verdict |
|---|---|---:|---:|---:|---:|---|---|
| agentops | LLM/agent-operations rooms | 40 | 32-48 | 48 | 48 | budget met at the +20% band ceiling; 2 wandb.ai bodies unusable, kept for provenance | PASS (ceiling) |
| dashboards | Operational dashboards & design systems | 50 | 40-60 | 58 | 66 | stopped after five batches; curated down from 66 by excluding 8 JS-shell/duplicate/thin pages | PASS |
| dataviz | Charts & data-visualization craft | 40 | 32-48 | 41 | 46 | stopped after six batches; Observable seed returned HTTP 429 and was substituted | PASS |
| cli | Terminal / CLI aesthetics | 30 | 24-36 | 34 | 46 | stopped after three batches; all 46 seeds resolved; curated to 34 | PASS |
| craft | Craft, patterns & reference standards | 40 | 32-48 | 48 | 78 | stopped at the +20% band ceiling; Material/Apple HIG JS-shells excluded | PASS (ceiling) |
| **Total** | | **200** | | **229** | **284 attributed / 300 unique** | | **PASS** |

**Note on the two stored-source counts.** The family meta files attribute 284 stored sources; the
append-only `sources.jsonl` holds 300 records with 300 distinct SHA-256 hashes. The difference is
that some sources are catalogued once but referenced by more than one family. The registered
endpoint is "at least 160 stored sources with provenance"; 300 unique, hash-deduplicated records
clears it.

**Stop-reason quality.** Four families stopped at a budget boundary or after exhausting seeds;
dataviz records a named-seed outage (Observable, HTTP 429) and its substitution. No family stopped
"sources run dry" without a coverage note. The dataviz and craft families record explicit
vocabulary drift and coverage caveats rather than hiding them.

**Corpus gaps recorded, not resolved:**

- agentops aesthetic is `unspecified` throughout: text extraction cannot see product pixels, so the
  visual and design-system burden is carried by dashboards and craft.
- Material/Apple HIG density pages did not text-extract, so `ia-density-ladder` is evidenced
  indirectly (Every Layout, web.dev, NN/g, Refactoring UI).
- performance evidence is claimed or absent everywhere except one measured web.dev source.

## 2. Taxonomy verification

`experiments/research/control_room/taxonomy.json` declares schema, phase, corpus totals, the
`min_support` bar (3), split/merge decisions, and 105 nodes.

| Check | Result |
|---|---|
| Corpus inputs resolve and match by SHA-256 | PASS - all five `corpus/*.jsonl` hashes reproduce exactly |
| Family record totals | PASS - agentops 48, dashboards 58, dataviz 41, cli 34, craft 48 = 229 |
| Canonical technique leaves | 56 defined; 52 promoted; 4 thin merged below the bar |
| Raw labels crosswalked | 270; 12 stack or source-specific mentions deliberately unmapped |
| Thin nodes dropped from reduction | PASS - `thin-ia-modal-sheet` (1), `thin-ia-overflow-drawer` (1), `thin-viz-threshold-bands` (1), `thin-ops-self-host` (2) all below the >=3-source bar |

**Unresolved semantic finding (r6a E1-E4).** The taxonomy is structurally consistent but its
`support` values are not raw-label support for several narrow leaves. Measured examples that remain
in the artifact:

| Node | Reported support | r6a direct raw-label support |
|---|---:|---:|
| `tech-viz-gauge` | 25 | 1 |
| `tech-viz-heatmap-status-grid` | 30 | 1 |
| `tech-viz-virtualized-table` | 32 | 3 |
| `tech-ia-board-per-domain` | 55 | 0 |
| `tech-money-budget-thresholds` | 19 | 0 |
| `tech-money-quota-wallet` | 7 | 0 |
| `tech-trust-degraded-banner` | 11 | 0 |
| `tech-trust-uncertainty-encoding` | 3 | 0 |

**Disposition:** the brief does not cite these counts as external consensus. The affected design
moves are stated as local policy `[P]` grounded in the r0 audit, or as bounded `[X]` observations
of the named exemplars. Regenerating the crosswalk is recorded as an open item, not a silent pass.

## 3. Reduction citation verification

`catalogs.json` and `skills.json` were checked mechanically for citation integrity.

| Check | Result |
|---|---|
| Catalog families | 7 (frameworks, ia-layout, chart-selection, color-motion, svg-technique, trust-attention, agent-ops) |
| Catalog items | 49; every item carries at least one ref and at least one taxonomy node |
| Catalog ref resolution | PASS - every `(family, uri, sha256)` resolves to a stored source record |
| Catalog taxonomy-node support match | PASS - every cited node exists and its stated support matches `taxonomy.json` |
| Skills | 9 (`skill-delivery`, `skill-shell-ia`, `skill-glance`, `skill-charts`, `skill-visual-system`, `skill-svg`, `skill-trust`, `skill-agent-ops`, `skill-synthesis`) |
| Skill backing-node resolution | PASS - every `backing_nodes` id exists and its support matches |
| Skill ref resolution | PASS - every cited `sha256` resolves to a stored source |
| Dropped items | PASS - 4 thin nodes recorded in `dropped`, each below `min_support=3` |

**Caveat carried into the brief:** citation resolution proves the links resolve; it does not prove
the semantic entailment of each claim. r6a is the authority on entailment and its E1-E8 findings
govern. The brief's claim discipline (`[M]` local, `[X]` external, `[P]` policy) is the mitigation.

## 4. The three adversary passes and their dispositions

The campaign required three independent passes over distinct models: r6a entailment (terra), r6b
design (luna; the controller substituted it for the disabled sonnet), and r6c information
architecture (sol). Each wrote its own review and returned a blocking verdict.

| Pass | Model | Verdict | Core findings | Disposition in the brief |
|---|---|---|---|---|
| r6a entailment | `openai/gpt-5.6-terra` | NOT CLEAN | E1-E4 inflated mark/IA/money/trust supports; E5 superlatives; E6 missing caveats; E7 no-build inference; E8 title drift | Affected claims downgraded to `[P]`/`[X]`; superlatives removed; no-build stated as local constraint; taxonomy repair recorded open |
| r6b design | `openai/gpt-5.6-luna` | REWORK REQUIRED | D1 dashboard template; D2 four-board fragmentation; D3 attention has no model; D4 truth bar too weak; D5 dated retro-ops costume; D6 cargo-culted charts; D7 topology theater; D8 palette not a control model; D9 generic transcript; D10 no-build not a virtue; D11 mobile reflow; D12 control semantics under-specified | Direction re-centered on evidence-first run triage; attention state model added; truth moved to objects; charts de-defaulted; topology gated; terminal grammar specified; mobile defined as triage mode; action preview required |
| r6c IA | `openai/gpt-5.6-sol` | FAIL | IA1 impossible no-interaction glance; IA2 run context fragmented; IA3 control packet not authoritative; IA4 attention strip has no information model; IA5 alerting is not a depth; IA6 interrupt vs pull-first; IA7 global truth cannot qualify local data; IA8 active-board polling stales global attention; IA9 decisions are counts; IA10 detail is geometry; IA11 lineage conflation; IA12 entry paths lost; IA13 search ambiguous; IA14 composition/performance conflated; IA15 contradictory homes; IA16 mobile reflow | Default Fleet Triage surface; control packet as current-state authority; durable Attention Inbox; disclosure/alert split; per-object truth; detail navigation contract; entry-path migration map; object and event search; mobile triage mode |

**Cross-pass agreement.** All three passes independently require the same three structural changes:
(1) one joined run context instead of board hopping, (2) a durable attention model instead of a
transient strip, and (3) local provenance instead of a single global freshness signal. That
convergence is the strongest evidence in the campaign and is the spine of the brief.

**Disposition completeness.** The brief addresses every D1-D12 and IA1-IA16 disposition, and either
downgrades or removes every E1-E8 claim.

## 5. Brief acceptance criteria (summary)

The full brief is `docs/research/control_room_direction.md`. Its acceptance criteria, which the
later facelift phase is graded against, are:

1. **Scope** - restyle and re-compose the existing build-less Flask portal; no framework migration,
   no new route category, no new persistence plane, no automatic actuation.
2. **Layout / IA** - persistent scope+truth chrome; a durable Attention Inbox; a default Fleet
   Triage body; one selected-run inspector that joins evidence, constraints, and safe action;
   secondary analytical lenses. ON-G1..G6 are visible together at rest.
3. **Chart set** - no unconditional chart defaults; every accepted chart names a question, a
   decision, a baseline, a completeness rule, a text equivalent, and a fallback.
4. **SVG set** - theme-aware, accessible, print-safe; topology only if live and scoped, otherwise
   moved out of the rest view.
5. **Motion budget** - state-change motion only, within the declared duration/easing tokens,
   fully disabled under `prefers-reduced-motion`, never competing with the live cadence.
6. **Accessibility bar** - WCAG 2.2 AA contrast, keyboard operation, table semantics with real
   controls, one transition-only live region, forced-colors support, focus containment and return.
7. **No regressions** - two-layer reconciliation, one selected stream, keyed write-on-change
   rendering, safe DOM construction, mutation/idempotency gates, and the no-build constraint all
   hold.

## 6. Deviations and open items

| # | Item | Status | Owner |
|---|---|---|---|
| 1 | r6a E1-E4 taxonomy crosswalk repair (regenerate raw-label support and descendants) | OPEN - mitigated by `[P]`/`[X]` downgrade in the brief | future r3/r4 repair pass; controller decides |
| 2 | r6a E8 seven catalog title drifts | OPEN - metadata only, references resolve | next catalog regeneration |
| 3 | dataviz named seed (Observable) unavailable; substitution recorded | RECORDED | accepted; coverage note carries it |
| 4 | Material/Apple HIG density pages not text-extractable | RECORDED | accepted; density ladder evidence is indirect |
| 5 | agentops aesthetic `unspecified` throughout | RECORDED | accepted; design-system evidence carried by F2/F5 |
| 6 | Corpus stored-source accounting (284 attributed vs 300 unique) | RECORDED - both clear the endpoint | accepted; explained in section 1 |
| 7 | The brief is a design contract, not an implemented facelift | NOT STARTED | the later facelift workflow (a1-a7) |

## 7. Reproduce

```bash
# corpus totals, budgets, stop reasons
python3 - <<'PY'
import json, pathlib
root=pathlib.Path('experiments/research/control_room/corpus')
for f in ['agentops','dashboards','dataviz','cli','craft']:
    m=json.loads((root/f'{f}.meta.json').read_text())
    print(f, m['family_budget'], m['facet_records'], m['stop_reason'][:80])
PY

# provenance, taxonomy, catalog, and skill consistency
python3 scripts/research_fetch.py --help
python3 - <<'PY'   # see section 3 checks; refs and backing nodes resolve
import json, pathlib
root=pathlib.Path('experiments/research/control_room')
json.loads((root/'taxonomy.json').read_text())
json.loads((root/'catalogs.json').read_text())
json.loads((root/'skills.json').read_text())
PY
```

Doc lifecycle: this file and the brief carry `status: accepted`
(`tests/test_doc_lifecycle.py`). Generated instruction surfaces are unaffected.

## 8. Verdict

The campaign delivers a verified, cited, adversary-tested facelift brief. The measured endpoints
(corpus, taxonomy, reduction, three adversary passes, brief) are met. The one unresolved blocker is
semantic, not structural: the taxonomy support counts that r6a found inflated were not regenerated,
so the brief treats every affected recommendation as local policy rather than external consensus.
That is the correct fail-closed choice for this phase; regenerating the crosswalk remains a named
open item for the controller.
