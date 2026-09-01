---
status: accepted
---

# Fleet-ladder p3 — the base image as the cache root + the per-job image path

**Status: PASS · Date: 2026-09-01 · Role: `fleet_job_submission` p3_base_image_caching.**
Makes `fleet/base` the caching-friendly floor every image builds on, adds the per-job image
path (`fleet/job-<name>`, built FROM `fleet/base`), threads an optional `image` field through
the submit contract to the phase-cell spawn, and documents the isolation contract the whole
ladder — base image, per-job image, or otherwise — never gets to loosen.

## 0. Verdict

**PASS.** `fleet/base` rebuilds hit cache on every toolchain layer (apt packages, the sonar
client, the python deps) for a repo-only change (verified live: `docker build` twice, the
second after touching a file outside `src/`/`pyproject.toml` — steps 1-10 `Using cache`, only
step 11 onward, the actual changed `COPY`, rebuilds). `docker build --cache-from fleet/base`
against `infrastructure/jobs/example/Dockerfile` (`FROM fleet/base`) built `fleet/job-example`
reusing every fleet/base layer. `docker-compose -f infrastructure/docker-compose.ladder.yml
config` validates. `tests/test_fleet_guards.py` (22 tests) and the extended
`tests/test_spawn_wrapper.py` / `tests/test_fleet_manager.py` submit suites are green.

## 1. The cache-root ordering (`Containerfile.fleet`)

The `base` target's layer order is now, in cache-cost order:

```
apt-get (system toolchain)  →  sonar client (baked, staged by build.sh)
  →  pyproject.toml  →  RUN pip install (stub package, deps only)
    →  COPY src/ (the real source)  →  COPY scripts/ apps/ conventions/ experiments/*
```

The deps-install `RUN` step (`pip install -e ".[neo4j,admin]"`) runs against `pyproject.toml`
plus an EMPTY stub package (`mkdir -p src/agentic_dynamics && touch
src/agentic_dynamics/__init__.py`) — enough for setuptools' src-layout auto-discovery
(`[tool.setuptools.packages.find] where=["src"]`) to register the editable link and pull every
declared dependency, with no repo source present yet. The REAL `src/` lands in the next layer;
pip's default (lenient) editable-install mode adds `src/` to `sys.path` via a `.pth` file rather
than baking a fixed package list at install time, so every subpackage under `src/` resolves
through normal import machinery with no reinstall required — verified live: `docker run --rm -e
FLEET_SKIP_PROBE=1 fleet/base python3 -c "import agentic_dynamics; from
agentic_dynamics.{core,measurement,experiment,adapters,control} import ..."` succeeds against
the real (non-stub) tree.

**Consequence:** a change under `scripts/`, `apps/`, `conventions/`, or the baked `experiments/`
subdirs never re-triggers `apt-get` or `pip install` — only the cheap `COPY` layers from that
point on rebuild. A change under `src/` or `pyproject.toml` still invalidates the deps layer
(unavoidable — that's where the dependency list itself, and the code pip's build backend reads
to construct the editable link, actually live), but that's the correct behavior for THIS repo's
build, not a "toolchain rebuild" — `apt-get`/the sonar stage stay cached even then.

## 2. The per-job image path

`fleet/job-<name>` — built with `scripts/fleet/build.sh job <name>`, which runs `docker build
--cache-from fleet/base -f infrastructure/jobs/<name>/Dockerfile -t fleet/job-<name> .`. The
Dockerfile is `FROM fleet/base` plus whatever custom layers that job needs (an extra system
package, a pinned tool version) — never a re-declaration of the toolchain. A worked example
lives at `infrastructure/jobs/example/Dockerfile` (built live: `Successfully built` in under a
second, every layer reused from `fleet/base`).

The submit contract's optional `image` field (`scripts/fleet/spawn_wrapper.py:
JOB_IMAGE_PATTERN`, `validate_submit_request`'s step 8) accepts ONLY the `fleet/job-<name>`
namespace — never a bare override of `fleet/base`/`fleet/orchestrator`/`fleet/supervisor` (the
ladder's own tiers) and never a third-party image. `fleet_manager submit --image
fleet/job-<name>` LPUSHes it; `build_submit_argv` turns a validated `image` into
`--cell-image fleet/job-<name>` on the `docker compose run ... workflow-runner python3
scripts/run_workflow.py --orchestrator ...` invocation; `run_workflow.py`'s `_run_orchestrator`
threads `--cell-image` to `spawn_wrapper.spawn_sibling(..., image=args.cell_image)`. This
changes which image the spec's **phase cells** run — never the `workflow-runner`/orchestrator
container itself, which always stays `fleet/orchestrator` (the one socket-holder needs the
docker CLI + the spawn wrapper; a job image built off bare `fleet/base` carries neither, so it
could never legally hold the socket even if named there — the namespace restriction is the
belt, this is the suspenders).

## 3. The isolation contract (holds regardless of which image runs)

The docker layer exists for **isolation**, not coordination — no submit, no per-job image, and
no future addition to either may change what a cell can reach. Concretely, for ANY image built
off `fleet/base` (bare `fleet/base` itself, `fleet/orchestrator`, `fleet/job-<name>`, …):

- **Sees only its declared mounts, on `fleet-net`.** `infrastructure/docker-compose.ladder.yml`'s
  `x-ladder-mounts` (cells) / `x-orchestrator-mounts` (the one socket tier) / `x-supervisor-mounts`
  are the enforcement point: the worktree (rw), the results dir (rw), the repo (ro), and the D-2
  auth set (the CLI bins + credential/config dirs, ro). Nothing outside that list is ever
  mounted — `tests/test_fleet_guards.py:test_mount_contract_holds_no_unexpected_target` asserts
  it against the committed compose file, not a live probe.
- **Host services are never reachable.** The story-agent Redis on 6379 is a DIFFERENT Redis
  instance from the ladder's own `finops-queue` (which is on fleet-net at its OWN internal
  6379 — the two are not the same service; AGENTS.md's two-instance rule) and is never attached
  to `fleet-net` at all — there is no network path from inside a cell to the host's 6379,
  regardless of image. The host filesystem beyond the four mount targets, and host credentials
  outside the D-2 auth set, are equally unreachable — a cell's filesystem view is exactly what
  `docker run -v ...` declared, nothing an image's own Dockerfile can expand (an image can add
  packages; it cannot add a mount to itself).
- **The socket appears in exactly one tier.** `/var/run/docker.sock` is ro and ONLY on the
  orchestrator tier (`test_socket_appears_in_exactly_one_tier`); a `fleet/job-<name>` image
  never mounts it — the per-job path only ever reaches the PHASE-cell tier, which was never a
  socket holder to begin with.
- **No orchestrator lock.** Per the spec's hard rule 4, concurrent submits (with or without a
  custom image) are never refused for "another job is already running" — refusal is always
  about validity (an out-of-namespace image, an unlisted model, a host-service workdir), never
  about concurrency.

## 4. Rollback

`Containerfile.fleet`, `scripts/fleet/build.sh`, `infrastructure/jobs/example/Dockerfile`,
`scripts/fleet/spawn_wrapper.py`, `scripts/run_workflow.py`, `scripts/fleet/fleet_manager.py`,
and the two extended test files are all this phase touched — reverting the commit reverts the
image cache-root ordering and the per-job image path together; nothing else depends on them yet
(the `image` field is optional everywhere it was added).

## LOG

**PASS.** `fleet/base`'s layer order puts the toolchain (apt, the sonar client, python deps)
strictly before any repo source — verified live with two real `docker build` runs (cache hit
through step 10, bust only from the touched file's `COPY` onward). The per-job image path
(`scripts/fleet/build.sh job <name>`, `infrastructure/jobs/<name>/Dockerfile` FROM `fleet/base`,
tagged `fleet/job-<name>`) built live with full cache reuse via `--cache-from fleet/base`. The
submit contract's new `image` field is validated to the `fleet/job-<name>` namespace only and
threaded to the phase-cell spawn as `--cell-image`, never touching the orchestrator's own
image. `docker-compose config` validates; the mount-contract guard suite
(`tests/test_fleet_guards.py`) and the extended submit tests
(`tests/test_spawn_wrapper.py`, `tests/test_fleet_manager.py`) are green. Committed.
