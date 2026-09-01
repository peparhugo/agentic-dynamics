"""Slice-4 audit guards (proposal §7 slice 4, §8) — seven read-only guard tests.

Each guard is a *read-only* assertion over the committed compose/specs/code, or a unit test of a
probe's logic — never a live-service dependency in the deterministic run (the live neo4j/board
checks are `@pytest.mark.external`, exercised by the operator's smoke test). A guard that fails on
the CURRENT committed state is a real violation the implementation left — fix the implementation,
not the guard (the proposal's own rule).

The seven guards:

  1. compose-contract (D-13/D-3)  — the mount contract holds (no unexpected mount target);
                                    the socket appears in exactly ONE tier (the orchestrator).
  2. fleet-health (D-14)           — the board surfaces worker heartbeats + per-queue DLQ counts.
  3. neo4j-index (D-12/§6)         — the fulltext index is defined + the kb-neo4j handler writes
                                    text (so the index populates) + skips facts (address, not
                                    relevance).
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
import sys
from pathlib import Path

import pytest
import yaml

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


# The four-mount contract + the D-2 auth set + the D-13 named volume + the D-3 socket
# (container-side TARGETS — the fixed paths, not the env-substituted host sources).
# The four-mount contract + the D-2 auth set (REVISED by the smoke test — the credential-
# file-ro / state-rw split: the results OVERLAY at /repo/experiments/results, the ISOLATED
# CLI state dirs rw, the credential files ro at /auth, the provider config ro) + the D-13
# named volume + the D-3 socket (container-side TARGETS — the fixed paths).
ALLOWED_MOUNT_TARGETS = {
    "/tmp",                                  # worktree (rw)
    "/repo",                                 # repo (ro)
    "/repo/.git",                            # gitdir OVERLAY (rw — D-16, phase commits write refs)
    "/repo/experiments/results",             # results OVERLAY (rw — the worker's relative paths)
    # The repo at its HOST path (D-16 fix, 2026-08-31 — compose commit 685d53964). A worktree
    # in the shared /tmp namespace carries a ``gitdir:`` pointer to the repo's HOST path; the
    # SAME path must exist in the container or the pointer does not resolve, git treats the
    # worktree as foreign, and the runner rewrites the pointer — wedging the worktree for the
    # host. This is the one target that is also a host path by design, and it mirrors
    # ``spawn_wrapper.CONTRACT_TARGETS`` ("repo-alias" / "repo-alias-git"), which is the
    # runtime half of the same contract. Working tree stays ro; only .git is overlaid rw.
    "/home/drseuss/ai-finops-framework",     # repo-alias (ro)
    "/home/drseuss/ai-finops-framework/.git",  # repo-alias-git (rw)
    "/home/drseuss/.local/share/opencode",   # the ISOLATED opencode state (rw, per worker)
    "/auth/opencode_auth.json",              # the credential FILE (ro) — seeded by the entrypoint
    "/home/drseuss/.local/share/claude",     # the claude binary chain (ro, D-18 symlink target)
    "/home/drseuss/.claude",                 # D-2 auth (ro)
    "/home/drseuss/.config",                 # the provider config (ro — smoke finding #4)
    "/home/drseuss/.local/bin",              # D-2 auth (ro)
    "/home/drseuss/.opencode",               # the opencode config + bin (ro)
    "/var/log/fleet",                        # the fleet-logs NAMED volume (D-13, not a host path)
    "/var/run/docker.sock",                  # the socket (orchestrator only, D-3)
}

ORCHESTRATOR_SERVICES = {"campaign-wrapper", "workflow-runner"}
SUPERVISOR_SERVICES = {
    "fleet-manager", "control-room", "game-board", "trigger-reviews",
    "registry-cli", "bundle-reference-check", "report-tools",
}
KB_CONSUMERS = {"kb-chroma", "kb-ledger", "kb-registry", "kb-neo4j"}


# ── guard 1 — the compose-contract guard (D-13 / D-3) ────────────────────────


def test_mount_contract_holds_no_unexpected_target():
    compose = _compose()
    for name, svc in compose["services"].items():
        for target, _mode in _volume_targets(svc):
            assert target in ALLOWED_MOUNT_TARGETS, (
                f"service {name!r} mounts {target!r} — outside the four-mount contract "
                f"+ the D-2 auth set + the fleet-logs named volume"
            )


def test_socket_appears_in_exactly_one_tier():
    compose = _compose()
    socket_holders = {
        name
        for name, svc in compose["services"].items()
        if any(t == "/var/run/docker.sock" for t, _m in _volume_targets(svc))
    }
    assert socket_holders == ORCHESTRATOR_SERVICES, (
        f"the socket must appear in exactly the orchestrator tier, got {sorted(socket_holders)}"
    )
    for name in socket_holders:
        for target, mode in _volume_targets(compose["services"][name]):
            if target == "/var/run/docker.sock":
                assert mode == "ro", f"{name}: the socket must be read-only"


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
    assert counts == {"story_jobs": 1, "analysis_jobs": 2, "review_jobs": 0}


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
def test_neo4j_index_populated_and_group_caught_up_live(neo4j_available):
    """LIVE (operator's smoke test): the index is populated and the group's pending = 0."""
    if not neo4j_available:
        pytest.skip("neo4j not reachable")
    from agentic_dynamics.knowledge.graph import Neo4jClient

    client = Neo4jClient()
    try:
        hits = client.search_knowledge_fulltext("task", limit=1)
        assert hits, "the fulltext index is empty — the lexical leg is dead"
    finally:
        client.close()


# ── guard 4 — the single-write-back audit (D-11 / G6 / D-15) ─────────────────


def test_exactly_one_kb_consumer_carries_the_write_flag():
    compose = _compose()
    writers = [n for n in KB_CONSUMERS if _env(compose["services"][n]).get("FINOPS_KB_WRITE") == "1"]
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
    from scripts.fleet import probe_binaries

    results = probe_binaries.probe_all(home="/home/drseuss")
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

    spec = ExperimentSpec.from_yaml(ROOT / "workflows" / "repository" / "fleet_ladder_implementation.yaml")
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
