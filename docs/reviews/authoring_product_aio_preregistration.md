---
status: accepted
kind: preregistration
spec: authoring_product_aio
phase: a0_pin_spec
generated_at: 2026-09-03T12:33:25Z
---

# Preregistration — `authoring_product_aio` (a0_pin_spec)

**The house pin convention.** This document is written BEFORE any implementation phase of the
wave executes (`a1_schema_linter`, `a2_examples`, `a3_command_surface`, `a4_aio_agent`,
`a5_aio_emission`). Its purpose is twofold, and both halves are load-bearing:

1. **Anchor the run to exact bytes.** A workflow spec is a mutable file. Recording the spec's
   SHA256 makes the mandate immutable *by reference*: any divergence is detectable by re-running
   one command.
2. **Verify the premises, do not assert them.** The five edges this wave builds on are stated as
   current-state claims in the spec's `current_state` block (authored 2026-09-02). This phase
   re-derives each edge against the actual repository at the pin and records the command that
   produced the evidence, so a reader can reproduce every finding without trusting this document.
   **An edge that does not hold is a FAILED finding.** No claim was accepted on the spec's
   authority; none required more than one reproduction attempt.

The mandate's failure rule is honored strictly: **edges 1 and 5 do not hold as literally stated.**
Both are recorded as FAILED findings with the true state proven below — the schema half of edge 1
holds in its strong form, and the falsifying content in each case is a placeholder rather than
product content (a 1-file skeleton README in `workflows/examples/`; two real actuation call sites
that predate the spec). Neither failure blocks the wave — each is a correction the implementation
phases and the adversarial review must consume so they target the real state, not the asserted one.

---

## 1. The pin

| Field | Value |
|---|---|
| Spec path | `workflows/repository/authoring_product_aio.yaml` |
| Spec **SHA256** | `980fd29400705e5e6ab4570c9c716604124a9e7c85c8d9a09b45fa63161fe8d5` |
| Spec size | 21,477 bytes |
| Worktree HEAD (git sha) | `24510116e76d50402c3bb14cc3e3bc5e925fbbe9` |
| HEAD subject | `spec: authoring_product_aio — Wave 3 (P2-1 authoring product + the AIO Control Agent)` |
| HEAD committed | 2026-09-03 14:28:05 +0200 |
| Worktree | `/tmp/wt_wave3` — detached `HEAD` at the spec-commit tip (git worktree of the main checkout; common dir `/home/drseuss/ai-finops-framework/.git`) |
| Main checkout | `/home/drseuss/ai-finops-framework` — branch `main`, HEAD `226aa634411300315cea0f65b5bd311888a16f9d` |
| main ↔ worktree | `main` = this HEAD + one commit (`226aa6344` "rebuild data.js (workflow_specs 173)…"). `git diff main HEAD` = `apps/website/data.js` only — every edge-relevant tree is identical, so the "machine-local state at the MAIN checkout" and the worktree agree on all five edges. |
| Working tree | clean except modified `run.log` (a runner artifact, not a source file) |
| Control db | `/home/drseuss/ai-finops-framework/experiments/results/control/control.db` present (machine-local, gitignored) — not needed by any edge below |
| Pinned at | 2026-09-03T12:33:25Z |

Reproduce the pin — these are the EXACT bytes the wave executes:

```bash
sha256sum workflows/repository/authoring_product_aio.yaml
# 980fd29400705e5e6ab4570c9c716604124a9e7c85c8d9a09b45fa63161fe8d5
git rev-parse HEAD          # (in the worktree)
# 24510116e76d50402c3bb14cc3e3bc5e925fbbe9
```

If either value differs when `a6_adversarial` (or `a7_test_gate`) runs, the spec was edited
mid-run and the mandate this document pins is no longer the mandate being executed — a
reportable finding in itself.

**Spec shape at the pin** — eight phases (seven `kind: agent` + one `kind: test`); no authored
`status:` (completion is derived from run evidence). Single factor: `model =
deepseek/deepseek-v4-flash`.

| # | Phase | kind | scope | notes |
|---|---|---|---|---|
| 0 | `a0_pin_spec` | agent | `implementation` | **this phase** — the preregistration |
| 1 | `a1_schema_linter` | agent | `implementation` | schema + linter (the authoring contract) |
| 2 | `a2_examples` | agent | `implementation` | the four canonical example workflows |
| 3 | `a3_command_surface` | agent | `implementation` | `workflow new` / `lint` / `plan --json` |
| 4 | `a4_aio_agent` | agent | `implementation` | the AIO agent definition |
| 5 | `a5_aio_emission` | agent | `implementation` | AIO decision emission + "first actuation caller" |
| 6 | `a6_adversarial` | agent | `adversarial_readonly` | independent pro reviewer (requires_deliverable, `run_model: deepseek/deepseek-v4-pro`) |
| 7 | `a7_test_gate` | test | `implementation` | 12 suites (five do not exist yet — see §3) |

---

## 2. Verified edges (the five current-state claims)

Each edge is stated as the spec's `current_state` states it, then **independently derived**
against the repository at `24510116e…`. "Method" is the command actually run; "Evidence" is its
actual output. No finding below was accepted on the spec's authority.

### Edge 1 — "no `workflows/schema/`, no `workflows/examples/`" → **FAILED** (schema half PASS; examples half is a content-free skeleton — D-1)

*Method.*

```bash
ls workflows/
ls workflows/schema/ 2>&1
ls workflows/examples/ 2>&1
git ls-files workflows/examples/
```

*Evidence.*

```
$ ls workflows/
examples  operations  repository  research

$ ls workflows/schema/
ls: cannot access 'workflows/schema/': No such file or directory   # EXIT=2

$ ls workflows/examples/
README.md                                                        # EXIT=0 — the dir EXISTS

$ git ls-files workflows/examples/
workflows/examples/README.md
```

`workflows/schema/` is absent in the strong form (no directory, not merely no files). But
`workflows/examples/` **exists**, holding exactly one file — a placeholder README
(`# workflows/examples/  Template specs. Populated by consolidation Stage 2.`), committed in
`20813fa2b` (a classification-guard era commit) as a directory skeleton. There are **zero**
example workflow YAMLs anywhere under it.

*Reading.* The schema half holds exactly as claimed — `a1_schema_linter` is greenfield, no
directory to collide with. The examples half does not hold in its literal form: `ls
workflows/examples/` succeeds. The falsifying content is a 1-file skeleton, not authoring-product
content, so `a2_examples` remains greenfield in every way that matters — but the exact claim a
reader would re-run (`ls workflows/examples/` → nothing) does not reproduce. Recorded as D-1;
`a2_examples` may add its four YAMLs beside the README without conflict, and should treat the
README as the dir's intended index.

### Edge 2 — "the CLI has `workflow run/discard-tree/promote` but no `new/lint/plan`" → **PASS**

*Method.* Read the command map, then search it and the backing-script directory for any
`new`/`lint`/`plan` leaf under `workflow`:

```bash
sed -n '40,50p' src/agentic_dynamics/cli.py
grep -n '"lint"\|"plan"\|"new"\|lint_workflow\|plan_workflow\|workflow new' src/agentic_dynamics/cli.py
ls scripts/ | grep -i workflow
```

*Evidence.*

```
    # workflow
    ("workflow", "run"): "run_workflow.py",
    ("workflow", "discard-tree"): "record_discarded_tree.py",
    ("workflow", "promote"): "promote.py",
```

The `"lint"|"plan"|"new"` grep returns **NONE** — no such leaf exists anywhere in `cli.py`. The
CLI help string (`cli.py:156`) reads `workflow    run|discard-tree|promote`. The only
workflow-named backing scripts are `run_workflow.py` and `aggregate_workflow_metrics.py` — no
`new_workflow.py`, `lint_workflow.py`, or `plan_workflow.py` exists. A second probe confirms no
authoring surface hides under another verb: the full `_COMMANDS` table has no `workflow new/lint/
plan` entry, and no linter/planner module exists to wire (`ls workflows/lint*.py`, zero hits).

*Reading.* The claim holds. The three existing verbs map to their verified backing scripts
(`promote` → `promote.py`). `a3_command_surface` is greenfield: `new`/`lint`/`plan` join an
existing namespace without modifying `run`/`discard-tree`/`promote`, exactly as the phase
mandates.

### Edge 3 — "no `.opencode/agents/aio-control.md`" → **PASS**

*Method.*

```bash
ls .opencode/agents/
ls .opencode/agents/aio-control.md 2>&1
ls .claude/agents/ 2>&1
```

*Evidence.*

```
$ ls .opencode/agents/
data-analysis.md
instrument-dev.md
pipeline-ops.md

$ ls .opencode/agents/aio-control.md
ls: cannot access '.opencode/agents/aio-control.md': No such file or directory   # EXIT=2
```

`.claude/agents/` mirrors the same three (`data-analysis.md`, `instrument-dev.md`,
`pipeline-ops.md`). No `aio-control` agent exists on either platform.

*Reading.* The claim holds. Supporting fact for `a4_aio_agent` (verified, see §3): both agent
directories are **generated surfaces** — `_gen_instructions.py:284` renders
`.opencode/agents/{name}.md` from `agent_config/agents/{name}.md`, and `:345-346` renders the
`.claude/agents/` twin from the same source. So a4 must author `agent_config/agents/aio-control.md`
and regenerate (both formats), keeping `_gen_instructions.py --check` green — not drop a file
straight into `.opencode/agents/`.

### Edge 4 — "the AIO exists only as the vocabulary section in `agent_config/rules.md`" → **PASS**

*Method.*

```bash
grep -rln "AIO Control Agent" --exclude-dir=.git .
grep -c "AIO Control Agent" agent_config/rules.md agent_config/mental-model.md
grep -n "VOCABULARY" agent_config/rules.md
```

*Evidence.* Repo-wide, the phrase appears in exactly four files:

| File | Count | Nature |
|---|---|---|
| `agent_config/rules.md` | 1 | **the source** — line 27, inside the `**VOCABULARY:**` paragraph (`rules.md:25`) of the `**AUTHORITY**` section |
| `AGENTS.md` | 1 | the generated render of `rules.md` (same single passage) |
| `workflows/repository/authoring_product_aio.yaml` | several | the spec itself — the mandate being pinned |
| `.instrument/session.jsonl` | 1 | an untracked session transcript (0 tracked files under `.instrument/`) — machine-local instrumentation, not repo content |

`agent_config/mental-model.md`: 0 hits. `CLAUDE.md` and the `.claude/`/`.opencode/` instruction
docs: 0 hits — they reach the vocabulary by import (`@AGENTS.md`), not by inline copy. There is no
occurrence in `src/`, `scripts/`, `apps/`, `tests/`, `docs/`, or any agent definition.

*Reading.* The claim holds. The AIO's only definitional home in the repository is the vocabulary
section of `agent_config/rules.md` (and its direct render `AGENTS.md`). There is no agent file, no
module, no design doc that defines the AIO elsewhere — which is precisely the gap `a4_aio_agent`
closes. `a4`'s contract must be consistent with this single source passage (the six points the
phase lists mirror the vocabulary's prose: the packet every turn, run_ids/candidate_shas only,
the verified commands, never bypass the gates).

### Edge 5 — "actuation_ingestion has zero call sites (nothing fires it)" → **FAILED** — two real call sites exist, predating the spec (D-2)

*Method.*

```bash
grep -rn "derive_actuation_record" apps/ src/ scripts/ tests/
```

*Evidence.* The grep finds two production call sites (plus test references):

**Call site A — the Control Room's human-gated steer/interrupt emit (armed, publishes).**
`apps/control_room/services/supervisor.py:182-233` defines `_emit_actuation_record`, which
imports `derive_actuation_record` at `:200` and calls it at `:208`, then publishes the record via
`knowledge_stream.publish_event(..., authorized=True, armed=True, source_type="actuation")`
(`:224-230`). It is wired, not dead: `apps/control_room/routes/flags.py:48-53` (POST
`/api/flags/<sid>/steer`) and `:77-81` (POST `/api/flags/<sid>/interrupt`) call
`_services.emit_actuation_record(...)` after the human-gated side effect succeeds
(`routes/flags.py` module docstring: "actuation emit is called through `server._emit_actuation_record`"). Landed in `66f4729ba` (2026-08-20). The module's own docstring names it: "The **one
legitimate call site** is the Control Room's human-gated steer/interrupt handlers"
(`actuation_ingestion.py:10-13`), and `tests/test_actuation_ingestion.py:161-166` acknowledges it
explicitly while guarding only `scripts/supervise.py` and the legacy
`src/instrument/workflow_runner.py` path.

**Call site B — the shadow-decision recorder (artifact-only, deliberately unarmed).**
`src/agentic_dynamics/control/rules.py:369-422` `record_shadow_decision` calls
`derive_actuation_record` at `:416`, stamps `applied: False`, and writes the durable artifact JSON
— but deliberately **never publishes** to `kb:v1:changes` and never attempts the armed gate
("recorded, never applied", `:376-394`). Landed by the `1a155c42e` merge (2026-08-24).

Both predate the spec's `current_state` measurement date (2026-09-02) and the a5 phase's premise
("`derive_actuation_record`, which has ZERO call sites today", `authoring_product_aio.yaml:252`).

*Reading.* The claim does not hold. The actuation path has had real call sites since 2026-08-20 —
one of them (the Control Room steer/interrupt) armed and stream-publishing when a human operator
acts on a flagged session. The stale "ZERO call sites (nothing fires it yet)" assertion also lives
in the generated instruction surfaces (`agent_config/mental-model.md:488` and its `.opencode/`/
`.claude/` renders), which is the prose `a5` inherits. What remains genuinely absent — the actual
residual `a5` exists to close — is any **AIO/permanence-decision caller**: no promote/publish/
approval decision anywhere emits an actuation record, and the AIO agent (edge 3) does not exist to
do so. `a5`'s VERIFY item (d) ("actuation_ingestion now has a real call site — the zero-call-site
gap is closed") targets a gap already closed; the deliverable that matters is the permanence
emission seam. Nuances recorded in D-2: whether the steer/interrupt path has *ever fired in
production* is not determinable at the pin (it needs a human POST against a flagged session), and
the CI guard's legacy path (`src/instrument/workflow_runner.py`) no longer exists post-
consolidation, so the guard is partially vacuous (the runner now lives at
`src/agentic_dynamics/runtime/workflow_runner.py`, currently call-free by the same grep).

---

## 3. Supporting current-state facts (verified, not mandated)

These are not among the five mandated edges, but later phases depend on them. They were cheap to
verify, so they were verified.

| Assertion | Method | Result |
|---|---|---|
| `.opencode/agents/` and `.claude/agents/` are GENERATED from `agent_config/agents/` | `ls agent_config/agents/` + `grep render scripts/_gen_instructions.py` | **PASS** — 3 sources (`data-analysis.md`, `instrument-dev.md`, `pipeline-ops.md`); `render_opencode` emits `.opencode/agents/{name}.md` (`:284`), `render_claude` emits `.claude/agents/{name}.md` (`:345-346`); validator knows the `.opencode/agents/` prefix (`:386`). a4 must add `agent_config/agents/aio-control.md` + regenerate, never author the generated file directly. |
| `workflow new/lint/plan` backing modules do not exist anywhere | `grep` of `scripts/`, `workflows/`, `src/agentic_dynamics/` for a linter/planner/scaffold | **PASS** — no `lint_workflow.py`, no `plan_workflow.py`, no schema module; zero `workflow-v1.schema.json` occurrences outside the spec |
| The workflow corpus the linter must not break | `find workflows -name '*.yaml'` | **PASS** — measured **173** workflow YAMLs under `workflows/` (excluding the empty `examples/`): `repository/` 147 + `operations/` 20 + `research/` 6; matches `data.js` `workflow_specs` (173 on `main`; 172 at this HEAD, one rebuild behind) |
| The a7 gate suites for a1-a5 do not exist yet | `ls tests/test_workflow_schema.py` (etc.) | **PASS** — `test_workflow_schema.py`, `test_workflow_linter.py`, `test_workflow_auth_cli.py`, `test_aio_agent.py`, `test_aio_emission.py` all ABSENT; they are deliverables of a1-a5, so a gate failure must be read as "an upstream phase did not deliver its tests", not a broken gate |
| The module docstring + CI test treat the Control Room steer/interrupt handler as the legitimate actuation caller | read `actuation_ingestion.py:8-26`, `tests/test_actuation_ingestion.py:160-176` | **PASS** — both name it explicitly; the test guards only `scripts/supervise.py` + the nonexistent legacy `src/instrument/workflow_runner.py` |
| `scripts/supervise.py` is call-free | `grep -c derive_actuation_record scripts/supervise.py` | **PASS** — 0 |

---

## 4. Deviations recorded against the pinned bytes / mandate

Recorded per the D-series convention. Each deviation is a correction to the spec's stated
baseline that the implementation phases should consume; D-1 and D-2 are FAILED edges per the
mandate's own rule, D-3 is prose-only and falsifies no edge.

**D-1 — `workflows/examples/` EXISTS as a content-free skeleton, so edge 1 does not reproduce
literally.** `ls workflows/examples/` succeeds: the directory holds one placeholder README
(`Template specs. Populated by consolidation Stage 2.`), committed in `20813fa2b`. The spec's
"no workflows/examples/" is true of example *workflows* (zero YAMLs) but not of the *path*. This
does not disturb `a2_examples` (the four YAMLs land beside the README, which is the dir's natural
index) but the edge is recorded FAILED rather than smoothed over.

**D-2 — the actuation path has TWO real call sites (Control Room steer/interrupt — armed and
publishing — plus the shadow-decision recorder), so edge 5 and the a5 premise "ZERO call sites
today" are stale.** `derive_actuation_record` is called at
`apps/control_room/services/supervisor.py:200,208` (landed 2026-08-20, `66f4729ba`) and at
`src/agentic_dynamics/control/rules.py:396,416` (landed by 2026-08-24, `1a155c42e`); both predate
the `current_state` measurement of 2026-09-02. The stale "ZERO call sites (nothing fires it yet)"
claim also lives in `agent_config/mental-model.md:488` + its generated `.opencode/`/`.claude/`
renders. `a5_aio_emission` should (i) treat its deliverable as the AIO-permanence emission seam
(promote/publish/approval call sites), which is genuinely absent, not as "the first caller"
(already exists); (ii) target its VERIFY (d) at the permanence caller it adds rather than at
closing a zero-call-site gap; and (iii) not propagate the stale mental-model note. `a6_adversarial`
should attack the real residual (does an AIO promote decision actually emit?) rather than the
already-satisfied "some caller exists" question. Note: whether the steer/interrupt path has ever
fired in production is not determinable at the pin (human-gated, Control-Room only); the claim
"nothing fires it" is falsified at the *call-site* level, which is the level the mandate's edge 5
states.

**D-3 — the spec's prose says "the corpus is 181 YAMLs"; the measured tree has 173.** All
references to "the 181-spec corpus" (domain_context, hard rule 2, a1/a6 prompts) name the
historical corpus the schema/linter must not break. Measured at the pin: 173 workflow YAMLs under
`workflows/` (excluding the empty `examples/`): 147 `repository/` + 20 `operations/` + 6
`research/` — consistent with `data.js`'s `workflow_specs` figure. The count is prose, not a
mandated edge; recorded so a1's "corpus is UNTOUCHED" VERIFY and a6's cross-check target the real
number. (The spec was left as authored — repairing prose would edit the very file whose SHA256
this document pins.)

---

## 5. Scope compliance

The phase mandate (a0_pin_spec prompt): write this preregistration carrying the pin + the five
edges verified against the actual repo, then commit with the `[workflow] a0_pin_spec — <goal
prefix>` subject.

- **Created:** `docs/reviews/authoring_product_aio_preregistration.md` (this file) — the wave's
  pin, in the `/tmp/wt_wave3` worktree at the spec-commit tip.
- **Edited:** nothing else. Every verification above is read-only — `sha256sum`, `git rev-parse`,
  `ls`, `git ls-files`, `git ls-tree`, `find`, and `grep`/`sed` reads. No `_gen_instructions.py`
  render was invoked; no control-db write was made; no model call was made.
- **Not done, deliberately:** the spec's prose was left as authored — repairing its `current_state`
  (edges 1 and 5) or its corpus count (D-3) would edit the very spec whose SHA256 this document
  pins. The `run.log` modification in the working tree is a runner artifact, untouched and
  unstaged.

---

## 6. Verdict

| # | Mandate edge (as stated) | Verdict |
|---|---|---|
| 1 | No `workflows/schema/` + no `workflows/examples/` | **FAILED (D-1)** — `workflows/schema/` absent (strong PASS); `workflows/examples/` exists as a content-free skeleton (one placeholder README, `20813fa2b`), zero example YAMLs |
| 2 | CLI has `workflow run/discard-tree/promote`, no `new/lint/plan` | **PASS** — `cli.py:45-47` maps the three; zero `new`/`lint`/`plan` leaves anywhere in `cli.py`; no backing module exists |
| 3 | No `.opencode/agents/aio-control.md` | **PASS** — the dir holds exactly `data-analysis.md`, `instrument-dev.md`, `pipeline-ops.md`; `.claude/agents/` mirrors the three |
| 4 | The AIO exists only as the vocabulary section in `agent_config/rules.md` | **PASS** — single hit at `rules.md:27` inside the `**VOCABULARY:**` paragraph; elsewhere only in the generated `AGENTS.md` render, the spec itself, and an untracked session transcript |
| 5 | `actuation_ingestion` has zero call sites (nothing fires it) | **FAILED (D-2)** — two production call sites predate the spec: Control Room steer/interrupt emit (`supervisor.py:200,208`, armed + publishing, `66f4729ba`) and `record_shadow_decision` (`rules.py:396,416`, artifact-only, `1a155c42e`); no AIO/permanence caller exists (the true residual for a5) |

**Pin verdict: 3/5 edges hold exactly as stated; edges 1 and 5 FAILED against the actual repo, each
recorded with reproducible evidence and a true-state correction (D-1, D-2).** The failures are
corrections, not blockers: a2 and the a5 permanence seam remain greenfield in the ways that matter,
and a6 now knows to attack the real residual (does an AIO permanence decision emit?) rather than a
claim the tree already contradicts. Edge 2 (the command surface), edge 3 (no aio-control agent),
and edge 4 (vocabulary-only AIO) anchor `a1`/`a3`/`a4` greenfield as stated; §3's supporting facts
add the a4-critical fact that `.opencode/agents/` is generated from `agent_config/agents/`.

The mandate is anchored: spec SHA256
`980fd29400705e5e6ab4570c9c716604124a9e7c85c8d9a09b45fa63161fe8d5` at git
`24510116e76d50402c3bb14cc3e3bc5e925fbbe9`. `a1_schema_linter` (implementation) may proceed.
