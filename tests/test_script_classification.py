"""Script-classification guard (critique rec 5).

The classification manifest in ``scripts/CONTEXT.md`` places every script under ``scripts/`` in
exactly one bucket — maintained command / historical analysis / one-time migration / deprecated.
This test parses that manifest and asserts it covers the real ``scripts/`` directory with zero
orphans, and that every maintained command is reachable from the Stage 3 CLI
(``agentic_dynamics.cli``) — no maintained command may live only as a loose script.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
CONTEXT = SCRIPTS_DIR / "CONTEXT.md"

BUCKETS = ("maintained", "historical", "one-time")

_START = "<!-- scripts-classification: start -->"
_END = "<!-- scripts-classification: end -->"


def _parse_manifest() -> dict[str, set[str]]:
    """Parse the ``bucket: <script>…`` lines between the manifest markers in CONTEXT.md."""
    text = CONTEXT.read_text(encoding="utf-8")
    if _START not in text or _END not in text:
        raise AssertionError("scripts/CONTEXT.md is missing the classification markers")
    body = text.split(_START, 1)[1].split(_END, 1)[0]
    manifest: dict[str, set[str]] = {b: set() for b in BUCKETS}
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "-")):
            continue
        for bucket in BUCKETS:
            if line.startswith(bucket + ":"):
                manifest[bucket] |= set(line[len(bucket) + 1:].split())
    return manifest


def test_manifest_covers_every_script_with_zero_orphans():
    """Every ``scripts/**/*.py`` (minus the ``_bootstrap.py`` helper) is in exactly one bucket.

    The ``one-time`` bucket lives under ``scripts/archive/``; the rest at the top of ``scripts/``.
    """
    actual = {p.name for p in SCRIPTS_DIR.rglob("*.py")} - {"_bootstrap.py"}
    manifest = _parse_manifest()
    classified = set().union(*manifest.values())
    assert classified == actual, (
        f"orphans (on disk, unclassified): {sorted(actual - classified)}; "
        f"extras (classified, not on disk): {sorted(classified - actual)}"
    )
    # No script may appear in two buckets.
    seen: set[str] = set()
    for bucket in BUCKETS:
        overlap = seen & manifest[bucket]
        assert not overlap, f"scripts in multiple buckets: {sorted(overlap)}"
        seen |= manifest[bucket]


def test_every_maintained_command_is_cli_reachable():
    """No maintained command lives only as a loose script (rec 5)."""
    from agentic_dynamics.cli import _COMMANDS

    # `registry.py` is dispatched by a special case (query|show|lineage), not a static prefix.
    cli_scripts = set(_COMMANDS.values()) | {"registry.py"}
    manifest = _parse_manifest()
    unreachable = manifest["maintained"] - cli_scripts
    assert not unreachable, f"maintained scripts absent from the CLI: {sorted(unreachable)}"
