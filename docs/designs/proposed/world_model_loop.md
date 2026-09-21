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
- **Durable emission (v1.1, 2026-09-21)** — the emissions (KB artifacts, run reports) and the
  reader now honor the fleet contract's `FINOPS_RESULTS_DIR` (default: this checkout). A run
  executing from an EPHEMERAL worktree must set it to the durable checkout
  (`FINOPS_RESULTS_DIR=<durable>/experiments/results`), so records and their links stay
  resolvable after the worktree goes away. Measured cause: the second loop run emitted its
  reports/records into `/tmp/wml_v1/` — durable only while that worktree lived, and invisible
  to a reader in another worktree (the posterior's own V5 false-negative).

## v1.3 built (2026-09-21, `feature/wml-v1.3`) — the three named gaps + the fleet scopes

- **Fleet-runnable (scopes).** v1.2 could only run in-process: its agent phases declared no
  `scope:`, so the durable path's spawn validation refused the spec, and the AIO
  local-execution exception forbids in-process agent runs. v1.3 declares them —
  `prior`/`posterior: proposal_write`, `execute`/`p2_mint`/`g_test_gate: implementation`,
  `g_adversarial: adversarial_readonly` — and the loop rides the fleet
  (first submission: `run-037d7d760bd6`).
- **`g_test_gate` (the missing independent verification).** A `kind: test` phase after execute
  whose targets come from the plan: `tests_from_plan: notes/plan.md` parses `## Tests`, keeps
  only `tests/` paths that EXIST in the worktree, and hands them to the independent runner. A
  plan that names no targets SKIPS explicitly (`test_gate_note` on the ledger;
  `test_executed_success` stays None — never a fabricated verdict), so the gate is harmless
  for analysis-only runs and exact for code-producing ones. Declared `tests:` lists are
  unchanged.
- **`p2_mint` (the runtime-skill path as a step, not a convention).** After the posterior, the
  mint phase turns each SKILL/PATTERN candidate in §UPDATES into a `notes/skills/<slug>.json`
  and mints it through the existing producer (`scripts/kb_produce_skill.py`, pattern/v1).
  Candidates that cannot be minted are recorded, never dropped; promotion remains a reviewed
  commit — generated surfaces are never hand-edited.
- **Forced research (mechanized as far as the vocabulary allows).** The prior must write
  `notes/sources.jsonl` — one provenance line per source actually used (KB id / file / URL +
  sha256; an explicit `{"none": true, "reason": ...}` when no external fact was needed) — the
  execute gate requires the file, and `g_adversarial` checks it against the world model: an
  external gap with no fetched source is a finding. The semantic check stays adversarial by
  design; the DECISION is no longer optional.
- **The notes-collision finding (from the merge).** Two loop runs committed different artifacts
  at the same fixed `notes/*.md` paths, so merging their branches conflicted on all four files.
  The merge preserved both (main's canonical at `notes/*`, the second run's under
  `notes/ci-preflight/`), and the next convention candidate is: namespace run notes by
  run/task, or route them to the durable results dir.

## v1.3.1 (2026-09-21, `feature/wml-v131`) — the live run's findings, fixed

The first successful fleet run (`run-0fad6c313dcd`, 6/6 phases, candidate `921252b82`) had its
adversarial phase attack the run itself; three findings were engine/spec defects:

- **F1 — a declared `run_model` now OUTRANKS the router.** The production root always injects
  `route_step`, and the router never reads `phase_def`, so `run_model:` was silently dead in
  every fleet run — the loop's "DIFFERENT model" adversarial phase ran on the run model.
  Explicit override wins over routing; regression on the containerized shape (the in-process
  executor's late override masks the bug and cannot show it).
- **F2 — report stamps carry microseconds.** A whole-second stamp let two same-phase reports in
  one second overwrite each other (nondeterministic counts, a lost report). Regression added.
- **F8 — `g_adversarial` is `proposal_write`.** A read-only scope cannot write the review file
  its prompt orders committed, and a phase without a commit blocks promotion (promote verifies
  per-phase commits; it refused exactly this candidate). `proposal_write` carries assemble_docs
  + git_commit — the review document's own write path.

Next: re-run the loop on this revision; a candidate whose adversarial phase commits is
promotable.

## Run-note hygiene (2026-09-21, `feature/loop-hygiene`) — L11 + L12

`notes/` is **ignored, not tracked**: the loop's run notes (world-model, plan, deviations,
posterior, sources, skills) are PROCESS records. Each run's notes live in its own worktree and
travel durably through the phase reports (`experiments/results/workflows/<spec>/reports/`) and
the KB findings; a run's branch carries its CODE/TESTS. Why: two runs committing identical fixed
paths collided on every note file at merge time (#109), and literal per-run namespacing would
need run-identity plumbing the engine does not have. The gates are unaffected —
`requires_files` / `requires_content` / `tests_from_plan` read the worktree paths, which the
phases still write.

The emit seam is now observable (L12): a swallowed emission failure lands on the phase result's
`emit_note` (+ stderr), so "no finding" cannot masquerade as "no emission"; and
`_phase_emit_scope` makes `rag.emit_scope` ONE precedence for BOTH the metadata finding and the
report variant (previously only the report variant honored it).

## Open extension: execute as a workflow (controller, 2026-09-21)

A massive plan must not run as ONE execute phase — the execute step should itself be a
workflow, and the plan should decompose. The seed exists (`ExperimentSpec`'s cells + the DAG
compiler: spec → cells → phases), so the natural shape: the PRIOR phase emits a plan that
COMPILES into the execute DAG (units with dependencies, budgets, and acceptance each), and the
POSTERIOR diffs the whole shape — including which units the plan mis-sized. Open questions:
the plan→spec bridge (what the prior writes that the compiler consumes), per-unit budgets, and
aggregating the posterior across units. v0 keeps one execute phase; decomposition is v1.
