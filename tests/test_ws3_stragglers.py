"""ws3_stragglers (fleet_launch_smoke) — close the loose docker callers.

The smoke wave's straggler closures (fleet_launch_smoke ws3_stragglers), both recorded
stragglers the wave's pin named next to the ws1/ws2 wiring:

    (a) ``scripts/archive/backfill_sonar.py`` ran a bare ``docker run`` (its :110 argv head) —
        a loose docker caller outside the broker's closed typed seam. The closure chosen is the
        wave's DOCUMENTED branch (routing an archived one-time migration through the seam would
        widen the seam's verb vocabulary for a frozen, never re-run script): the module
        docstring records it as the broker's ONLY-caller rule's SECOND documented benign
        read-only exception (alongside ``system_snapshot.py``'s read-only ``docker ps``, fb3
        f4), with the reason, and its code-dir mount is now read-only so the "read-only"
        record is literally true.
    (b) the launch-broker systemd unit embedded the operator's host checkout path
        (``/home/<user>/ai-finops-framework``) — a b1 host-literal a committed unit must not
        carry. The committed ``infrastructure/agentic-dynamics-launch-broker.service`` is now a
        TEMPLATE whose three repo-dependent fields carry a token, and
        ``infrastructure/gen_launch_broker_service.py`` renders the installable unit from the
        tier-0 ``PathConfig`` (never a literal).

VERIFY coverage (the wave's ws3 checklist, both directions):

    (a) backfill_sonar's docker usage is broker-routed OR documented (grep + its docstring);
    (b) the broker service file carries no host literal (grep the unit content) — and the
        values it installs with are PathConfig-derived, proven by the render + install tests.

Hermetic: no docker, no Redis, no subprocess — pure file greps + a pure render.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_INFRA_DIR = _ROOT / "infrastructure"
if str(_INFRA_DIR) not in sys.path:
    sys.path.insert(0, str(_INFRA_DIR))

import gen_launch_broker_service as gen  # noqa: E402

from agentic_dynamics.core.paths import PathConfig  # noqa: E402

_BACKFILL_SONAR = _ROOT / "scripts" / "archive" / "backfill_sonar.py"
_UNIT_FILE = _INFRA_DIR / "agentic-dynamics-launch-broker.service"


# ── (a) backfill_sonar's docker usage: broker-routed OR documented ───────────


def test_backfill_sonar_still_has_the_docker_run_call():
    """The loose caller is real (the preregistration edge): the archived script runs docker."""
    text = _BACKFILL_SONAR.read_text()
    assert '"docker", "run"' in text, "backfill_sonar's docker run argv must still exist"
    assert "subprocess.run(cmd" in text


def test_backfill_sonar_docker_usage_is_documented_not_broker_routed():
    """(a) the DOCUMENTED branch was chosen: the archived script imports no broker seam client
    (not routed), and its docstring records the exception + the reason (grep + docstring)."""
    text = _BACKFILL_SONAR.read_text()
    # The not-routed branch: no seam import anywhere in the archived script.
    assert "broker_client" not in text, "the archived script is documented, not broker-routed"
    assert "BrokerClient" not in text
    # The recorded exception, named as the SECOND documented benign read-only exception, with
    # the other carve-out (system_snapshot's docker ps) and the reason (archive = one-time).
    doc = text.split('"""', 2)[1]
    assert "ONLY-caller rule's SECOND documented benign read-only exception" in doc
    assert "scripts/system_snapshot.py" in doc, "the first documented exception is named"
    assert "RECORDED, not routed" in doc
    assert "IMMUTABLE HISTORICAL MATERIAL" in doc, "the archive/ one-time reason is recorded"
    # The call site points at the docstring record.
    assert "see the module docstring" in text


def test_backfill_sonar_code_dir_mount_is_read_only():
    """The record says 'benign READ-ONLY exception' — make it literally true: the code
    directory the scanner reads is mounted :ro (a read-only source, never a write into the
    worktree the archive stores)."""
    text = _BACKFILL_SONAR.read_text()
    assert 'f"{code_dir}:/usr/src:ro"' in text, "the sonar-scanner code mount must be :ro"


def test_backfill_sonar_lives_in_the_archived_one_time_bucket():
    """The 'never re-run' half of the reason is structural: the file sits in scripts/archive/
    (the one-time bucket per scripts/CONTEXT.md), not in any live runtime path."""
    assert _BACKFILL_SONAR.is_file()
    assert _BACKFILL_SONAR.parent.name == "archive"


# ── (b) the broker service file carries no host literal ─────────────────────


def test_launch_broker_service_unit_carries_no_host_literal():
    """(b) grep the unit content: the operator's host checkout path appears NOWHERE — no /home
    user prefix, no repo-basename literal. The repo-dependent fields carry the render token."""
    text = _UNIT_FILE.read_text()
    assert "/home/" not in text, "no host /home literal may live in the committed unit"
    assert "drseuss" not in text, "no host-user literal may live in the committed unit"
    assert "ai-finops-framework" not in text, "no repo-basename literal may live in the unit"
    # The repo-dependent fields are the token, not a path — the PathConfig-derived shape.
    assert "Environment=REPO=@REPO_ROOT@" in text
    assert "WorkingDirectory=@REPO_ROOT@" in text
    assert "Documentation=file://@REPO_ROOT@/" in text
    # The fb2 continuity surface is untouched: the unit still names the broker module + seam.
    assert "scripts/fleet/launch_broker.py" in text
    assert "ExecStart=" in text
    assert "--socket" in text
    assert "launch-broker.sock" in text


def test_launch_broker_service_template_pins_exactly_the_repo_fields():
    """The template carries EXACTLY the token count the generator pins (Environment=REPO=,
    WorkingDirectory=, Documentation=file://) — a fourth repo-dependent field is a shape change
    the render refuses rather than absorbs silently."""
    text = _UNIT_FILE.read_text()
    assert text.count(gen.REPO_TOKEN) == gen.EXPECTED_TOKEN_COUNT


# ── (b) the installed values are PathConfig-derived (the render, both directions) ─


def test_unit_render_substitutes_repo_root_into_the_repo_fields():
    """Positive direction: render_unit replaces every token with the given repo root — the
    Environment=REPO=, WorkingDirectory= and Documentation fields carry the derived path, the
    ExecStart/seam surface is untouched, and no token survives the render."""
    root = "/srv/agentic-dynamics"
    rendered = gen.render_unit(root)
    assert gen.REPO_TOKEN not in rendered
    assert f"WorkingDirectory={root}" in rendered
    assert f"Environment=REPO={root}" in rendered
    assert (
        f"Documentation=file://{root}/workflows/repository/"
        "fleet_launch_boundary_followups.yaml" in rendered
    )
    exec_start = next(
        line for line in rendered.splitlines() if line.startswith("ExecStart=")
    )
    assert "python3" in exec_start
    assert "launch_broker.py serve" in exec_start
    assert "--socket" in exec_start


def test_unit_render_refuses_a_template_missing_tokens():
    """Fail-loud: a template whose repo fields no longer carry the tokens is refused, never
    silently half-rendered (a field that lost its token would install a stale empty value)."""
    with pytest.raises(ValueError, match="tokens, expected"):
        gen.render_unit("/srv/agentic-dynamics", template_text="[Unit]\nNo repo fields here\n")


def test_generator_install_derives_repo_root_from_pathconfig(monkeypatch, tmp_path):
    """Positive direction, end to end: install() derives the repo root from PathConfig (the
    FINOPS_REPO_DIR env override — the same derivation the fleet operates under), renders the
    unit with it, and writes it to the requested output. No host literal anywhere."""
    repo = tmp_path / "checkout"
    (repo / ".git").mkdir(parents=True)
    out = tmp_path / "systemd" / "user" / gen.UNIT_NAME
    monkeypatch.setenv("FINOPS_REPO_DIR", str(repo))

    written = gen.install(out)

    assert written == out and out.is_file()
    rendered = out.read_text()
    assert f"WorkingDirectory={repo}" in rendered
    assert f"Environment=REPO={repo}" in rendered
    assert gen.REPO_TOKEN not in rendered
    # The value IS the PathConfig derivation under the same env — never a hardcoded path.
    cfg = PathConfig.from_env({"FINOPS_REPO_DIR": str(repo)})
    assert str(cfg.repo_root) == str(repo)
    assert f"WorkingDirectory={cfg.repo_root}" in rendered


def test_generator_default_output_is_the_user_systemd_unit_dir():
    """The install target defaults to the operator's systemd USER unit directory — the same
    location the unit's own install instructions document."""
    rel = os.path.join(".config", "systemd", "user", gen.UNIT_NAME)
    assert str(gen.DEFAULT_OUTPUT).endswith(rel), gen.DEFAULT_OUTPUT
    assert gen.DEFAULT_OUTPUT.parent.is_absolute()
