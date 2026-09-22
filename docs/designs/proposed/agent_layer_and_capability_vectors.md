---
status: proposed
---
# The agent layer: roles for the workflows, and capability vectors as the binding's content

**Status:** proposed (2026-09-22). **Author:** the AIO, from the controller's direction ("what
agents do we need for our workflows now, so it's not just prompts and skills plus tools — and
how does this fit our plugin?").

## 1. The observed gap (facts, not framing)

* The repo ships **four agents** (`agent_config/agents/` → `.opencode/agents/` + `.claude/`
  mirrors): `aio-control` (primary, pro) and three subagents — `data-analysis`,
  `instrument-dev`, `pipeline-ops` (flash).
* **Workflow phases do not use them.** A phase runs as `kind: agent` with a `run_model:` pin;
  the adapter's worker pin (`WORKER_AGENT = "build"`, `adapters/opencode.py`) sends every
  phase to the **built-in `build` profile**. There is no `run_agent:` key anywhere in the
  corpus or the runner.
* The plugin's identity binding covers the **primary AIO session only**; phase sessions and
  subagents are unbound, and Unit D's gate (live, see §5) validates the *AIO's* binding, not a
  phase's role.
* Therefore: roles today live in **prompts** (the specs' step prompts carry the persona), not
  in the agent layer. The `agent` surface is the thinnest plane in an otherwise
  control-plane-heavy repo.

## 2. The roster (one role per plane × skeleton-contract phase)

The skeleton contract's phases already name what each step must DO; the roster gives each a
defined actor with scoped permissions, a model class, and a surface it owns.

| role | plane it owns | phase it serves | model | permissions |
|---|---|---|---|---|
| `aio-control` *(exists)* | the control plane's acts | operator turns; promotion | pro | edit allow (worktrees) |
| `spec-author` | `workflows/repository/`, `experiments/definitions/` | authoring surface (`workflow new/lint/plan`) + `prior` | pro | edit allow in those trees; no `src/` |
| `verifier` | read-only across planes | `posterior` | flash | **edit deny** — evidence only |
| `adversarial-reviewer` | read-only across planes | `g_adversarial` | a DIFFERENT family (today pinned `openai/gpt-5.6-terra`) | **edit deny** except `notes/adversarial_review.md` |
| `instrument-dev` *(exists)* | `measurement/`, `adapters/`, `runtime/` | `execute` (instrument loops) | flash | edit ask |
| `control-room-dev` | `apps/control_room/` + the render gate | `execute` (L23) | flash | edit allow in `apps/control_room/` |
| `site-editor` | `apps/website/` | `execute` (L24) | flash | edit allow in `apps/website/` |
| `data-analysis` *(exists)* | analysis + lab books | `prior` (inventory) | flash | edit ask |
| `pipeline-ops` *(exists)* | data pipeline + deploy prep | ops tasks | flash | edit ask |

Design rules: **independence is a permission boundary** (`verifier` and
`adversarial-reviewer` cannot edit what they judge — the L20 posterior's V-list and the terra
reviews are the behaviour this formalizes); **models follow the role** (authoring/review on a
pro model class, mechanical work on flash); **ownership is per-plane**, so a phase's blast
radius is visible in its agent definition rather than inferred from its prompt.

## 3. `run_agent:` — the phase schema key

The adapter already accepts `--agent` (`adapters/opencode.py`: "Callers that select a
specialized profile pass `agent=` and keep it"). The missing piece is the workflow layer:

```yaml
phases:
  - name: execute
    kind: agent
    run_model: deepseek/deepseek-v4-flash
    run_agent: control-room-dev        # NEW — resolves to .opencode/agents/control-room-dev.md
```

Resolution order (proposed): `run_agent` (phase) → `spec.workflow.params.agent` → the
existing `WORKER_AGENT` pin (`build`). Defaults never change: a spec without `run_agent`
behaves exactly as today. The runner threads the resolved agent into the step executor's
kwargs; the cell path already passes opencode flags through, so the container needs no new
mount (the agents live in the repo).

## 4. Capability vectors — the binding's content

The task-context schema is static (`task`, `predecessor_slug`, `knowledge_ids`, `acceptance`,
…). A **capability vector** makes the binding's *authority* explicit and versioned:

```json
{
  "identity": {"native_session_id": "ses_…", "agent": "aio-control", "role": "aio-control"},
  "task": {"slug": "…", "acceptance": "…", "project": "agentic-dynamics"},
  "capabilities": {
    "verbs": ["run_workflow", "promote"],     // the consequential verbs this session may exercise
    "scopes": ["workflows/repository/**", "apps/control_room/**"],
    "leases": {"campaign_budget_usd": 4.0, "concurrency": 1},
    "expires_at": "2026-09-23T00:00:00Z"
  },
  "version": {"context_version": 5, "authorization_version": 2}
}
```

Rules:

* **Capabilities are data, granted and checked — never inferred.** Unit D's gate compares the
  required capability for a verb against the binding's vector (today it checks identity,
  agent, authorization identity, task revision, and project — the vector generalizes those
  checks without weakening them).
* **Versioning rides the existing epochs**: routine progress bumps `context_version`;
  a task-defining or capability change mints a new `authorization_version` (already the
  stale-command refusal in `_validate_aio_binding`). A capability-poorer update is a
  *downgrade* and must mint a new authorization identity — never mutate in place.
* **Subagents and phases inherit a SCOPED binding**: same task, narrower vector (their role's
  verbs/scopes), the parent's identity recorded as provenance. This is what turns "the AIO
  session is bound" into "every actor acting for the task is bound, per role."
* **First real consumers** (in order): (1) the submit gate refusing an under-capable session
  for `run_workflow`; (2) `promote` requiring the AIO role + the run's own evidence; (3) the
  capsule injecting the role-relevant subset (below).

## 5. How this fits the plugin

* **Binding already works** (Unit C) and **enforcement is live** (Unit D): `validate-submit`
  and the host launch broker re-resolve the binding from the durable store by native session
  id — a forged `binding_id` refuses by name (live-proven 2026-09-22, both directions; see
  `.opencode/plugins/README.md`).
* The vector is the natural *extension of the same record*: today the binding carries
  identity + task + project + epochs; §4 adds the role and its capabilities to the same
  versioned slot, so **no new store** is needed.
* **Capsule subsets per role**: the capsule stays primary-only for the AIO; a scoped child
  binding gets a bounded capsule slice (its task, its acceptance, its role's sources) — which
  is also the experiment surface for "self-optimizing composition" (do NOT build the learner;
  build the ablations — see §6).
* **Fail-visible, as today**: an unavailable store refuses; a missing capability refuses by
  name; capacity stays ADVISORY.

## 6. Explicitly out of scope (with preconditions)

* **Self-optimizing capsule composition** — no downstream-performance signal per capsule
  variant exists. Precondition: a capsule-ablation ExperimentSpec (arm = capsule variant;
  metric = downstream quality-per-dollar) — a study, not a plugin feature.
* **TLA+/Alloy of the binding protocol** — the protocol's invariants are already pinned by
  tests (version serialization, first-write-exactly-once, copied-slot refusal, modified-request
  refusal, stale-authorization refusal). Precondition for formal modelling: the protocol grows
  a second writer or a cross-host path. Until then, stateful property tests are the ceiling
  worth paying for.

## 7. Migration path

1. **Roster** (§2): add the five new agent definitions in `agent_config/agents/`, regenerate
   the surfaces (`scripts/_gen_instructions.py`), guard with a test that every phase's
   `run_agent` (when set) resolves to a defined agent.
2. **`run_agent`** (§3): schema + runner plumbing + fail-first test (phase honors the key;
   default unchanged).
3. **Capability vectors** (§4): extend the binding record with the vector + version semantics;
   extend Unit D's gate with the required-capability check for the consequential verbs; tests
   for refuse/allow.
4. **Scoped child bindings** (§4, §5): the phases' sessions get scoped bindings; the plugin
   injects the subset capsule.

Each step is independently shippable; steps 1–2 are small and unblock the L22–L24 wave's
successors by making their phases' roles explicit.
