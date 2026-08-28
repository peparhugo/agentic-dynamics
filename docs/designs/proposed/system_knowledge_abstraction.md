---
status: proposed
---

# The knowledge-abstraction stack — the system's game board (the system shapes the agent; the agent reshapes the system)

**Status: PROPOSED (2026-08-28, operator-directed pivot).** The principle, stated twice because it
is load-bearing: **the system shapes the agent, and the agent reshapes the system.** Every time
one side changes — a boundary commit, a new campaign, a new module, a renamed script — the
derived surfaces (the generated agent files, mental model, tools, skills, mds) must be re-rendered
to the new state. Today the repo enforces that with guard tests and triages the drift by hand
(the controller chat diagnosing sync failures). This design replaces hand-triage with
**self-maintenance**: the machine regenerates its own surfaces, and the shared mental model
becomes a live snapshot every actor reads. **The contract layer (frontmatter, marker blocks,
status fields) is the state; the formatter is the render — and the self-maintenance loop
maintains BOTH, with the derivation running one way: a contract transition (proposed →
accepted → superseded, a marker block edit) is a state change made with sign-off, and the
formatter re-renders from it; the sync regenerates renders, never the contract backwards.
The guards verify contract ⟷ render consistency in both directions.**

## 1. The failure mode being fixed

The guard families (`test_doc_lifecycle`, `test_script_classification`, `test_cli_resolution`,
`test_data_flow`, `test_spec_lifecycle`, the README↔data.js contract, …) catch drift — but the
repair is manual and slow: a boundary lands, four guards go red, and the controller chat has to
diagnose which derived surface is stale and re-run the right generator. The guards are a
verification layer; they should never be the repair path. The repair path should be ONE command
that re-renders every derived surface from its sources, run by the machine itself at the moments
the surfaces change (post-merge, post-campaign-phase, in the pipeline plans). The guards stay —
they become the backstop that proves the re-render, and their failure message names the one
command.

## 2. The abstraction stack (the game board)

```
L0  THE GAME BOARD (live state — what is happening NOW)
    agent_config/system_snapshot.md  — GENERATED, auto-refreshed
    → rendered to .opencode/instructions/system_snapshot.md
      and .claude/rules/system_snapshot.md (same bytes, both platforms)
    → served read-only by the Control Room
    → read by EVERY actor: workers (orientation), controller (triage → gone),
      supervisor (assessment baseline)
    Content: main HEAD + sha; spec index counts; registry count; corpus counts
    + spend; queue/worker state; running campaigns + worktrees; daemon status;
    RECENT CHRONOLOGICAL HISTORY (last N commits); worktrees awaiting the
    controller's permanence decision.

L1  THE ARCHITECTURE (what changes slowly)
    agent_config/{mental-model,conventions,rules}.md + agents/commands/skills
    — the existing generated surfaces, regenerated from agent_config/ by
    scripts/_gen_instructions.py. Rendered identically to .opencode/ and .claude/.

L2  THE INTELLIGENCE (higher-level knowledge)
    docs/designs/*, preregistrations, verdicts, lab books — the research layer.
    The docs-taxonomy restructure design (proposed) organizes these; the
    experiment index (spec → preregistration → … → superseding study) is the
    L2 navigation surface. Consumed selectively: workers load their skill's
    doc chain; the controller reads verdicts; the supervisor reads verdicts +
    postmortems to calibrate assessments.

L3  DOMAIN SKILLS (long-lived knowledge, measured)
    A skill IS domain knowledge. The creative UI/UX agents need a UI/UX mental
    model (research + examples) that the controller does NOT need. Domain
    skills persist over time and their persistence is itself an experimental
    question: does a skill-bearing agent beat a bare agent on its domain?
    Design the experiment when the first real domain skill is authored.
```

## 3. The access matrix

| actor | L0 game board | L1 architecture | L2 intelligence | L3 domain skills | chronology |
|---|---|---|---|---|---|
| **workers** (cell/story/workflow agents) | yes (their skill injects the snapshot) | yes (generated mental model) | their skill's doc chain | their own skill | no |
| **controller** (the operator chat) | yes | yes | yes (verdicts, preregs) | read-only, never auto-loaded | **yes + the PERMANENCE GATE** |
| **supervisor** (supervise.py passes) | yes (the assessment baseline) | yes | verdicts + postmortems | no | **yes — full chronological read: loop/undo detection** |

**The controller's permanence gate (chronological history).** Worktree branches
(`feature/*`, `wt_*`) are EPHEMERAL — proposals. The chronological history of the system is
`main` plus the merges the controller signs. The controller decides what becomes permanent:
the machine proposes (campaign phases, workflow commits, the snapshot lists every worktree
awaiting the decision); the controller merges. The snapshot's "awaiting permanence" section is
the board that makes this decision cheap.

**The supervisor's chronological eye.** To answer "are we undoing anything / moving in circles",
the supervisor reads the commit history chronologically (across branches and campaigns) with
explicit loop-detection guidance: repeated commit subjects across attempts, discarded trees
re-presented (the relabel ledger), a campaign re-covering ground a prior campaign covered, the
same gate failing twice. The supervisor's assessment prompts (security / on-task / over-budget)
are grounded in L0 (what is running, what it costs, what it claims to do) + the chronology.

## 4. The self-maintenance loop (the machine reshapes itself)

**`agentic-dynamics surfaces sync`** (backing script `scripts/sync_surfaces.py`) — ONE command
that regenerates every derived surface from its sources, in dependency order:

```
1. scripts/system_snapshot.py      → agent_config/system_snapshot.md   (L0 — the game board)
2. scripts/_gen_instructions.py    → .opencode/** + .claude/**         (L0 + L1 rendering)
3. python3 scripts/spec_status.py  → experiments/specs/{index,STATUS}.md (spec lifecycle)
4. scripts/sync_data.py            → parquet
5. scripts/build_data.py           → apps/website/data.js
6. scripts/generate_manifest.py    → data_manifest.json
7. (verify) python3 -m pytest tests/ -m "not external"  → the guards prove the re-render
```

Wired into the moments the surfaces change:
- the pipeline plans (a `surfaces` step in ci/deploy/full_matrix/cross_models before the final
  checks), so a campaign's own data-chain phases end with the game board re-rendered;
- the post-merge ritual (the operator's boundary commits run it once);
- the Control Room serves the snapshot read-only (/api/snapshot) — the shared game board is
  visible to the supervisor and the operator from the same board.

**What does NOT change:** the guard tests stay (the backstop); the derived surfaces stay
committed (the snapshot is part of the repo — the game board is reviewable history, not a
runtime-only view); every generator stays idempotent and best-effort per subsystem (Redis down,
queue empty — the snapshot degrades gracefully, never blocks).

## 5. Slice order

1. **This design** (proposed).
2. **L0 + self-maintenance**: `system_snapshot.py` (the game board) + `sync_surfaces.py` (the
   one command) + `_gen_instructions.py` renders the snapshot + plan wiring + CONTEXT.md/CLI
   registration + the guards green. — the pivot's first landing.
3. **Supervisor upgrade**: the supervise skill (agent_config) reads the snapshot + the
   chronology with loop-detection guidance; regenerate the surfaces. Assessment prompts gain
   the security/on-task/budget grounding.
4. **Controller permanence**: the snapshot's "awaiting permanence" section + the merge ritual
   documented in the mental model.
5. **L3 experiment design** (when the first real domain skill is authored): does a
   skill-bearing agent beat a bare agent on its domain? — preregistered.

## Guard

L0's content is generated from live state only (git, Redis, filesystem — never hand-edited; a
hand-edit is overwritten by design). Every number in the snapshot cites its source (the same
artifacts the guards verify). The sync command is the machine's own maintenance act — the
guard tests verify it, and their failure message names it.

**LOG:** the pivot restated as the knowledge-abstraction stack (L0 game board → L1 architecture
→ L2 intelligence → L3 domain skills) with the access matrix (worker/controller/supervisor +
the controller's permanence gate + the supervisor's chronological eye); the self-maintenance
loop (one sync command, wired into the plans and the post-merge ritual, guards as backstop);
the slice order (L0 + sync first, then supervisor, then permanence, then the L3 experiment).
**PROPOSED — slice 2 is the first implementation.**
