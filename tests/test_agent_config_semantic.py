"""Semantic guard over the ``agent_config/`` instruction tree (semantic-integrity review item 6).

The repair release's ``test_stale_path_guard.py`` proves that no accepted doc *names* a retired
path family (``src/instrument/``, ``admin/server.py``, ``code_reviews/…``). That guard is
syntactic — it rejects a fixed list of retired strings. This guard upgrades the check to
**semantic**: for every file under ``agent_config/**`` (agents, skills, commands, rules,
conventions, mental-model) it verifies that the prose refers to things that actually exist and
uses only the current vocabulary.

The seven concerns, one assertion each (a failure prints the full violation set):

1. **referenced repo paths exist** — backticked ``src|scripts|apps|docs|workflows|experiments|…``
   paths (and plane shorthand like ``measurement/perturb.py``) resolve to a real file.
2. **import examples resolve** — ``from agentic_dynamics… import …`` (and ``python -m …``)
   name a real module under ``src/``.
3. **CLI commands exist** — a two-word ``agentic-dynamics <verb> <noun>`` maps to a command in
   ``agentic_dynamics.cli._COMMANDS`` (plus the registry / ``analyze lab`` special cases).
4. **named scripts exist** — ``scripts/<name>.<ext>`` resolves.
5. **retired package imports are absent** — ``from instrument …`` / ``import instrument`` /
   ``instrument.<attr>`` never appear (the package is ``agentic_dynamics``).
6. **retired taxonomy + sources are absent** — the old ``SEMANTIC``/``MANIFOLD`` operator
   taxonomy (replaced by the three ``PERTURBATION_CLASSES``) and the retired
   ``_results_summary.json`` corpus (replaced by the canonical registry resolver) never appear
   except in explicit "retired/quarantined/historical" framing.
7. **no hard-coded counts** — no ``(NNNL)`` line counts, ``NNN lines``, or module/script/file
   counts (they drift; the authoritative counts live in ``scripts/CONTEXT.md``, the lab
   manifest, and the tree itself).

Placeholders (``<name>``), shell variables (``$ARGUMENTS``), globs (``*``), URLs (``http://…``),
and absolute paths (``/tmp/…``) are excluded by construction from the path/script checks.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from agentic_dynamics import cli

ROOT = Path(__file__).resolve().parent.parent
AGENT_CONFIG = ROOT / "agent_config"

#: Repo top-level directories a backticked path may start from (resolved relative to ROOT).
_TOP_DIRS: tuple[str, ...] = (
    "src/",
    "scripts/",
    "apps/",
    "docs/",
    "workflows/",
    "experiments/",
    "tests/",
    "conventions/",
    "infrastructure/",
    "agent_config/",
    ".opencode/",
    ".claude/",
)

#: The eight plane names — shorthand paths like ``measurement/perturb.py`` resolve under
#: ``src/agentic_dynamics/`` (see ARCHITECTURE.md §1).
_PLANES: tuple[str, ...] = (
    "core",
    "experiment",
    "measurement",
    "runtime",
    "adapters",
    "knowledge",
    "control",
    "reporting",
)

#: A trailing ``:NN`` / ``:NN-MM`` file:line citation (provenance, not a path component).
_LINE_REF = re.compile(r":\d+(?:-\d+)?$")

#: Backticked inline-code spans (the canonical way agent_config cites a path).
_BACKTICK = re.compile(r"`([^`\n]+)`")

#: ``from X import …`` / ``import X`` / ``python -m X`` module references.
_IMPORT = re.compile(
    r"^\s*(?:from\s+([\w.]+)\s+import\b|import\s+([\w.]+)|python3?\s+-m\s+([\w.]+))", re.M
)

#: Retired ``instrument`` package references (the current package is ``agentic_dynamics``).
_RETIRED_IMPORT = re.compile(
    r"\b(?:from\s+instrument\b|import\s+instrument\b|instrument\.[a-zA-Z_])"
)

#: The retired SEMANTIC/MANIFOLD operator taxonomy (replaced by PERTURBATION_CLASSES).
_RETIRED_TAXONOMY = re.compile(r"\b(?:SEMANTIC|MANIFOLD)\b")

#: Retired data corpus — must only appear in retired/quarantine/historical framing.
_RETIRED_SUMMARY = re.compile(r"_results_summary\.json")
_RETIRED_FRAME = re.compile(
    r"retired|quarantin|legacy|historical|no longer|not a (?:live|build|publication)|never"
)

#: Hard-coded module/line/file counts (drift-prone; see module docstring).
_COUNT = re.compile(
    r"\(\d+L\)"  # (330L)
    r"|\b\d+\s+lines?\b"  # 1396 lines / 1 line
    r"|\b\d+\s+(?:scripts|files|modules|commands)\b"  # 73 scripts / 71 files / 46 modules
    r"|\b\d+\s+(?:active\s+)?labs?\b"  # 19 active labs / 20 lab books
    r"|\b\d+\s+total\b"  # 34 total
)

#: ``scripts/<name>.<ext>`` references.
_SCRIPT = re.compile(r"\bscripts/([A-Za-z0-9_]+)\.(py|sh|md)\b")

#: ``agentic-dynamics <verb> <noun>`` (two subcommand words).
_CLI = re.compile(r"agentic-dynamics\s+([a-z][a-z-]*)\s+([a-z][a-z-]*)")


def _files() -> list[Path]:
    """Every markdown file under ``agent_config/`` (the neutral source the renderers project)."""
    return sorted(AGENT_CONFIG.rglob("*.md"))


def _is_path_candidate(token: str) -> bool:
    """True when a backticked token looks like a repo path we should resolve."""
    if not token or any(c in token for c in "<>$*{}"):
        return False
    if " " in token or token.startswith(("http://", "https://", "file://", "/", "~", "-", "#")):
        return False
    token = _LINE_REF.sub("", token)
    if token.startswith(_TOP_DIRS):
        return True
    return token.startswith(tuple(p + "/" for p in _PLANES)) and token.endswith(".py")


def _path_exists(token: str) -> bool:
    """Resolve a path candidate against the repo root and the package root."""
    token = _LINE_REF.sub("", token)
    for base in (ROOT, ROOT / "src" / "agentic_dynamics"):
        if (base / token).exists():
            return True
    return False


def _module_exists(module: str) -> bool:
    """True when a dotted ``agentic_dynamics…`` module resolves to a real file."""
    rel = module.replace(".", "/")
    return (ROOT / "src" / f"{rel}.py").exists() or (ROOT / "src" / f"{rel}/__init__.py").exists()


def _cli_prefixes() -> set[tuple[str, ...]]:
    """Valid ``(verb, noun)`` command prefixes: the CLI table + registry + ``analyze lab``."""
    valid = {tuple(k) for k in cli._COMMANDS}
    for sub in cli._REGISTRY_SUBCOMMANDS:
        valid.add(("registry", sub))
    valid.add(("analyze", "lab"))
    return valid


def _violations(check: Callable[[str, str], list[str]]) -> list[str]:
    """Run ``check(text, rel)`` over every agent_config file, collecting ``file: reason`` strings."""
    out: list[str] = []
    for path in _files():
        rel = str(path.relative_to(ROOT))
        text = path.read_text(encoding="utf-8")
        out.extend(check(text, rel))
    return out


# --- the checks ---------------------------------------------------------------


def _check_paths(text: str, rel: str) -> list[str]:
    bad: list[str] = []
    for m in _BACKTICK.finditer(text):
        tok = m.group(1).strip()
        if _is_path_candidate(tok) and not _path_exists(tok):
            bad.append(f"{rel}: referenced path does not exist: `{tok}`")
    return bad


def _check_imports(text: str, rel: str) -> list[str]:
    bad: list[str] = []
    for m in _IMPORT.finditer(text):
        module = next((g for g in m.groups() if g), None)
        if module and module.startswith("agentic_dynamics") and not _module_exists(module):
            bad.append(f"{rel}: import example does not resolve: `{module}`")
    return bad


def _check_retired_imports(text: str, rel: str) -> list[str]:
    return [
        f"{rel}: retired `instrument` import at: {m.group(0)!r}"
        for m in _RETIRED_IMPORT.finditer(text)
    ]


def _check_cli(text: str, rel: str) -> list[str]:
    valid = _cli_prefixes()
    bad: list[str] = []
    for m in _CLI.finditer(text):
        prefix = (m.group(1), m.group(2))
        if prefix not in valid:
            bad.append(f"{rel}: unknown CLI command: `agentic-dynamics {prefix[0]} {prefix[1]}`")
    return bad


def _check_scripts(text: str, rel: str) -> list[str]:
    bad: list[str] = []
    for m in _SCRIPT.finditer(text):
        if not (ROOT / "scripts" / f"{m.group(1)}.{m.group(2)}").exists():
            bad.append(
                f"{rel}: referenced script does not exist: `scripts/{m.group(1)}.{m.group(2)}`"
            )
    return bad


def _check_taxonomy(text: str, rel: str) -> list[str]:
    bad: list[str] = []
    for m in _RETIRED_TAXONOMY.finditer(text):
        bad.append(f"{rel}: retired taxonomy term: {m.group(0)!r}")
    for m in _RETIRED_SUMMARY.finditer(text):
        line = text.count("\n", 0, m.start())
        context = text.splitlines()[line] if 0 <= line < len(text.splitlines()) else ""
        if not _RETIRED_FRAME.search(context):
            bad.append(
                f"{rel}: retired source `_results_summary.json` cited as live (line {line + 1})"
            )
    return bad


def _check_counts(text: str, rel: str) -> list[str]:
    return [f"{rel}: hard-coded count: {m.group(0)!r}" for m in _COUNT.finditer(text)]


# --- the tests ----------------------------------------------------------------


def test_referenced_repo_paths_exist():
    violations = _violations(_check_paths)
    assert not violations, "agent_config references paths that do not exist:\n" + "\n".join(
        sorted(violations)
    )


def test_import_examples_resolve():
    violations = _violations(_check_imports)
    assert not violations, "agent_config import examples that do not resolve:\n" + "\n".join(
        sorted(violations)
    )


def test_no_retired_package_imports():
    violations = _violations(_check_retired_imports)
    assert not violations, (
        "agent_config references the retired `instrument` package:\n"
        + "\n".join(sorted(violations))
    )


def test_cli_commands_exist():
    violations = _violations(_check_cli)
    assert not violations, "agent_config names unknown CLI commands:\n" + "\n".join(
        sorted(violations)
    )


def test_named_scripts_exist():
    violations = _violations(_check_scripts)
    assert not violations, "agent_config references scripts that do not exist:\n" + "\n".join(
        sorted(violations)
    )


def test_no_retired_taxonomy_or_sources():
    violations = _violations(_check_taxonomy)
    assert not violations, "agent_config references retired taxonomy/sources:\n" + "\n".join(
        sorted(violations)
    )


def test_no_hardcoded_counts():
    violations = _violations(_check_counts)
    assert not violations, "agent_config hard-codes module/line/file counts:\n" + "\n".join(
        sorted(violations)
    )
