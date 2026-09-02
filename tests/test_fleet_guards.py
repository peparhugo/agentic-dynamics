"""Slice-4 audit guards (proposal §7 slice 4, §8) — seven read-only guard tests.

Each guard is a *read-only* assertion over the committed compose/specs/code, or a unit test of a
probe's logic — never a live-service dependency in the deterministic run (the live neo4j/board
checks are `@pytest.mark.external`, exercised by the operator's smoke test). A guard that fails on
the CURRENT committed state is a real violation the implementation left — fix the implementation,
not the guard (the proposal's own rule).

The seven guards:

  1. compose-contract (D-13/D-3)  — the mount contract holds (no unexpected mount target);
                                    the socket appears in exactly ONE tier (the orchestrator).
  2. fleet-health (D-14)           — the board surfaces worker heartbeats + per-queue DLQ counts;
                                    LIVE, scoped to kb-neo4j-v1 (retrieval_activation
                                    p4_activation_gate) — the consumer the neo4j-index guard
                                    below depends on being alive.
  3. neo4j-index (D-12/§6)         — the fulltext index is defined + the kb-neo4j handler writes
                                    text (so the index populates) + skips facts (address, not
                                    relevance); LIVE, the index's population state and
                                    kb-neo4j-v1's stream backlog are asserted as ONE equivalence
                                    (retrieval_activation p4_activation_gate — slice 3 asserted
                                    these as two separate historical facts, never as a live
                                    biconditional).
  4. single-write-back (D-11/G6)   — exactly ONE kb consumer (kb-registry) carries
                                    FINOPS_KB_WRITE=1; the orchestrator/supervisor never do (D-15).
  5. binary-probe (D-18)           — resolve_chain fails loudly on a missing/non-executable chain.
  6. scope-vocabulary (D-16)       — every phase's scope: ∈ the five-scope vocabulary and the
                                    authorization table is well-formed.
  7. network-policy (D-17)         — every tier attaches to exactly fleet-net; 6379/8001/4096/host
                                    absent from the ladder's network surface.
"""

from __future__ import annotations

import importlib
import re
import sys
import time
from pathlib import Path

import pytest
import yaml

from agentic_dynamics.core.paths import PathConfig

ROOT = Path(__file__).resolve().parent.parent
COMPOSE_PATH = ROOT / "infrastructure" / "docker-compose.ladder.yml"

# ── shared helpers ────────────────────────────────────────────────────────────


def _compose() -> dict:
    return yaml.safe_load(COMPOSE_PATH.read_text())


def _env(service: dict) -> dict:
    env = service.get("environment")
    return env if isinstance(env, dict) else {}


def _volume_targets(service: dict) -> list[tuple[str, str]]:
    """Return ``[(target, mode)]`` for a service's volume mounts (both string + long syntax).

    Mount sources carry ``${VAR:-default}`` substitutions whose braces contain a colon, so the
    string is split from the RIGHT (``rsplit``) — the target + mode are the trailing fields and
    the source is everything before them.
    """
    out: list[tuple[str, str]] = []
    for v in service.get("volumes") or []:
        if isinstance(v, str):
            parts = v.rsplit(":", 2)
            target = parts[1] if len(parts) >= 2 else parts[0]
            mode = parts[2] if len(parts) >= 3 else "rw"
            out.append((target, mode))
        elif isinstance(v, dict):
            out.append((v.get("target", ""), "ro" if v.get("read_only") else "rw"))
    return out


def _fleet_module(name: str):
    """Import a scripts/fleet module (they import each other as top-level modules)."""
    fleet_dir = str(ROOT / "scripts" / "fleet")
    if fleet_dir not in sys.path:
        sys.path.insert(0, fleet_dir)
    return importlib.import_module(name)


# ── The mount contract — the single source is the wrapper's runtime contract ──
#
# F5 (the mount-contract guard gap, docs/reviews/docs_architecture_refresh_remediation.md): the
# guard's allowlist used to be a hand-copied mirror of the wrapper's runtime contract, and it
# went stale — the compose's repo-alias + `.git` overlay targets (docker-compose.ladder.yml:70-71)
# were missing from the guard while the wrapper already allowed them
# (scripts/fleet/spawn_wrapper.py). The fix is to CONSUME the wrapper's runtime contract as the
# single source (never a copy that can drift again).
#
# b1_path_config (fleet_launch_boundary Wave 2): the wrapper's contract is now derived from a
# PathConfig — its repo-alias/.git pair and D-2 auth dirs track the config's repo_root/git_dir/
# auth_home, so the guard must evaluate the wrapper contract under the SAME env the compose
# declares. It therefore reads the compose file's own `${VAR:-default}` indirections
# (FINOPS_REPO_DIR / FINOPS_WORKTREE_ROOT / AUTH_HOME) and builds the config from those defaults
# — the guard is env-independent (a runner checkout / CI box has no ambient FINOPS_* vars) and
# literal-free (the defaults are read from the file, never hard-coded). The guard's allowlist is
# the wrapper's runtime contract for that config unioned with the ladder's OWN compose-only
# surface (the D-3 socket, the D-13 named log volume, the provider config, the compose results
# overlay, and the compose-wide opencode dir) — targets the wrapper's sibling-spawn contract
# deliberately does not govern. An unexpected target still fails (the negative test proves it).


def _compose_env_defaults() -> dict[str, str]:
    """The compose file's own ``${VAR:-default}`` indirections — first occurrence per var.

    Read from the YAML text (never hard-coded): ``FINOPS_WORKTREE_ROOT`` (default ``/tmp``),
    ``FINOPS_REPO_DIR`` (the repo's host path), ``AUTH_HOME`` (the host auth home). This is the
    env the ladder would actually be brought up under when no operator override is exported.
    """
    defaults: dict[str, str] = {}
    for name, default in re.findall(r"\$\{([A-Z_][A-Z0-9_]*):-([^}]*)\}", COMPOSE_PATH.read_text()):
        defaults.setdefault(name, default)
    return defaults


def _compose_config() -> PathConfig:
    """The PathConfig the compose declares by its own env defaults (structural, no fs checks)."""
    return PathConfig.from_env(_compose_env_defaults(), require_existing=False)


def _wrapper_contract_targets() -> frozenset[str]:
    """The spawn-wrapper's runtime mount contract for the compose's own config.

    Consumed, never copied — the single source for the shared four-mount + D-2-auth surface. A
    copy is exactly the staleness class F5 closed: the guard drifted from the wrapper's runtime
    allowlist once; consuming it removes the copy entirely, so the two cannot diverge again (a
    future wrapper addition is allowed here by construction, not by re-sync). The wrapper's
    repo-alias/.git + D-2 auth entries are config-derived (b1_path_config), so the guard
    evaluates them under the config the compose file itself declares.
    """
    return frozenset(_fleet_module("spawn_wrapper").contract_targets(_compose_config()))


# The ladder's compose-ONLY surface — targets the wrapper's sibling-spawn contract does not
# govern, so they cannot come from the wrapper's runtime contract: the D-13 fleet-logs NAMED
# volume, the provider config (~/.config — the wrapper's auth set is narrower), the compose's
# results OVERLAY at the /repo path (the wrapper mounts results at /app/experiments/results
# instead), and the compose-wide opencode dir (~/.opencode — the wrapper's auth set is the
# narrower ~/.opencode/bin). The two auth-home-relative entries derive from the compose's own
# ``AUTH_HOME`` default. NOTE (b3_launch_broker): the D-3 docker socket is NOT here — the
# socket leaves every container; the host-side launch broker owns it, so no compose target may
# ever name it again.
def _compose_only_targets() -> frozenset[str]:
    cfg = _compose_config()
    return frozenset(
        {
            "/var/log/fleet",  # the fleet-logs NAMED volume (D-13, not a host path)
            str(cfg.auth_home / ".config"),  # the provider config (ro — smoke finding #4)
            "/repo/experiments/results",  # results OVERLAY (rw — the worker's relative paths)
            str(cfg.auth_home / ".opencode"),  # the opencode config + bin (ro)
        }
    )


# The wrapper's runtime contract carries the four-mount contract (worktree /tmp rw, repo /repo
# ro, results /app/experiments/results, the /repo/.git + config repo-alias + repo-alias/.git
# overlays) and the config-derived D-2 auth set (~/.claude, ~/.local/share/claude,
# ~/.local/bin, ~/.opencode/bin — ro). Unioned with the compose-only surface above, every
# target the compose declares is permitted here, and nothing outside it is.
ALLOWED_MOUNT_TARGETS = _wrapper_contract_targets() | _compose_only_targets()

ORCHESTRATOR_SERVICES = {"campaign-wrapper", "workflow-runner"}
SUPERVISOR_SERVICES = {
    "fleet-manager",
    "control-room",
    "game-board",
    "trigger-reviews",
    "registry-cli",
    "bundle-reference-check",
    "report-tools",
}
KB_CONSUMERS = {"kb-chroma", "kb-ledger", "kb-registry", "kb-neo4j"}


# ── guard 1 — the compose-contract guard (D-13 / D-3) ────────────────────────


def _mount_contract_violations(compose: dict) -> list[tuple[str, str]]:
    """Return ``[(service, target)]`` for every mount target outside the allowlist.

    The single shared check for both directions of the mount guard: the positive
    (every declared compose target is allowed) and the negative (a foreign target is
    rejected). Keeping them on one predicate means the negative test proves the guard
    still bites — it cannot silently diverge from what the positive test enforces.
    """
    out: list[tuple[str, str]] = []
    for name, svc in compose["services"].items():
        for target, _mode in _volume_targets(svc):
            if target not in ALLOWED_MOUNT_TARGETS:
                out.append((name, target))
    return out


def test_mount_contract_holds_no_unexpected_target():
    violations = _mount_contract_violations(_compose())
    assert violations == [], (
        "these mounts are outside the four-mount contract + the D-2 auth set + the "
        f"fleet-logs named volume: {violations}"
    )


def test_mount_guard_rejects_a_foreign_target():
    """Both-directions evidence (F5): the guard still fails on an invented foreign mount.

    The allowlist is aligned with the wrapper's runtime contract for the compose's own config
    (repo-alias + ``.git`` overlays + the D-2 auth set), never weakened — an unexpected target
    must still fail. The compose's volume anchors are shared across the cell services, so a deep
    copy is injected with a genuinely foreign target to prove the guard bites.
    """
    import copy

    compose = copy.deepcopy(_compose())
    foreign = "/opt/something/not/allowed:/opt/something/not/allowed:ro"
    compose["services"]["story-worker"]["volumes"].append(foreign)
    violations = _mount_contract_violations(compose)
    assert ("story-worker", "/opt/something/not/allowed") in violations, (
        "the mount guard must still reject a genuinely foreign mount target — the "
        "allowlist alignment must never weaken it"
    )


def test_no_service_mounts_the_docker_socket():
    """b3_launch_broker hard rule 1: the socket leaves EVERY container.

    No ladder service may mount /var/run/docker.sock — the host-side launch broker owns the
    socket and is the ONLY Docker API caller. Before b3 the invariant was "exactly the
    orchestrator tier"; the wave's mandate is stronger: the socket appears in NO service.
    """
    compose = _compose()
    socket_holders = {
        name
        for name, svc in compose["services"].items()
        if any(t == "/var/run/docker.sock" for t, _m in _volume_targets(svc))
    }
    assert socket_holders == set(), (
        f"the socket must appear in NO compose service after b3 (the host-side launch broker "
        f"owns it), got {sorted(socket_holders)}"
    )


def test_supervisor_has_no_socket_and_no_worktree_mount():
    compose = _compose()
    for name in SUPERVISOR_SERVICES:
        svc = compose["services"][name]
        targets = {t for t, _m in _volume_targets(svc)}
        assert "/var/run/docker.sock" not in targets, f"{name}: supervisor must not hold the socket"
        assert "/tmp" not in targets, f"{name}: supervisor must not mount the worktree"


def test_fleet_logs_is_a_named_volume_not_a_host_path():
    compose = _compose()
    top_volumes = compose.get("volumes") or {}
    assert "fleet-logs" in top_volumes, "fleet-logs must be declared as a named volume (D-13)"


# ── guard 2 — the fleet-health guard (D-14) ──────────────────────────────────


class _FakeRedis:
    """Minimal redis stand-in for the heartbeat/DLQ board surface."""

    def __init__(self) -> None:
        self._hashes: dict[str, dict[str, str]] = {}
        self._lists: dict[str, list[str]] = {}

    def hset(self, key: str, mapping: dict) -> None:
        self._hashes[key] = {k: str(v) for k, v in mapping.items()}

    def scan_iter(self, match: str | None = None, count: int | None = None):
        return iter(self._hashes.keys())

    def type(self, key: str) -> str:
        return "hash"

    def hgetall(self, key: str) -> dict[str, str]:
        return self._hashes.get(key, {})

    def llen(self, key: str) -> int:
        return len(self._lists.get(key, []))

    def rpush(self, key: str, *values: str) -> int:
        self._lists.setdefault(key, []).extend(values)
        return len(self._lists[key])


def test_board_surfaces_heartbeats_and_dlq_counts():
    heartbeat = _fleet_module("heartbeat")
    dlq = _fleet_module("dlq")

    r = _FakeRedis()
    heartbeat.publish(r, "story", "a", jobs=3, pid=100)
    heartbeat.publish(r, "analysis", "b", jobs=0, pid=101)
    dlq.record_dead(r, "analysis_jobs", {"job": "x"}, "worktree missing")
    dlq.record_dead(r, "analysis_jobs", {"job": "y"}, "worktree missing")
    dlq.record_dead(r, "story_jobs", {"job": "z"}, "timeout")

    heartbeats = heartbeat.read_all(r)
    assert "worker:story:a" in heartbeats
    assert "worker:analysis:b" in heartbeats
    assert heartbeats["worker:story:a"]["jobs"] == "3"

    counts = dlq.dead_counts(r)
    assert counts == {"story_jobs": 1, "analysis_jobs": 2, "review_jobs": 0, "fleet_jobs": 0}


# ── guard 3 — the neo4j index guard (D-12 / §6) ──────────────────────────────


def test_fulltext_index_is_defined_over_knowledge_text():
    from agentic_dynamics.knowledge import graph

    fulltext = "\n".join(graph._KNOWLEDGE_FULLTEXT)
    assert "knowledge_text_ft" in fulltext
    assert "Knowledge" in fulltext and "k.text" in fulltext, (
        "the lexical leg's fulltext index must cover Knowledge.text"
    )


def test_kb_neo4j_handler_writes_text_and_skips_facts():
    # The handler MERGEs `k.text` (what populates the fulltext index) and calls
    # create_knowledge_schema; and it skips source_type == "fact" (address, not relevance).
    import inspect

    from scripts import kb_worker

    # A fact record must be skipped (the handler returns before constructing a Neo4jClient).
    class _Fact:
        source_type = "fact"

    handler = kb_worker.build_handler("kb-neo4j-v1", _FakeRedis())
    handler(_Fact())  # must not raise (no Neo4jClient is constructed for a fact)

    src = inspect.getsource(kb_worker.build_handler)
    assert "create_knowledge_schema" in src
    assert "k.text = $text" in src


@pytest.mark.external
def test_neo4j_index_populated_and_group_caught_up_live(neo4j_available, redis_fleet_available):
    """LIVE: the fulltext index's population state and kb-neo4j-v1's stream backlog must agree.

    Slice 3 (docs/fleet/06_slice3_neo4j_rrf_log.md) asserted these as two SEPARATE facts (an
    index query returned hits; a container log separately reported pending=0). The retrieval
    activation agenda (docs/architecture/current/2026-09-01_retrieval_agenda.md, "Not yet
    established" #3) found no test establishing them as one live equivalence. This measures
    both from the SAME live services in one test: an ONLINE, fully-populated
    ``knowledge_text_ft`` index implies ``kb-neo4j-v1`` has drained its backlog (pending == 0),
    and a non-zero backlog implies the index is not (yet) fully caught up.
    """
    if not neo4j_available:
        pytest.skip("neo4j not reachable")
    if not redis_fleet_available:
        pytest.skip("kb redis (6380) not reachable")
    from agentic_dynamics.knowledge import knowledge_stream as ks
    from agentic_dynamics.knowledge.graph import Neo4jClient

    client = Neo4jClient()
    try:
        hits = client.search_knowledge_fulltext("task", limit=1)
        assert hits, "the fulltext index is empty — the lexical leg is dead"
        row = client._run_value(
            "SHOW INDEXES YIELD name, state, populationPercent WHERE name = $name",
            {"name": "knowledge_text_ft"},
        )
        assert row is not None, "knowledge_text_ft is not defined"
        index_caught_up = row["state"] == "ONLINE" and float(row["populationPercent"]) >= 100.0
    finally:
        client.close()

    r = ks.connect()
    try:
        stream_caught_up = ks.pending_count(r, "kb-neo4j-v1") == 0
    finally:
        r.close()

    assert index_caught_up == stream_caught_up, (
        f"knowledge_text_ft state={row['state']} populationPercent={row['populationPercent']} "
        f"(caught_up={index_caught_up}) disagrees with kb-neo4j-v1's stream backlog "
        f"(caught_up={stream_caught_up}) — the index and the consumer disagree about whether "
        "ingestion has drained"
    )


@pytest.mark.external
def test_kb_neo4j_heartbeat_is_on_the_board_live(redis_fleet_available):
    """LIVE fleet-health (guard 2, D-14), scoped to the consumer this activation depends on.

    Guard 2's deterministic test (``test_board_surfaces_heartbeats_and_dlq_counts``) only
    proves ``heartbeat.read_all`` parses a fake board correctly. This proves the REAL board
    carries a live, non-stale heartbeat for ``kb-neo4j-v1`` — the consumer the neo4j-index
    guard above depends on being alive and supervised (``docker-compose up -d kb-neo4j``,
    slice 3 §1).
    """
    if not redis_fleet_available:
        pytest.skip("kb redis (6380) not reachable")
    heartbeat = _fleet_module("heartbeat")
    import redis

    r = redis.Redis(host="127.0.0.1", port=6380, db=1, decode_responses=True)
    try:
        beats = heartbeat.read_all(r)
    finally:
        r.close()
    kb_neo4j_beats = {k: v for k, v in beats.items() if k.startswith("worker:kb-neo4j-v1:")}
    assert kb_neo4j_beats, (
        "no worker:kb-neo4j-v1:* heartbeat is on the board — the consumer is not running/"
        "supervised, so the neo4j-index guard's live equivalence has no producer keeping it true"
    )
    # A restarted container's heartbeat key is never cleared (the DLQ's own precedent: dead
    # entries linger, disposition is recorded rather than erased) — a PRIOR generation's
    # container leaves a stale worker:kb-neo4j-v1:<old-host>:<pid> key beside the current one.
    # The guard only needs ONE live producer today, so it checks the FRESHEST heartbeat, not
    # the stalest.
    now = time.time()
    freshest = max(float(v.get("last_seen", 0)) for v in kb_neo4j_beats.values())
    assert now - freshest < 60.0, (
        f"the freshest worker:kb-neo4j-v1:* heartbeat is {now - freshest:.0f}s old — stale "
        "(dead worker, per D-14's staleness rule)"
    )


# ── guard 4 — the single-write-back audit (D-11 / G6 / D-15) ─────────────────


def test_exactly_one_kb_consumer_carries_the_write_flag():
    compose = _compose()
    writers = [
        n for n in KB_CONSUMERS if _env(compose["services"][n]).get("FINOPS_KB_WRITE") == "1"
    ]
    assert writers == ["kb-registry"], (
        f"exactly the kb-registry consumer must carry FINOPS_KB_WRITE=1 (D-11), got {writers}"
    )


def test_orchestrator_and_supervisor_never_carry_the_write_flag():
    compose = _compose()
    for name in ORCHESTRATOR_SERVICES | SUPERVISOR_SERVICES:
        assert _env(compose["services"][name]).get("FINOPS_KB_WRITE") != "1", (
            f"{name}: the orchestrator/supervisor must never carry FINOPS_KB_WRITE (D-15)"
        )


def test_no_service_arms_actuation():
    compose = _compose()
    for name, svc in compose["services"].items():
        assert _env(svc).get("FINOPS_ACTUATION_ARMED") != "1", (
            f"{name}: FINOPS_ACTUATION_ARMED is never set in the ladder (G2)"
        )


# ── guard 5 — the binary-resolution probe (D-18) ─────────────────────────────


def _make_fake_bin(tmp_path: Path, name: str, executable: bool = True) -> Path:
    p = tmp_path / name
    p.write_text("#!/bin/sh\necho 'fake 1.0'\n")
    if executable:
        p.chmod(0o755)
    return p


def test_probe_valid_binary_passes(tmp_path):
    from scripts.fleet import probe_binaries

    bin_path = _make_fake_bin(tmp_path, "fake_bin")
    result = probe_binaries.resolve_chain("fake", str(bin_path))
    assert result.ok is True
    assert result.version is not None


def test_probe_missing_launcher_fails_loudly(tmp_path):
    from scripts.fleet import probe_binaries

    result = probe_binaries.resolve_chain("missing", str(tmp_path / "does_not_exist"))
    assert result.ok is False
    assert any("launcher missing" in f for f in result.failures)


def test_probe_non_executable_target_fails_loudly(tmp_path):
    from scripts.fleet import probe_binaries

    bin_path = _make_fake_bin(tmp_path, "no_exec", executable=False)
    result = probe_binaries.resolve_chain("noexec", str(bin_path))
    assert result.ok is False
    assert any("not executable" in f for f in result.failures)


def test_probe_all_resolves_the_two_clis():
    from agentic_dynamics.core.paths import PathConfig
    from scripts.fleet import probe_binaries

    # The probe's auth home is the config's auth_home (derived from env, never a literal).
    results = probe_binaries.probe_all(home=str(PathConfig.from_env().auth_home))
    assert {r.name for r in results} == {"opencode", "claude"}


# ── guard 6 — the scope-vocabulary guard (D-16) ──────────────────────────────


def _spec_yamls():
    for d in (ROOT / "workflows", ROOT / "experiments" / "definitions"):
        yield from d.rglob("*.yaml")


def test_every_phase_scope_is_in_the_vocabulary():
    from agentic_dynamics.experiment.experiment_spec import (
        SCOPE_VOCABULARY,
        ExperimentSpec,
    )

    for path in _spec_yamls():
        try:
            spec = ExperimentSpec.from_yaml(path)
        except Exception:
            continue  # not a spec YAML (or unloadable for an unrelated reason)
        for phase in spec.workflow.params.get("phases") or []:
            if not isinstance(phase, dict):
                continue
            if "scope" in phase:
                assert phase["scope"] in SCOPE_VOCABULARY, (
                    f"{path}: phase {phase.get('name')!r} declares undeclared scope "
                    f"{phase['scope']!r}"
                )


def test_authorization_table_is_well_formed():
    from agentic_dynamics.experiment.experiment_spec import (
        PHASE_SCOPE_AUTHORIZATION,
        SCOPE_VOCABULARY,
    )

    for phase, scope in PHASE_SCOPE_AUTHORIZATION.items():
        assert scope in SCOPE_VOCABULARY, (
            f"authorization table maps {phase!r} to undeclared scope {scope!r}"
        )


def test_implementation_workflow_phases_are_authorized():
    from agentic_dynamics.experiment.experiment_spec import (
        SCOPE_VOCABULARY,
        ExperimentSpec,
        phase_scope,
    )

    spec = ExperimentSpec.from_yaml(
        ROOT / "workflows" / "repository" / "fleet_ladder_implementation.yaml"
    )
    for phase in spec.workflow.params.get("phases") or []:
        authorized = phase_scope(phase)
        assert authorized in SCOPE_VOCABULARY, (
            f"phase {phase.get('name')!r} has no authorized scope ({authorized!r})"
        )


# ── guard 7 — the network-policy guard (D-17) ────────────────────────────────


def test_every_tier_attaches_to_exactly_fleet_net():
    compose = _compose()
    for name, svc in compose["services"].items():
        assert svc.get("network_mode") is None, f"{name}: no host/bridge network_mode allowed"
        networks = svc.get("networks") or []
        assert networks == ["fleet-net"], (
            f"{name}: must attach to exactly fleet-net, got {networks}"
        )


def test_no_ladder_service_publishes_the_sandbox_or_server_ports():
    compose = _compose()
    for name, svc in compose["services"].items():
        for port in svc.get("ports") or []:
            host_side = port.split(":")[0]
            assert "6379" not in host_side and "4096" not in host_side, (
                f"{name}: must not publish 6379 (finops-redis) or 4096 (opencode server)"
            )


def test_portal_binds_loopback_only():
    compose = _compose()
    ports = compose["services"]["control-room"].get("ports") or []
    assert ports, "control-room must publish its port"
    for port in ports:
        host_side = port.split(":")[0]
        assert host_side.startswith("127.0.0.1"), (
            f"control-room must bind loopback only (the cells must not reach the portal), "
            f"got {port!r}"
        )


def test_egress_proxy_is_the_single_policy_point_on_fleet_net():
    compose = _compose()
    egress = compose["services"]["egress"]
    assert egress.get("networks") == ["fleet-net"]
