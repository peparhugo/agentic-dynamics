---
status: proposed
---

# The world-model loop: prior → plan → execute → posterior

**Origin.** The controller's design direction, 2026-09-21: workflows should form an explicit
*a priori* model of the problem — searching the code graph, prior sessions, edits, PRs and
analysis — write down the gaps and the plan BEFORE executing, then close by diffing what
actually happened against the model and updating (beliefs, knowledge, skills). "Once we know
what we didn't know."

## The loop

1. **Prior (world model).** Read what is known: the code graph (`graph build`), the KB
   (`knowledge read` — the reader verb), prior sessions/decisions/reviews/ledgers, lab analyses,
   and — when gaps warrant it — the open web (`research_fetch`, provenance-carrying). Output: a
   persisted **world-model artifact**: what the problem is believed to be, what exists, what is
   unknown (gaps), and what would reduce the uncertainty.
2. **Plan.** From the model: the files to touch, the tests to create, the acceptance, the risks —
   written down and used to gate execution. The observed failure mode: the model plans inside its
   chain-of-thought (the "wait wait wait" pattern) instead of in an artifact the run can check
   against.
3. **Execute.** The workflow's phases, against the plan.
4. **Posterior.** Diff the model against what happened: **violations** (reality differed),
   **unknowns discovered** (what we didn't know we didn't know), and **updates**: beliefs
   (`belief_update`), reflections, KB findings, and skill/pattern candidates. The contemplation
   fan-out + synthesis is this step's experimental form.

## What already exists (2026-09-21)

| need | primitive | state |
|---|---|---|
| read the corpus for a scope | `knowledge read` (reader verb) + `knowledge-reader` skill | built 2026-09-21 |
| code graph | `graph build` / Neo4j | exists |
| prior sessions/decisions/ledgers | KB records + registry + `registry query` | exists |
| retrieval-in-the-loop | `rag_augment` + `rag_params` | exists, enabled by 8 specs |
| open-web research | `research_fetch` (uri/sha256/text provenance) | exists, rarely used |
| belief updates | `belief_ingestion` / `belief_update` / `belief_seeds` | exists |
| reflection records | `reflection_ingestion` (session self-notes) | exists |
| context assembly for a step | `control.context_compiler` | exists |
| procedural skills as knowledge | `kb_produce_skill` (pattern/v1 projection) | exists (KB-side) |
| local CI parity | `agentic-dynamics validate preflight` (built 2026-09-21 on `feature/ci-preflight`, pending merge) | built |

## What is missing (the three artifacts)

1. **The world-model artifact + its contract.** Nothing today persists "what the run believed
   before it acted" as a first-class, reviewable artifact — so there is nothing to diff against.
2. **The posterior diff.** No phase/step compares model vs outcome, names violations, or
   produces the update set. (Beliefs/reflections exist as destinations, not as a driven loop.)
3. **The runtime skill path.** A finding can be a pattern record (KB-side), but there is no
   gated path from a runtime discovery ("I needed an SVG/graph-UI skill") to an actual skill the
   agents load — generated surfaces belong to the generator; a candidate must ride the same gate
   as any other change.

## Smallest next steps

- **Pilot**: a three-phase `agent_task` — `prior` (read + model + plan artifacts) → `execute`
  (against the plan) → `posterior` (diff + updates) — on one real small task, with the
  prior/posterior artifacts persisted and emitted (the emission path is now wired).
- **Local CI preflight**: one command running the workflow's gates locally (ruff → generator
  check → docs drift → fast path → full suite) so a push fails locally, not after minutes of
  waiting. (`act` is not installed; the parity set is the cheap version.)
- **Runtime-skill candidate path**: define where a runtime-minted skill lands before promotion
  (a `skill-candidate` record in the KB + an explicit promotion step) — never a hand-edit of
  generated surfaces.

## v1 built (2026-09-21, `feature/world-model-v1`)

- **The artifact gate** — a phase declares `requires_files: [...]`; the runner REFUSES before
  any prompt build, admission, or spend when a declared artifact is absent from the worktree.
  This is the plan gate: `execute` cannot run without the prior phase's `notes/plan.md`, and
  `posterior` cannot run without the model and the plan. Tests:
  `tests/test_world_model_gates.py`.
- **The report variant for committed phases** — `rag.emit_report: true` ALSO emits the full
  captured turn as a retrievable record, so a loop's notes (world model, plan, posterior) are
  knowledge, not only git files. The world-model loop spec opts in.
- **Runtime-skill candidates (convention)** — a runtime discovery that wants to become a skill
  lands as a KB record scoped to the proposing cell (the existing `kb_produce_skill` /
  pattern-projection seam, or the posterior's UPDATES list), and is promoted into
  `agent_config/skills/` only through an explicit promotion step (a reviewed commit) — never a
  hand-edit of generated surfaces.

## Open extension: execute as a workflow (controller, 2026-09-21)

A massive plan must not run as ONE execute phase — the execute step should itself be a
workflow, and the plan should decompose. The seed exists (`ExperimentSpec`'s cells + the DAG
compiler: spec → cells → phases), so the natural shape: the PRIOR phase emits a plan that
COMPILES into the execute DAG (units with dependencies, budgets, and acceptance each), and the
POSTERIOR diffs the whole shape — including which units the plan mis-sized. Open questions:
the plan→spec bridge (what the prior writes that the compiler consumes), per-unit budgets, and
aggregating the posterior across units. v0 keeps one execute phase; decomposition is v1.
