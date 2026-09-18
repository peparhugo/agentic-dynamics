# Worker image, loaded revision, and the engine-shaped output — identified

**Run:** `run-75e8319533fb` (job `91492963f979`, `flash_ladder_kb`, 2026-09-18).

## The chain, from the run's own records and the artifacts it left

1. **The launch.** The spawn-wrapper dispatch (ladder `workflow-runner` service, journal) was
   `docker-compose run --rm -e FINOPS_CELL_ID=91492963f979 -e FINOPS_ADMISSION_REQUIRED=1 … workflow-runner python3 scripts/run_workflow.py --spec workflows/repository/flash_ladder_kb.yaml … --orchestrator …`.
   The orchestrator tier ran in the **workflow-runner service**: `working_dir: /repo`, repo bind
   `FINOPS_REPO_DIR:/repo:ro`, results rw. Its per-run clone landed at
   `/tmp/agentic-dynamics-runs/run-75e8319533fb/repo` at base `9da3687ef` + the agent's commit
   `136d1c2fc`; the prepared step was written into that clone
   (`.fleet/prepared_steps/generate.a1.json`, `prompt_sha256` verified).

2. **The cell image.** The submit carried no `--image`; the default cell base applied:
   `fleet/base` (built **2026-09-12 22:33**), whose probe shows `ModuleNotFoundError` for
   `chromadb` and `ollama` — the image's stale optional deps ARE the phase's
   `retrieval_leg_errors`.

3. **The cell's working directory.** `launch_broker.build_launch_argv` builds the cell as
   `docker run … <image> <command>` and set **no `-w`**; the image's `WORKDIR` is `/app`; the
   command is relative (`python3 scripts/run_workflow.py …`). The cell therefore executed
   **`/app/scripts/run_workflow.py` — the image's baked copy — not the clone's
   `/repo/scripts/run_workflow.py`**. The clone was mounted at `/repo` and passed as the
   script's `--workdir`, which is why the agent's work landed in the clone while the *code*
   that ran came from the image.

4. **The image copy is mid-evolution (pre `67cd2e988`, 2026-09-13).** It contains
   `prepared_child = True` and copies the prepared payload into the phase
   (`phase["prompt"] = prepared["prompt"]`, "prepared mode is EXACT … never from this child's
   flags, spec, or environment") — **but it does not contain `_run_prepared_child`**, so it
   still runs the engine around the prepared prompt. That is exactly why the phase emitted
   engine-path lines the current clone's prepared-child branch cannot print:
   `admission: gate disarmed…` (`_build_phase_admission`, current line 309 — called at 838,
   after the prepared return at 768), `control: child mode…` (`_control_terminal_write`, current
   line 1753 — called at 1076), and the engine's own `cost: $… ok: …`.

5. **Consequence for the delivery claim.** Under the image copy's prepared mode the prompt the
   adapter executed can only be the prepared payload (augmentation is skipped). The worker's
   own session (`child_session.jsonl`, session `ses_f4967713effewb6VVmYbkp7jUb`, the id the
   phase attempt records) contains the citation from that prompt. So the prepared prompt did
   reach the worker — **through the old wrapping, by image-version forensics**. The current
   prepared-child implementation (`_run_prepared_child`: concrete request, no engine, no
   child-side ledger/gates) was **not** exercised, and no retro artifact alone distinguished
   the paths. That is the review's point, and it stands.

## The repair (this branch)

`build_launch_argv` now pins `-w /repo` — the fixed repo target every mount profile provides —
so cells start in the mounted clone view and execute the clone's code. A test pins the flag.
This also removes the systemic class: *every* fleet cell was running image-baked code up to six
days older than its clone.

## The rerun must additionally assert

- the phase reaches `g_test` (possible once the commit-msg hook installs — the other fix on
  this branch);
- the ledger shows two phases (`generate` ok, `g_test` ok) with `test_executed_success` from
  the test phase;
- no engine-path lines in the phase output, and the child executed the clone revision.
