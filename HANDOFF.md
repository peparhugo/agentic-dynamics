---
status: accepted
---
# HANDOFF — session boundary 2026-08-25

> This session built the machine's control plane end-to-end (CAP I0–I10), populated its fact
> store, ran its first live experiments, seeded the private investing domain, and
> institutionalized the adversarial process discipline. The next session picks up at the
> evidence-integrity adversary verdict. Read this first, then `agent_config/conventions.md`.

## The machine (what this repo is)

Information-acquisition loop for AI economics: **instrument → measure → policy → grid → campaign**.
To make policies we need information — the compiler gate refuses any rule whose requirements
aren't measured (`requires_facts`). Facts are canonical state; knowledge records are what agents
read; the controller consumes compiled, contract-bounded snapshots by address, never retrieval.

## Two repos

| Repo | URL | Visibility | HEAD |
|---|---|---|---|
| Framework | github.com/peparhugo/agentic-dynamics | public | `a504ff505` |
| Private investing | github.com/peparhugo/rrsp-investing | **PRIVATE** | paper-journal merged |

The private repo holds personal strategy (buy-to-open calls/puts, sell-to-close only, long
straddles; no sell-to-open) — its records never enter the public repo. The framework repo tracks
its results corpus deliberately (manifest + publication tests depend on it).

## Done and merged (the session's arc)

1. **CAP I0–I7 + remediation** — fact schema, spec-status/ledger/workflow reducers, context
   compiler, fact contracts (R1–R11 gate), shadow controller, apply seam (OFF). Remediation fixed
   the identity-collision class (run-qualified attempt ids), null-not-zero, current-run
   aggregation, duplicate-evidence guards.
2. **Addendum I8–I10** — `DomainProfile`/`ChallengeProfile` (contract-wins composition), the
   `pattern` fact kind (D7: no EPISTEMIC_MAP row), `SessionCheckpoint` + `session_routing`
   contract (proposal-only; `AUTOMATABLE_ACTIONS = {continue, route}`).
3. **Backfill** — fact store retro-populated: registry 830 → **12,065 rows** (10,867 facts),
   `kb/` 14k artifacts. F1 (failed-before-call cost = uncaptured, never 0.0) and F2 (registry
   materialization) fixed + verified. Coverage census published
   (`docs/designs/current/cap_fact_backfill_coverage.md`).
4. **Evidence campaign (4 branches, sonnet-adversary reviewed, merged)** —
   E2 confidence-cascade retrospective (evaluable: 78% workflow confidence coverage), E3
   coverage impact, 6 minted patterns (`pattern/v1`), story bridge (`story_facts/v1` + token
   splits), test-runner wiring (`phase_test_verified` producible for agent phases).
5. **E4 grit pilot** — first live routing measurement: null inconclusive (n=1 cells), retry
   fired exactly once per policy, cost 3.1× over the heuristic envelope (lesson: re-baseline
   per-story cost empirically).
6. **Flash vs Luna** — same review task: flash $0.062 vs Luna $0.165 (2.66×), both 2/2 ok.
7. **Control Room refresh** — "Obsidian Signal" UI merged; live on **port 8001**. **Chroma owns
   port 8000** on this machine — never start the portal on 8000.
8. **Private repo** — 4 audits, remediated designs (R1–R30), `src/investing/` (identity,
   producers, reducers incl. `close_only_holds`, private ACL; 243+13 tests), paper-journal
   vertical (33 records emitted, 9/9 verification).
9. **Process institutionalized** — adversarial convention (findings re-verified + known-safe
   list, no bare PASS), visibility matrix + D1–D4 decisions (drafted, awaiting ratification),
   long-running-session lessons (below), deferred reasoning-measurement idea.

## In flight (resume point)

**`cap_evidence_adversary` — reviewing `feature/cap-evidence-integrity`** (deepseek-v4-pro,
opencode backend; Claude OAuth expired — see Operational notes). The evidence-integrity branch
has all 7 phases committed (**not merged**): p0 deterministic gate, e1 Sonar revision identity
(stale-refused), e2 typed CodeSnapshot/CodeDelta (two-ID, tree-sitter), e3 issue-level records
(Sonar + Pyright), e4 versioned graph (traversal ACL), e5 `code_change_facts/v1` +
`verify_code_change/v1`, e6 runtime-loop smoke.

## Queued / next steps (in order)

1. **Adversary verdict → review + merge `cap_evidence_integrity`** — then regenerate manifest
   + publication data at the campaign boundary.
2. **The two evidence campaigns** (designed in `cap_evidence_integrity_design.md` §6, not
   authored): 2a shadow calibration (proposal hit-rate ≥ 0.6 gate), 2b randomized live pilot;
   context-value campaign with the RAG arm's graph expansion explicitly disabled.
3. **Session-routing prospective study** — I10 machinery merged; the 4-arm checkpoint study
   (continue/fork-with-checkpoint/fork-blind/escalate) closes the n=0 continuation gap.
4. **Private repo: market-data vertical** — MD-4/MD-5 unblocks `iv_rank` + `no_short_delta`.
5. **Runner improvements (logged, not built)** — per-phase ledger checkpointing (mid-run kills
   re-walk prior phases today); per-phase model support (flash-work/sonnet-adversary pattern is
   manual); heartbeat/CPU check in execute specs.
6. **Reasoning measurement** — deliberately deferred (`docs/designs/current/reasoning_measurement_idea.md`).

## Operational notes (all in `agent_config/conventions.md` — read it)

- **Claude OAuth expires repeatedly** (several times this session). Before any sonnet workflow:
  `claude auth status` → must show `loggedIn: true`. Fix: `claude auth login --claudeai` or a
  fresh `CLAUDE_CODE_OAUTH_TOKEN`. The operator is frustrated — prefer DeepSeek fallbacks when
  auth is down, and consider long-lived tokens.
- **Never kill a "stalled" agent on wall-clock silence**: check CPU (~0% = hung; 50%+ = working
  in a long subprocess) and the child tree. The backfill p5 was killed at 51% CPU — the error
  that produced this rule.
- **Mid-run kills + ledger-based resume = re-walk of prior phases** (backfill re-audited p0–p2
  after a kill). Preserve in-flight work as a non-phase commit before killing; budget the
  re-walk.
- **Commit run artifacts at campaign cadence** with manifest regen — not per run (auto-emit
  writes facts to the main tree on every workflow completion; the corpus is deliberately tracked).
- **Live grids: measure one cell's cost before committing a budget** (E4 was 10× over).
- **Model routing**: flash handles doc/review-shaped work; sonnet for implementation/adversary;
  the operator has overridden pinned models on operational grounds (e.g., this adversary).

## Key files

- Design authority: `docs/designs/current/context_abstraction_design.md` (+ Addendum A),
  `context_abstraction_addendum_*.md`, `cap_evidence_integrity_design.md`,
  `visibility_matrix.md` + `_decisions.md`
- Specs: `workflows/repository/cap_*.yaml` (the campaign library)
- Gate: `scripts/evidence_prereq_gate.py` (`agentic-dynamics validate prereq`)
- Fact store: `experiments/results/registry_index.jsonl` (12,065 rows),
  `experiments/results/kb/` (14k artifacts), `experiments/data_manifest.json` (13.4MB)
- Census: `docs/designs/current/cap_fact_backfill_coverage.md`
- Controls: `src/agentic_dynamics/control/` (facts, reducers, context_compiler, rules,
  checkpoint, profiles), `core/contracts.py`, `experiments/contexts/session_routing.yaml`

## Numbers to carry

- 153 commits since Aug 23; registry 12,065 rows / 10,867 facts / 11,181 manifest entities
- E2: cascade evaluable (78% confidence coverage workflow family)
- Patterns: 6 minted (validity_window-in-fingerprint instability logged as a framework gap)
- E4: grit null inconclusive; retry at high perturbation looks like flailing (n=1)
- Escalation premium: 3.1× (retro, n=7); Luna 2.66× flash on review tasks
- No policy has fired yet (apply OFF, shadow 0% admissible pre-wiring) — the flip decision is
  the machine's first real test.

## How to resume

1. `ps aux | grep run_workflow` + `git -C /tmp/wt_evidence_adversary log --oneline -3` — the
   adversary either ran or is running.
2. If done: review its findings, review the evidence-integrity branch, merge, regen manifest.
3. Then the campaign queue (2a/2b → session-routing prospective → private market vertical).
