"""fb3_stragglers — f4 (the game board's docker usage is documented, not a second untyped
caller) + f6 (no committed prose describes the pre-b3 socket-in-container state)
(fleet_launch_boundary_followups).

The Wave-2 adversarial review recorded two stragglers next to the clone-mount (fb1) and the
host-side broker (fb2):

* **F4** — ``scripts/system_snapshot.py`` ran ``docker ps`` directly, a second Docker API
  caller outside the launch broker. The closure chosen here is the one the wave's hard rule 3
  allows: DOCUMENT it as the broker's ONLY-caller rule's FIRST of two documented benign
  read-only exceptions (a host-side DISPLAY read for the game board's chromadb row — never a
  launch, never a write, never reachable from a cell), not an untyped caller. (The SECOND
  documented exception is the archived one-time sonar-scanner docker run in
  ``scripts/archive/backfill_sonar.py`` — fleet_launch_smoke ws3_stragglers, frozen, never
  re-run; the rule statements below name both.)
* **F6** — committed prose still described the pre-b3 socket-holder state (the orchestrator
  container mounting ``/var/run/docker.sock`` ro). The Containerfile and the ``agent_config``
  sources are corrected to the broker reality; the agent surfaces are regenerated (never
  hand-edited).

VERIFY coverage (the wave's fb3 checklist, both directions):

    (a) system_snapshot's docker usage is documented — grep the call site + its docstring
        (module docstring + the ``_chromadb_docker_ps`` helper docstring), and no second
        untyped docker caller exists in the maintained non-fleet code;
    (b) no committed prose describes the socket-in-container state — grep the Containerfile +
        the agent_config sources (+ the rendered root / opencode / claude surfaces);
    (c) the surfaces regenerate cleanly — ``scripts/_gen_instructions.py --check`` is green
        (asserted here by the positive broker-reality markers on the rendered surfaces; the
        byte-level drift gate lives in tests/test_agent_config_render.py).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parent.parent

SNAPSHOT = ROOT / "scripts" / "system_snapshot.py"
CONTAINERFILE = ROOT / "Containerfile.fleet"
AGENT_CONFIG = ROOT / "agent_config"

#: The marker phrase the f4 documentation uses — module docstring AND the helper's docstring
#: (the ws3_stragglers record made the carve-outs two; both statements name the count).
DOCUMENTED_EXCEPTION_PHRASE = "two documented"
BENIGN_READ_ONLY_PHRASE = "benign read-only exception"

#: The docker invocation list-literal subcommands (a real docker CLI call, not the word
#: "docker" in prose or a keyword vocabulary).
_DOCKER_SUBCOMMANDS = (
    "ps|run|compose|rm|images|exec|pull|build|create|start|stop|inspect|logs|network|volume|info|version"
)
_DOCKER_INVOCATION_RE = re.compile(r'docker",\s*"(' + _DOCKER_SUBCOMMANDS + r")")

#: The stale socket-holder phrases f6 removes. Each asserts the PRE-b3 reality (a container —
#: "the orchestrator" — mounting /var/run/docker.sock ro and being "the ONE socket-holder").
#: Broker-reality prose ("the docker socket is never mounted into any container", "the host-side
#: launch broker is the socket's only home", the removed "socket-holder-era docker-cli install")
#: deliberately does NOT match these patterns, so the grep is one-directional: a match is always
#: stale.
STALE_SOCKET_HOLDER_PHRASES = (
    "ONE socket-holder",
    "one socket-holder",
    "the socket in exactly one tier",
    "socket lives in exactly one tier",
    "mounts /var/run/docker.sock ro",
    "mount /var/run/docker.sock ro",
    "mounts the docker socket (ro)",
    "the container mounts the docker socket",
    "docker socket call",
    "BEFORE the socket call",
)


# ── (a) f4 — system_snapshot's docker usage is documented, never a second untyped caller ──


def _module_docstring(src: str) -> str:
    """The first triple-quoted string in the source (the module docstring), whitespace-
    normalized so a line-wrapped phrase still greps as the phrase."""
    match = re.search(r'"""(.*?)"""', src, re.DOTALL)
    assert match is not None, "no module docstring found"
    return re.sub(r"\s+", " ", match.group(1))


def _helper_docstring(src: str) -> str:
    """The ``_chromadb_docker_ps`` docstring (the text between its ``def`` and its body),
    whitespace-normalized."""
    match = re.search(
        r"def _chromadb_docker_ps\(\) -> str:\n\s+\"\"\"(.*?)\"\"\"", src, re.DOTALL
    )
    assert match is not None, "no _chromadb_docker_ps helper with a docstring found"
    return re.sub(r"\s+", " ", match.group(1))


def test_snapshot_module_docstring_documents_the_docker_exception():
    """fb3 VERIFY (a): the call site's module documents the docker usage as one of the recorded
    benign read-only exceptions to the broker's ONLY-caller rule (now two documented exceptions
    — the other: the archived one-time backfill_sonar docker run, ws3_stragglers) — never an
    untyped caller."""
    doc = _module_docstring(SNAPSHOT.read_text(encoding="utf-8"))
    assert DOCUMENTED_EXCEPTION_PHRASE in doc, (
        "system_snapshot's module docstring must name the docker ps as a documented exception "
        "to the ONLY-caller rule"
    )
    assert BENIGN_READ_ONLY_PHRASE in doc
    assert "scripts/fleet/launch_broker.py" in doc


def test_snapshot_docker_call_site_has_a_documenting_docstring():
    """fb3 VERIFY (a): the docker call site is a named helper whose docstring documents the
    exception (a grep of the call site + its docstring resolves the f4 closure)."""
    src = SNAPSHOT.read_text(encoding="utf-8")
    helper_doc = _helper_docstring(src)
    assert DOCUMENTED_EXCEPTION_PHRASE in helper_doc
    assert BENIGN_READ_ONLY_PHRASE in helper_doc
    assert "docker" in helper_doc and "chromadb" in helper_doc


def test_snapshot_has_exactly_one_docker_invocation_site():
    """fb3 VERIFY (a), negative direction: the ONLY ``docker`` invocation literal in the whole
    script lives inside the documented helper — no second (untyped) caller can appear."""
    src = SNAPSHOT.read_text(encoding="utf-8")
    assert src.count('"docker"') == 1, (
        "system_snapshot must contain exactly one \"docker\" invocation literal (the "
        "documented _chromadb_docker_ps helper)"
    )
    # …and that single literal sits in the documented helper, never in main().
    head, _tail = src.split("def main()", 1)
    assert '"docker"' in head, "the docker invocation must live in a helper, not in main()"
    assert "_chromadb_docker_ps()" in _tail, "main() must call the documented helper"


def test_no_second_untyped_docker_caller_in_maintained_non_fleet_code():
    """fb3 hard rule 3 ('No second untyped caller appears'): across the maintained top-level
    scripts and the src planes, the ONLY docker invocation-literal site is the documented
    system_snapshot exception (the broker lives under scripts/fleet/; archived one-time scripts
    are immutable historical material)."""
    offenders: list[str] = []
    for base in (ROOT / "scripts", ROOT / "src"):
        for path in sorted(base.rglob("*.py")):
            rel = path.relative_to(ROOT)
            if rel.parts[:2] in (("scripts", "fleet"), ("scripts", "archive")):
                continue
            if _DOCKER_INVOCATION_RE.search(path.read_text(encoding="utf-8")):
                offenders.append(str(rel))
    assert offenders == ["scripts/system_snapshot.py"], (
        "the only docker invocation literal in the maintained non-fleet code must be the "
        f"documented exception (system_snapshot.py); got {offenders}"
    )


# ── (b) f6 — no committed prose describes the socket-in-container state ─────


def _f6_surfaces() -> list[tuple[str, str]]:
    """The f6 grep surface: the Containerfile + the agent_config sources + every rendered root/
    opencode/claude markdown surface (the surfaces are derived from agent_config — regenerated,
    never hand-edited, so a stale render here is as much a finding as a stale source)."""
    out: list[tuple[str, str]] = [(str(CONTAINERFILE.relative_to(ROOT)), CONTAINERFILE.read_text(encoding="utf-8"))]
    for base, glob in (
        (AGENT_CONFIG, "*.md"),
        (ROOT, "AGENTS.md"),
        (ROOT, "CLAUDE.md"),
        (ROOT / ".opencode", "**/*.md"),
        (ROOT / ".claude", "**/*.md"),
    ):
        for path in sorted(base.glob(glob)):
            if path.is_file():
                out.append((str(path.relative_to(ROOT)), path.read_text(encoding="utf-8")))
    return out


def test_containerfile_describes_no_socket_holder_state():
    """fb3 VERIFY (b): the Containerfile no longer describes the pre-b3 socket-in-container
    reality (the orchestrator as the socket-holder mounting /var/run/docker.sock ro)."""
    text = CONTAINERFILE.read_text(encoding="utf-8")
    for phrase in STALE_SOCKET_HOLDER_PHRASES:
        assert phrase not in text, f"Containerfile.fleet still carries stale phrase {phrase!r}"
    # Positive direction: it describes the broker reality instead — and no longer names the
    # socket path at all (the socket-holder era named it; the broker era names the host unit).
    assert "host-side launch broker" in text
    assert "docker socket" in text
    assert "/var/run/docker.sock" not in text


def test_agent_config_sources_describe_no_socket_holder_state():
    """fb3 VERIFY (b): every agent_config source (the neutral instruction tree) is free of the
    pre-b3 socket-holder phrasing."""
    for rel, text in _f6_surfaces():
        if not rel.startswith("agent_config/"):
            continue
        for phrase in STALE_SOCKET_HOLDER_PHRASES:
            assert phrase not in text, f"{rel}: stale phrase {phrase!r} remains in a source"


def test_rendered_surfaces_describe_no_socket_holder_state():
    """fb3 VERIFY (b) on the derived surfaces: AGENTS.md / CLAUDE.md / the .opencode and .claude
    trees carry no stale socket-holder prose (they are regenerated from agent_config, so this
    also proves the sources were regenerated rather than hand-edited into submission)."""
    stale_in: dict[str, list[str]] = {}
    for rel, text in _f6_surfaces():
        if rel.startswith("agent_config/"):
            continue
        for phrase in STALE_SOCKET_HOLDER_PHRASES:
            if phrase in text:
                stale_in.setdefault(rel, []).append(phrase)
    assert stale_in == {}, f"rendered surfaces still carry stale socket-holder prose: {stale_in}"


def test_rendered_surfaces_carry_the_broker_reality():
    """fb3 VERIFY (c), positive direction on the surfaces that f6 edits: the operational-notes
    and run-workflow surfaces describe the broker seam reality (the host-side broker performs
    the docker call; no container mounts the docker socket) — the text a socket-holder revert
    would delete."""
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "emits every launch as a typed request over the unix-socket seam" in agents
    assert "the docker socket's only home" in agents
    skill = (ROOT / ".opencode" / "skills" / "run-workflow" / "SKILL.md").read_text(encoding="utf-8")
    assert "No container mounts the docker socket" in skill
    assert "host broker's unix-socket seam" in skill
    claude_skill = (ROOT / ".claude" / "skills" / "run-workflow" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert claude_skill == skill, "the two platform skill surfaces must render identically"
