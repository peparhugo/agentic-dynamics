---
status: accepted
kind: preregistration
spec: control_db_publication
phase: p0_pin_spec
generated_at: 2026-09-01T22:30:40Z
---

# Preregistration — `control_db_publication`

**The house pin convention.** This document is written BEFORE any implementation phase
runs. Its purpose is twofold, and both halves are load-bearing:

1. **Anchor the run to exact bytes.** A workflow spec is a mutable file. If it is edited
   mid-run (a phase appends a fence, an operator retunes a prompt), the run that finishes
   is not the run that started, and the adversarial phase (p7) has no fixed target to
   falsify. Recording the spec's SHA256 makes the mandate immutable *by reference*: any
   later divergence is detectable by re-running one command.
2. **Verify the premises, do not assert them.** The spec's `current_state` block is a
   set of claims about the repository, written by the spec author on 2026-09-01. Every
   implementation phase is justified by those claims — you do not build a control db if
   one already exists, and you do not "collapse the instruction surfaces onto one
   generator" if the generator already emits `AGENTS.md`. A preregistration that copied
   those claims forward would be circular. This one re-derives each claim from the
   actual repository and records the command that produced the evidence, so a reader
   can reproduce every PASS without trusting this document.

The mandate is: **a claim that does not hold is a FAILED finding.** All six claims hold.
Two spec-integrity deviations were found and are recorded in §4 — they do not falsify any
claim, but they are facts about the pinned bytes and the reader is entitled to them.

---

## 1. The pin

| Field | Value |
|---|---|
| Spec path | `workflows/repository/control_db_publication.yaml` |
| Spec **SHA256** | `1d1c6a10ab5ebaeb6542c8adc16a3bf3e177f8724e241795d1ab78fc589791be` |
| Spec size | 32,486 bytes |
| Worktree HEAD (git sha) | `59b5ca42f473ca89f02ecb19c37a9876e8e2c592` |
| HEAD subject | `spec: control_db_publication — p0_pin_spec (the house pin convention)` |
| HEAD committed | 2026-09-02 00:23:27 +0200 |
| Branch | detached `HEAD` (worktree `wt_control_db`, `/tmp/wt_control_db`) |
| `main` at pin time | `99f671398d664a8da3a1fdeb9aa5193eaa6e76f1` |
| Working tree | clean except untracked `run.log` (a runner artifact, not a source file) |
| Pinned at | 2026-09-01T22:30:40Z |

Reproduce the pin — these are the EXACT bytes the run executes:

```bash
sha256sum workflows/repository/control_db_publication.yaml
# 1d1c6a10ab5ebaeb6542c8adc16a3bf3e177f8724e241795d1ab78fc589791be
git rev-parse HEAD
# 59b5ca42f473ca89f02ecb19c37a9876e8e2c592
```

If either value differs at the time p7 (adversarial) or p8 (test gate) runs, the spec was
edited mid-run and the mandate this document pins is no longer the mandate being executed.
That is itself a reportable finding, and this table is what makes it detectable.

### Spec shape at the pin (what is being anchored)

Nine phases, of which eight are `kind: agent` and one is `kind: test`:

| # | Phase | kind | scope | prompt bytes |
|---|---|---|---|---|
| 0 | `p0_pin_spec` | agent | `implementation` | 1466 |
| 1 | `p1_control_db` | agent | `implementation` | 3588 |
| 2 | `p2_outbox` | agent | `implementation` | 1525 |
| 3 | `p3_projection_watermarks` | agent | `implementation` | 1442 |
| 4 | `p4_control_packet` | agent | `implementation` | 1501 |
| 5 | `p5_instruction_surfaces` | agent | `implementation` | 1510 |
| 6 | `p6_publication_receipt` | agent | `implementation` | 1554 |
| 7 | `p7_adversarial` | agent | `adversarial_readonly` | 2270 |
| 8 | `p8_test_gate` | test | `implementation` | — (`tests:` list, no prompt) |

`p8_test_gate` gates on ten suites, six of which do not exist yet and are deliverables of
the phases above them:

```
tests/test_control_db.py               tests/test_outbox.py
tests/test_projection_watermarks.py    tests/test_control_status.py
tests/test_agent_config_render.py      tests/test_doc_lifecycle.py
tests/test_script_classification.py    tests/test_cli_resolution.py
tests/test_publish_release.py          tests/test_spawn_wrapper.py
```

The exact 12-state run vocabulary the spec mandates (recorded here so p7 can check the
delivered enum against the pinned mandate rather than against the delivered code):

```
queued · running · awaiting_approval · verifying · promotable · promoting
merged · projecting · published · failed · cancelled · quarantined
```

---

## 2. Verified current-state claims

Each claim is stated as the spec states it, then **independently re-derived** against the
repository at `59b5ca42f`. "Method" is the command actually run; "Evidence" is its actual
output. No claim below was accepted on the spec's authority.

### Claim 1 — no `experiments/results/control/control.db` exists → **PASS**

*Method.* Two independent probes, because a single `ls` would miss a database created at a
different path under a different name (which would still falsify "there is no durable
control state today"):

```bash
ls -la experiments/results/control/
find . -name 'control.db*' -not -path './.git/*'
grep -rn "control\.db" --include='*.py' --include='*.md' --include='*.yaml' .   # minus the spec itself
```

*Evidence.* `ls` → `No such file or directory` — the **directory** does not exist, not
merely the file. `find` over the whole worktree → zero matches. The source grep (excluding
`control_db_publication.yaml`, which would trivially self-match) → zero matches: no module
anywhere opens, creates, or names a control database.

*Reading.* The claim holds in its strong form. There is no control db and no code that
expects one, so `p1_control_db` is greenfield — it cannot collide with an existing schema,
and it owes no migration path.

### Claim 2 — no `control status` CLI surface (`agentic-dynamics control` does not resolve) → **PASS**

*Method.* Claim 2 is about *behavior*, so it is verified by execution, not by reading the
command table. The table is read second, to explain the behavior:

```bash
python3 -m agentic_dynamics.cli control status --json ; echo "EXIT=$?"
PYTHONPATH=src python3 -c "from agentic_dynamics import cli; print(cli._resolve(['control','status','--json']))"
ls scripts/ | grep -i '^control'
```

*Evidence.*

```
agentic-dynamics: unknown command control status --json
EXIT=2
resolve -> (None, [])
(no scripts/control*.py)
```

The resolver returns `(None, [])` — no prefix in `_COMMANDS` matches `control`. Inspection
of `_COMMANDS` (`src/agentic_dynamics/cli.py:21-118`) confirms the registered top-level
verbs are: `experiment`, `story`, `workflow`, `queue`, `analyze`, `data`, `knowledge`,
`graph`, `review`, `spec`, `validate`, `supervise`, `usage`, `release`, `surfaces`, `docs`,
plus the `registry` special case. `control` is absent. There is no backing script either.

A third probe rules out the packet existing under another entry point:

```bash
grep -rn "control-status/v1\|control_status" --include='*.py' --include='*.json' --include='*.ts' .
# zero matches (excluding the spec)
```

*Reading.* The claim holds, and holds broadly: neither the CLI verb, nor a backing script,
nor the `control-status/v1` schema string exists anywhere. `p4_control_packet` is
greenfield. Note for p4: `release` is already a registered verb
(`release check-protection` → `check_branch_protection.py`), so `p6`'s
`publish release --candidate-sha` must be reconciled with that existing namespace rather
than assumed free.

### Claim 3 — `scripts/_gen_instructions.py` renders `.opencode/` + `.claude/` but NOT root `AGENTS.md` → **PASS**

*Method.* The decisive test is not "does the string `AGENTS.md` appear in the generator"
(it does not, but a generator could write the file via a computed path). The decisive test
is to **execute the renderers and enumerate the output keys** — the writer
(`write_surfaces`, line 331) writes exactly `{**render_opencode(), **render_claude()}` and
nothing else, so those keys are the complete set of generated files:

```bash
PYTHONPATH=src python3 -c "<import _gen_instructions by path; enumerate render_opencode()|render_claude() keys>"
```

*Evidence.*

```
total surface files: 38
prefixes: ['.claude', '.opencode']
AGENTS.md in outputs: False
```

Thirty-eight files, every one of them under `.claude/` or `.opencode/`. The only occurrence
of the token `AGENTS` in the generator is line 54, `AGENTS = ("data-analysis",
"instrument-dev", "pipeline-ops")` — the **subagent name tuple**, unrelated to the root
instructions file. Root `AGENTS.md` is hand-maintained: `git log -- AGENTS.md` shows it
edited by ordinary commits (`03b3dff8c`, `f6ef98353`, `1983ef1c9`), and it carries
`status: accepted` frontmatter, not a generated-file banner.

*Corollary verified for `p5`.* The spec also requires `--check` as a CI gate. It does not
exist today:

```
main signature: () -> 'int'
argparse imported: False
```

`main()` takes no arguments and the module never imports `argparse` — the generator is
write-only, with no verify mode. So `p5_instruction_surfaces` must add both the `AGENTS.md`
output and the `--check` flag; neither is a modification of existing behavior.

*Reading.* The claim holds. The drift risk the spec names is real and structural: 38 files
are regenerated and one root instruction file is not, so the two can disagree silently.

### Claim 4 — `apps/website/index.html` hard-codes a session count that contradicts `data.js` → **PASS** (actual numbers recorded below)

The mandate explicitly says to record the ACTUAL numbers rather than repeat the spec's.
They are recorded here, and they match the spec's `1,067` vs `1027`.

*Method.*

```bash
grep -n "1,067\|1067\|1,027\|1027" apps/website/index.html
grep -n "story_sessions" apps/website/data.js
```

*Evidence — `data.js` (the canonical, generated source; `build_data.py` output):*

| Field | Value | Provenance tag |
|---|---|---|
| `story_sessions` | **1027** (appears twice, both `1027`) | `"C"` computed / `"M"` measured |
| `stories_total` | 207 | `"C"` |
| `variants` | 7 | `"M"` |
| `story_total_cost` | 309.1685 | — |
| `generated_at` | 2026-09-01T06:11:21.881091+00:00 | — |

*Evidence — `index.html` (hand-authored prose):* the literal string `1,067` appears **4
times**, and the data-bound span `data-stat="story_sessions"` appears **2 times**:

| Line | Form | Text |
|---|---|---|
| 6 | hard-coded `1,067` | `<meta name="description" … measures that collision across 1,067 sessions and 7 models.">` |
| 8 | hard-coded `1,067` | `<meta property="og:description" … from 1,067 sessions and 7 models.">` |
| 74 | **bound** `1,027` | `<span data-stat="story_sessions">1,027</span>` (proof card "Story sessions") |
| 83 | hard-coded `1,067` | `<dt>Corpus / date</dt><dd>1,067 story sessions, 7 models (measured [M]); updated 2026-08-27.</dd>` |
| 204 | hard-coded `1,067` | `<p class="lead">The supporting corpus contains 1,067 instrumented story sessions.</p>` |
| 255 | **bound** `1,027` | `<span data-stat="story_sessions">1,027</span> story sessions · …` |

*Reading.* The claim holds, and the failure is sharper than "the page is stale". The **same
page** states both numbers: the data-bound spans render 1,027 (agreeing with `data.js`)
while four hand-written passages assert 1,067 — a 40-session discrepancy, self-contradictory
within one document. Line 83 is the most severe: it tags the wrong number `(measured [M])`,
i.e. it claims measured provenance for a figure no measurement produced.

*Corollary verified for `p6`.* No HTML-consistency test exists today:
`ls tests/ | grep -i "html\|site\|website"` returns nothing, and the only suites mentioning
`index.html` are `test_admin_claude_agents_frontend.py`, `test_static_narrative_guard.py`,
and `test_admin_frontend.py` — Control Room frontend tests, none of which cross-checks
`apps/website/index.html` against `data.js`. This is precisely why the contradiction
survived to be found by hand.

### Claim 5 — the outbox does not exist; children emit best-effort → **PASS** (both halves)

*Method (half A — absence).*

```bash
grep -rn "outbox" --include='*.py' --include='*.md' --include='*.yaml' --include='*.json' .
ls src/agentic_dynamics/control/
```

*Evidence (half A).* Every `outbox` hit is inside
`experiments/results/reports/exp_batch_batch_collaborative_editor_baseline clau/code/collab/sync.py`
— source code **written by a story agent** as an experiment artifact (a CRDT sync buffer),
not framework code. Zero hits in `src/`, `scripts/`, `apps/`, `tests/`, or `docs/`. The
`control` plane contains 28 modules (`admission.py`, `lease_registry.py`, `settlement.py`,
`facts.py`, …); there is no outbox module and no table that would back one.

*Method (half B — the emission path is best-effort).* Read the actual call site rather than
infer it from the spec's characterization:

```bash
grep -n "emit_phase_finding\|emit_self" src/agentic_dynamics/runtime/workflow_runner.py
sed -n '905,922p' src/agentic_dynamics/runtime/workflow_runner.py
```

*Evidence (half B).* `workflow_runner.py:3205-3206` — after a phase commits, the runner
calls `_emit_self_finding(pr, goal=goal, scope=cell_scope(wd))`. That function
(`workflow_runner.py:908-921`) is documented and implemented as best-effort:

```python
def _emit_self_finding(pr: PhaseResult, *, goal: str, scope: str) -> None:
    """Emit a completed phase's finding into the cell's own scope (self-build producer).

    Best-effort: emission failure (Redis down, write guard off, artifact path issue) is
    swallowed — a self-build finding is a progressive enhancement, never a gate on the phase.
    ...
    """
    try:
        from agentic_dynamics.knowledge.knowledge_ingestion import emit_phase_finding
        emit_phase_finding(pr, goal=goal, repository_id=scope, revision=pr.commit_hash)
    except Exception:
        pass  # progressive path — never block or fail the phase on emission
```

A bare `except Exception: pass` around the emission is the mechanical proof of "best-effort":
a dropped knowledge event is invisible and unrecoverable. The emit is **per-child** — the
scope is `cell_scope(wd)` = `self-<worktree>`, so each child writes into its own scope with
no parent-side record that the write was owed.

*Reading.* Both halves hold. There is no atomic parent-side write and no retry; the current
path can silently lose events, which is exactly the gap `p2_outbox` exists to close.

### Claim 6 — no projection watermark surface exists → **PASS**

*Method.* Search for the concept by its name across every plausible file type, then search
for the weaker term `projection` to be sure a watermark surface does not exist under
different vocabulary:

```bash
grep -rni "watermark" --include='*.py' --include='*.ts' --include='*.md' --include='*.json' --include='*.yaml' .
grep -rni "projection" --include='*.py' src/ scripts/ apps/
```

*Evidence.* `watermark` → **zero occurrences** anywhere in the repository (excluding the
spec). `projection` matches exist but none is a read-model watermark:
`admission_context.py:203,369`, `cost_provenance.py:243`, `admission.py:303`,
`lease_registry.py:364` are all "JSON-safe projection" (serialization helpers);
`spec_status.py:142` is "a projection, not the whole WorkflowRunResult";
`fact_ingestion.py:53,153` is `PATTERN_PROJECTION_VERSION` / `build_pattern_projection_record`
(a knowledge-record kind); `augment.py:157` is a `pattern_projection` RAG flag.

*Supporting fact verified.* The spec's premise that the knowledge plane has four consumer
groups but no watermark is confirmed by execution:

```
CONSUMER_GROUPS -> ('kb-chroma-v1', 'kb-neo4j-v1', 'kb-ledger-v1', 'kb-registry-v1')   # count: 4
```

Four groups consume the stream; nothing anywhere records where each one has read to.

*Reading.* The claim holds. There is no `last_event_id`, no lag figure, and no
`last_success_at` for any projection — so today it is impossible to answer "is Chroma caught
up?" without querying Chroma itself, which is the observability gap `p3` closes.

---

## 3. Supporting current-state facts (verified, not mandated)

These are not among the six mandated claims, but the spec's `current_state` asserts them and
later phases depend on them. They were cheap to verify, so they were verified.

| Assertion | Method | Result |
|---|---|---|
| Run state lives in ledger JSON under `experiments/results/workflows/<spec>/` | `ls experiments/results/workflows/` | **PASS** — 145 spec directories |
| Knowledge plane has four consumer groups | import `CONSUMER_GROUPS` | **PASS** — exactly 4 |
| P0 wave merged: `runtime/executor.py` exists | `ls src/agentic_dynamics/runtime/executor.py` | **PASS** — 7,447 bytes |
| P0 wave merged: `scripts/promote.py` is the push-to-main path | `ls scripts/promote.py` | **PASS** — present; `workflow promote` registered in `_COMMANDS` |
| `docs/reviews/` exists to receive this document | `ls -d docs/reviews` | **PASS** |

---

## 4. Deviations found in the pinned bytes

Recorded per the D-series convention: one-line notes with reasoning, no theatrical
percentages. Neither deviation falsifies a claim, so neither fails this phase — but both
are properties of the exact bytes being pinned, and p7 should treat them as known.

**D-1 — the phase scope fence landed six times in `p1_control_db` and zero times in
`p2`–`p7`.** Commit `f74fd73c8` ("phase scope fence — the 2026-09-02 failed-run lesson")
appended the fence paragraph
(`SCOPE FENCE: this phase delivers ONLY its own deliverable…`) intending one copy per
implementation phase. Measured per-phase occurrence counts:

```
p0_pin_spec  0   p1_control_db  6   p2_outbox  0   p3_projection_watermarks  0
p4_control_packet  0   p5_instruction_surfaces  0   p6_publication_receipt  0
p7_adversarial  0   p8_test_gate  0 (test phase, no prompt)
```

All six copies are concatenated into `p1_control_db`'s prompt, inflating it to 3,588 bytes
against a ~1,500-byte norm for its siblings. Reasoning for recording rather than fixing:
the fence exists to prevent the exact failure mode that produced it (a phase doing the next
phase's work), and `p2`–`p6` are now unfenced — the phases most likely to reach backwards
into the control-db schema. This phase's mandate permits **no edits to existing files**, so
the spec is left exactly as pinned; the deviation is surfaced for the controller's decision
and for p7's attack list. `p0_pin_spec` carries its own narrower fence ("The ONLY files this
phase may create: the preregistration doc"), which is honored — see §5.

**D-2 — `p8_test_gate` gates on six suites that do not exist yet.** Of its ten test files,
`test_control_db.py`, `test_outbox.py`, `test_projection_watermarks.py`,
`test_control_status.py`, `test_publish_release.py`, and `test_cli_resolution.py` are absent
at the pin and are deliverables of `p1`–`p6`. This is expected for a test gate at the end of
an implementation wave — recorded so that a p8 failure is read correctly as "an upstream
phase did not deliver its tests" rather than as a broken gate.

---

## 5. Scope compliance

The phase mandate: *"The ONLY files this phase may create: the preregistration doc. The ONLY
edit allowed: none to existing files."*

- **Created:** `docs/reviews/control_db_publication_preregistration.md` (this file) — one file.
- **Edited:** nothing. Every verification above is read-only — `sha256sum`, `git rev-parse`,
  `ls`, `find`, `grep`, `sed -n`, and `python3 -c` imports that call pure render/resolve
  functions. `write_surfaces()` was deliberately **not** called; only `render_opencode()` and
  `render_claude()` were, which return dicts and touch no disk.
- **Not done, deliberately:** D-1 (the misplaced scope fence) was left unrepaired. Fixing it
  would edit `workflows/repository/control_db_publication.yaml` — an existing file, and the
  very file whose SHA256 this document pins. Repairing it would invalidate the pin in the act
  of recording it.

---

## 6. Verdict

| # | Claim | Verdict |
|---|---|---|
| 1 | No `experiments/results/control/control.db` exists | **PASS** |
| 2 | No `control status` CLI surface (`agentic-dynamics control` does not resolve) | **PASS** |
| 3 | `_gen_instructions.py` renders `.opencode/` + `.claude/` but NOT root `AGENTS.md` | **PASS** |
| 4 | `index.html` hard-codes `1,067` while `data.js` says `1027` | **PASS** |
| 5 | The outbox does not exist; children emit best-effort | **PASS** |
| 6 | No projection watermark surface exists | **PASS** |

**6/6 PASS. No claim failed. Two deviations recorded (D-1, D-2), neither falsifying.**

The mandate is anchored: spec SHA256
`1d1c6a10ab5ebaeb6542c8adc16a3bf3e177f8724e241795d1ab78fc589791be` at git
`59b5ca42f473ca89f02ecb19c37a9876e8e2c592`. Every premise the implementation wave rests on
was verified against the repository, not inherited from the spec. `p1_control_db` may proceed.
