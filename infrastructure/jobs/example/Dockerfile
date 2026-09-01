# infrastructure/jobs/example/Dockerfile — a per-job image, demonstrating the fleet/job-<name>
# path (p3_base_image_caching). Build with:
#
#   scripts/fleet/build.sh job example
#
# which runs `docker build --cache-from fleet/base -f infrastructure/jobs/example/Dockerfile
# -t fleet/job-example .` — every layer fleet/base already built (the toolchain: apt packages,
# node, the sonar client, the python deps) is reused; ONLY the layers below this line build
# fresh. A real job directory is infrastructure/jobs/<name>/Dockerfile for whatever <name> the
# submit contract's `image: fleet/job-<name>` field references
# (scripts/fleet/spawn_wrapper.py:JOB_IMAGE_PATTERN).
#
# Isolation still applies unchanged (docs/fleet/08_job_image_cache_root.md): this image is the
# PHASE CELL's image (threaded via --cell-image, scripts/run_workflow.py's orchestrator mode —
# never the orchestrator/workflow-runner container itself, which stays fleet/orchestrator so it
# keeps the one socket the ladder grants it). The cell sees only its mounts on fleet-net,
# regardless of which image runs it.
FROM fleet/base

# Custom per-job layers go here — e.g. a pinned tool version or an extra system package this
# job's phase needs that fleet/base does not carry. Nothing here may reintroduce a mount the
# isolation contract forbids (a host port, a host path, a credential file outside the D-2 set) —
# an image only ever RUNS inside the compose mount contract; it cannot grant itself a new one.
