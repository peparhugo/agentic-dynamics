---
status: accepted
---

# authoring_product_aio — adversarial review (Wave 3)

**Role:** independent adversarial reviewer (a6), a different model + session from the flash
author. **Spec:** `workflows/repository/authoring_product_aio.yaml` (pinned at a0, SHA256
`980fd29400705e5e6ab4570c9c716604124a9e7c85c8d9a09b45fa63161fe8d5`). **Worktree HEAD:**
`fb027f2d9`. **Verdict: NOT merge-ready — 5 findings, two of which are gate-suite failures
introduced by this branch.**

Every claim below was re-verified against the actual code (commands run + actual output), never
asserted. The attack ran in the mandated order: a1 → a3 → a4 → a5 → cross. Each named a1
violation DOES fire when the crafted workflow genuinely matches it; a1 PASSES on the four named
violations but has a genuine slip-through (A1). a3 and a4 PASS. a5 emits for promote/publish but
the `approve` verb is declared yet unwired (A2). The cross-check FAILS: the corpus is untouched
(184 ExperimentSpecs, zero workflow-v1 leak), but the gate suite is NOT green — two guard tests
break on branch deliverables (A4, A5), alongside three pre-existing failures inherited from the
branch point.

## The findings

| # | severity | attack | finding |
|---|---|---|---|
| **A1** | MEDIUM | (1) a1 linter | **An `approval` step with `executor: agent` slips through `prompt-as-evidence` clean (exit 0, `ok: true`).** The rule only checks `kind == "gate"`; the schema's `executor` enum (`agent|test|command|human`) is not constrained per-kind, so an `approval` (declared "controller/human checkpoint") carrying an LLM executor is treated as legitimate human evidence. An author can make an LLM self-approval the candidate's ONLY required gate — the exact anti-pattern the rule exists to forbid. |
| **A2** | MEDIUM | (4) a5 emission | **The `approve` permanence verb is declared (seam `PERMANENCE_VERBS`, contract point 6, a5 SHAPE) but has NO call site.** Only `promote.py` (`verb=promote`) and `publish_release.py` (`verb=publish`) reach `aio_emission`. The AIO's gated-run approval — a P0 controller act named in the doctrine's authority tier — is still unobservable. |
| **A3** | LOW | (3) a4 deploy-gate fix | **The a4/a2 deploy-gate false-positive fix introduces a COMMAND-tier false negative for shell-wrapped deploys.** `sh -c "firebase deploy"`, `bash -c "firebase deploy"`, and `eval "firebase deploy"` all return `None` (firebase is not at a "known launcher" command position and there is no `&&`/`;`/`||` chain). The OUTPUT tier backstops only *successful* deploys (the "Deploy complete!" banner); a wrapped deploy that fails before the banner slips both tiers. |
| **A4** | **HIGH** | (5) cross / gate suite | **`tests/test_context_plane_contracts.py::test_committed_spec_corpus_gains_zero_new_refusals_from_the_i5_gate` FAILS on this branch.** The four new `workflows/examples/*.yaml` (workflow-v1 docs, not ExperimentSpecs) are discovered by the test's own `(REPO_ROOT / "workflows").rglob("*.yaml")` glob at `test_context_plane_contracts.py:453` — not the new exclusion-aware `committed_spec_paths` — and `load_spec` raises `ValueError: ExperimentSpec missing required fields`. The workflow-v1 exclusion was wired into `spec_status`'s discovery but not this consumer. |
| **A5** | HIGH | (5) cross / gate suite | **`tests/test_stale_path_guard.py::test_accepted_docs_use_no_retired_paths` FAILS on this branch.** The a0 deliverable `docs/reviews/authoring_product_aio_preregistration.md` references the retired path `src/instrument/workflow_runner.py` (lines 243, 265, 282), tripping the retired-path guard. |

Three further gate failures exist but are **not branch-introduced** (verified `git diff --name-only
main...HEAD` touches none of `README.md`, `apps/website/data.js`, or `scripts/lab_manifest.json`):
`test_doc_lifecycle::test_readme_spec_counts_match_index`,
`test_publication_singular_door::test_readme_figures_match_public_statistics`, and
`test_lab_outputs_canonical::test_site_lab_keys_are_all_contract_bearing`. They are main-side
README/data.js drift inherited at the branch point and are outside this wave's scope fence.

## Attack log (in order, with re-verification)

### (1) a1 — does the linter actually reject each named violation?

**Four named violations, each crafted and run through the real CLI surface**
(`python3 scripts/workflow_lint.py <file> --json`):

| crafted violation | finding emitted | exit |
|---|---|---|
| `metadata.status: completed` (authored status) | `authored-status` | 1 |
| `spec.status: running` (authored status nested) | `schema-invalid` + `authored-status` | 1 |
| mutating step, no gate | `mutating-without-verification` (+ `promotion-without-gates`) | 1 |
| gate, `candidateFrom` a non-producing step | `unbound-gate` | 1 |
| gate with zero mutating upstream | `unbound-gate` | 1 |
| gate reaching 2 mutating ancestors (no `candidateFrom`) | `unbound-gate` | 1 |
| required gate, `executor: agent` | `prompt-as-evidence` | 1 |

The `unbound-gate` rule was also probed at its three distinct triggers (candidateFrom a
non-producer; zero mutating upstream; multiple mutating ancestors) — all fire. A gate with a
single mutating upstream via `needs` correctly does NOT fire (it binds by the
single-mutating-upstream rule, which is correct behaviour, not a miss).

**Slip-through (A1).** `approval` + `executor: agent`, as the candidate's only `requiredGates`
entry, lints clean:

```
$ python3 scripts/workflow_lint.py /tmp/opencode/a1_attack/approval_agent.yaml --json
{"ok": true, "findings": []}   # exit=0
```

Root cause is two-part: (i) `_prompt_as_evidence_findings` skips every step whose `kind !=
"gate"` (`lint_workflow.py:585`), and (ii) the schema's `executor` enum is declared once for all
four step kinds with no per-kind constraint (`workflow-v1.schema.json` `$defs.step.properties.executor`),
so `approval.executor: agent` is schema-legal. The rule's own docstring claims "A controller
approval (kind: approval) is legitimate human evidence" — true only when the approval's executor
is actually `human`, which nothing enforces.

### (2) a3 — does `workflow new` scaffold a genuinely valid workflow?

**PASS.** `python3 scripts/workflow_new.py a6_probe --output-dir /tmp/opencode/a1_attack` wrote a
file that is schema-valid (independent `Draft202012Validator`, zero errors) AND linter-clean
(exit 0, empty findings). The scaffold also refuses an invalid name, refuses overwrite, and
refuses a bad template (writes nothing). Guard tests `tests/test_workflow_commands.py` (25) green.

### (3) a4 — is the AIO definition consistent with the doctrine?

**PASS.** The vocabulary section of `agent_config/rules.md` (rendered to `AGENTS.md`) is the
single doctrinal source; the agent definition is its operational form. The six contract points in
`agent_config/agents/aio-control.md` (and its committed `.opencode/agents/` + `.claude/agents/`
twins) are consistent with the doctrine: packet-every-turn, act-only-on-returned-ids, never-infer-
from-chat, permanence-through-verified-commands (`promote.py`/`publish_release.py`), never-hand-
edit-generated-surfaces, decisions-emitted. The surface is real: `aio-control` is registered in
`_gen_instructions.py`'s `AGENTS` manifest, `.opencode/agents` and `.claude/agents` are generated
trees, the committed twins byte-match `render_all()`, and `python3 scripts/_gen_instructions.py
--check` exits 0 ("38 generated files match"). Point 2 adds `gate_ids` to the doctrine's
`run_ids / candidate_shas` — a faithful superset, since the packet's `awaiting_approvals` /
`safe_actions` do carry `gate_id`. No contradiction found.

### (4) a5 — does a promote decision actually emit? is the lineage gate real?

**PASS for promote + publish.** `tests/test_aio_emission.py` (20) green, including the
end-to-end promote path against a fake knowledge stream: the observation lands first (and is
indexed), the actuation lands second with `causes == observation.knowledge_id`, and a causeless
actuation is rejected by the stream's `_resolves_to_observation` lineage gate (best-effort,
returns no entry id). The lineage gate is real code, not asserted: `knowledge_stream.publish_event`
requires `armed=True` AND `causes` resolving to an indexed observation-family record
(`knowledge_stream.py:192-204`). Emission is best-effort: a raising emitter / downed stream never
blocks the push (proven by `test_emission_failure_never_blocks_the_act`).

**Gap (A2).** `approve` is in `PERMANENCE_VERBS` and `build_observation`/`build_actuation` accept
it (guard-tested), but grep of `src/`+`scripts/`+`apps/` shows the seam is reached only from
`promote.py` and `publish_release.py`; no production call site emits a decision with
`verb="approve"`. The a5 mandate's VERIFY items are all promote-scoped, so this is a
contract-fidelity gap, not a mandate violation.

### (5) cross — corpus untouched; gate suite green?

**Corpus untouched: PASS.** `git diff --name-only main...HEAD` contains no change under
`workflows/repository|operations|research/` or `experiments/definitions/`. The four new
`workflows/examples/*.yaml` are workflow-v1 docs, correctly excluded from the ExperimentSpec index
by `experiment_spec.committed_spec_paths` (`_is_workflow_v1_document`): `committed_spec_paths('.')`
returns **184** specs with **zero** workflow-v1 leak. (The "181" figure in the mandate prose is the
historical D-3 count; the measured ExperimentSpec corpus is 184, consistent with the pin's 173
workflow YAMLs + `experiments/definitions/`.)

**Gate suite green: FAIL (A4, A5).** The fast path (`pytest -m fast`) reports 547 passed / 5
failed. Two of the five are branch-introduced (A4, A5 above); the other three are pre-existing
README/data.js/lab drift (see the finding note). The 91 authoring/AIO guard tests
(`test_workflow_schema/linter/examples/commands/aio_agent`) and 20 emission tests are green; the
regression is isolated to the two consumers the branch did not update.

## Verdict

**NOT merge-ready.** A4 and A5 are gate-suite failures this branch introduces; they must be
fixed before the branch lands. A1 is a genuine linter coverage hole worth closing (the fix is
small — constrain `approval.executor` to `human` in the schema, or extend `_prompt_as_evidence_findings`
to flag any non-human executor on an approval step). A2 and A3 are recorded as accepted
limitations: A2 because the a5 mandate's VERIFY items are promote-scoped (approval emission is a
declared-but-deferred follow-up), A3 because the deploy-gate OUTPUT tier backstops the successful
indirect-deploy case and the residual (a wrapped deploy failing before the banner) is narrow and
pre-dates the fix's output-tier design.

Recommended fixes (a follow-up phase, not this read-only review):

1. **A4** — update `tests/test_context_plane_contracts.py:453` to discover via
   `committed_spec_paths(REPO_ROOT)` (the same exclusion `test_spec_status.py` already uses),
   or skip `_is_workflow_v1_document` files.
2. **A5** — repoint the three `src/instrument/workflow_runner.py` references in
   `docs/reviews/authoring_product_aio_preregistration.md` to
   `src/agentic_dynamics/runtime/workflow_runner.py` (the consolidated path), or add a
   historical-reference allowlist entry.
3. **A1** — add a per-kind `executor` constraint (approval ⇒ `human`) to
   `workflow-v1.schema.json`, plus a linter finding for a non-human executor on an `approval`
   step, with a regression test.

## Scope compliance

- **Created:** `docs/reviews/authoring_product_aio_adversarial.md` (this file).
- **Edited:** nothing else. Every check was read-only (lint CLI runs against `/tmp/opencode`
  scratch files, `pytest`, `grep`, `git diff`). No model call was made; no generated surface was
  regenerated; no control-db write; no push. The `spec_status.py` probe that regenerated
  `experiments/specs/{index.json,STATUS.md}` was reverted (`git checkout --`) — the working tree
  is clean except this review.
