#!/usr/bin/env python3
"""Render the host-side launch-broker systemd unit from PathConfig (fleet_launch_smoke ws3_stragglers).

The committed unit ``agentic-dynamics-launch-broker.service`` (in this directory) is a
TEMPLATE: its repo-dependent fields (``Environment=REPO=``, ``WorkingDirectory=``, and the
``Documentation=file://`` URL) carry the ``@REPO_ROOT@`` token instead of a host path. The
operator's checkout path was the b1 host-literal the fleet banished from committed code
(``fleet_launch_boundary b1_path_config``): a unit that hard-codes it must be hand-edited
whenever the framework lives elsewhere, and no committed unit may carry the operator's host
path. This generator derives the repo root ONCE from the tier-0 path object
(``agentic_dynamics.core.paths.PathConfig`` — the ``FINOPS_REPO_DIR`` env override, else the
package root of the checkout that runs the generator; never a literal) and renders the
installable unit the operator actually starts.

Install (as the operator, NOT root — replaces the old hand-edit/``cp`` of a host-literal unit):

    python3 infrastructure/gen_launch_broker_service.py
    systemctl --user daemon-reload
    systemctl --user enable --now agentic-dynamics-launch-broker.service

``--output`` overrides the install target (default ``~/.config/systemd/user/
agentic-dynamics-launch-broker.service``); every non-repo field of the unit (the ExecStart, the
``%t`` seam socket, the docker/compose binaries) is left exactly as the template carries it.
The rendered file is a REAL systemd unit; the committed file is its source template and must
never be installed by ``cp`` (a literal ``@REPO_ROOT@`` working directory fails loudly at start
— never a silent misconfiguration). The broker itself additionally self-locates its repo from
its module path at serve time, so a stale or hand-edited unit cannot silently point the daemon
at the wrong checkout.

Pure render (``render_unit``) carries no I/O; tests exercise it hermetically.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from pathlib import Path

#: This file's directory (``infrastructure/``) — the template lives next to the generator.
INFRA_DIR = Path(__file__).resolve().parent
#: The committed unit template — the broker service file this generator renders.
UNIT_TEMPLATE = INFRA_DIR / "agentic-dynamics-launch-broker.service"
#: The installable unit's name (systemd user units live under ~/.config/systemd/user/).
UNIT_NAME = "agentic-dynamics-launch-broker.service"
#: The token the template carries in place of every repo-dependent host path.
REPO_TOKEN = "@REPO_ROOT@"
#: The default install target: the operator's systemd USER unit directory.
DEFAULT_OUTPUT = Path.home() / ".config" / "systemd" / "user" / UNIT_NAME

# Put the repo's src/ on sys.path so the tier-0 path object resolves when this generator is run
# as a script from any cwd (same convention as the scripts under scripts/).
_REPO_ROOT = INFRA_DIR.parent
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

#: The number of repo-dependent fields the template pins (Environment=REPO=, WorkingDirectory=,
#: Documentation=file://) — a template that grows a fourth occurrence is a shape change this
#: generator must not absorb silently.
EXPECTED_TOKEN_COUNT = 3


def derive_repo_root(env: Mapping[str, str] | None = None) -> Path:
    """The repo root the rendered unit points at — derived, never a host literal.

    ``PathConfig.from_env`` resolves ``FINOPS_REPO_DIR`` when set, else the package root of the
    checkout running this generator, and validates the root exists (fail-loud: a bogus repo is
    a refusal, never a render of a wrong path). ``require_existing=False`` is deliberately NOT
    used: the unit must point at a real checkout.
    """
    from agentic_dynamics.core.paths import PathConfig  # noqa: PLC0415 — lazy (leaf import)

    return PathConfig.from_env(env).repo_root


def render_unit(repo_root: Path | str, template_text: str | None = None) -> str:
    """Substitute every ``@REPO_ROOT@`` token in the unit template with ``repo_root``.

    Pins the template shape first: exactly :data:`EXPECTED_TOKEN_COUNT` tokens must be present
    (the Environment=REPO=, WorkingDirectory= and Documentation=file:// fields), so an edit that
    adds or drops a repo-dependent field is a loud failure here, never a silently half-rendered
    unit. ``template_text`` is injectable for tests; the default reads the committed template.
    """
    text = UNIT_TEMPLATE.read_text() if template_text is None else template_text
    if text.count(REPO_TOKEN) != EXPECTED_TOKEN_COUNT:
        raise ValueError(
            f"launch-broker unit template carries {text.count(REPO_TOKEN)} {REPO_TOKEN!r} "
            f"tokens, expected {EXPECTED_TOKEN_COUNT} (Environment=REPO=, WorkingDirectory=, "
            f"Documentation=file://) — a repo-dependent field changed shape; update the "
            f"generator before rendering"
        )
    rendered = text.replace(REPO_TOKEN, str(repo_root))
    assert REPO_TOKEN not in rendered, "every repo token must be substituted"
    return rendered


def install(
    output: Path | str,
    *,
    repo_root: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> Path:
    """Render the unit from ``repo_root`` (derived from PathConfig when None) and write it.

    Creates the target's parent directory (the user systemd dir is typically absent until the
    first user unit is installed). Returns the written path.
    """
    root = Path(repo_root) if repo_root is not None else derive_repo_root(env)
    rendered = render_unit(root)
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(rendered)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="where to write the rendered unit (default: %(default)s)",
    )
    args = parser.parse_args(argv)
    out = install(args.output)
    print(f"[gen-launch-broker] rendered {out} from {UNIT_TEMPLATE.name}")
    print("[gen-launch-broker] next: systemctl --user daemon-reload")
    print(f"[gen-launch-broker]       systemctl --user enable --now {UNIT_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
