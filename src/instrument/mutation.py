"""Flash V4 mutation compiler — semantic perturbation of specs and code.

Uses DeepSeek Flash V4 to generate coherent, semantically meaningful
mutations of engineering specifications and source code. Each mutation
is compiled once per experiment cell and pinned as a hashable artifact,
ensuring all sessions in that cell see the same input.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .language import detect_language


# ── Operator Registry ──────────────────────────────────────────

SPECIFICATION_OPERATORS = [
    "inject_false_premise",
    "remove_constraint",
    "insert_contradiction",
    "invert_constraint",
    "inject_phantom_success",
    "inject_competing_goal",
    "inject_alien_vocab",
    "shift_framing",
    "reverse_causality",
    "force_abandonment",
]

CODEBASE_OPERATORS = [
    "inject_bug",
    "add_dead_code",
    "introduce_coupling",
    "duplicate_abstraction",
    "break_convention",
    "corrupt_docstring",
    "remove_error_handling",
    "weaken_type_hints",
    "scatter_logic",
    "circular_dependency",
]

ALL_OPERATORS = SPECIFICATION_OPERATORS + CODEBASE_OPERATORS


# ── Prompt Templates ───────────────────────────────────────────

_SPEC_MUTATION_PROMPT = """You are a mutation compiler for an experimental measurement instrument.
Your job is to apply a specific semantic perturbation to an engineering specification.

OPERATOR: {operator}
STRENGTH: {strength} (0.0 = minimal perturbation, 1.0 = maximum perturbation)

ORIGINAL SPECIFICATION:
{specification}

INSTRUCTIONS:
1. Apply the {operator} perturbation at strength {strength} to the specification.
2. Do NOT change the core task beyond what the operator demands.
3. Do NOT add commentary, explanations, or meta-commentary.
4. Output ONLY the mutated specification text.

MUTATED SPECIFICATION:"""

_CODE_MUTATION_PROMPT = """You are a mutation compiler for an experimental measurement instrument.
Your job is to inject a specific code-level perturbation into source files.

OPERATOR: {operator}
STRENGTH: {strength} (0.0 = minimal perturbation, 1.0 = maximum perturbation)

CODEBASE LANGUAGE: {language}

ORIGINAL FILES:
{files}

INSTRUCTIONS:
1. Apply the {operator} perturbation at strength {strength} to the codebase.
2. Make the changes look like organic accumulation of technical debt, not obviously deliberate sabotage.
3. Ensure the mutated code still compiles/parses (syntax remains valid).
4. Output ONLY a unified diff that can be applied with `patch -p1`.

UNIFIED DIFF:"""


# ── Data Structures ────────────────────────────────────────────

@dataclass
class MutationArtifact:
    """A pinned, hashable mutation artifact.

    Generated once per experiment cell. All sessions in that cell
    consume this exact artifact — no per-session randomness in the
    independent variable.
    """

    mutation_id: str
    operator: str
    operator_class: str  # "specification" | "codebase"
    strength: float
    compiler_model: str = "deepseek/deepseek-v4-flash"
    compiler_timestamp: str = ""
    original_spec: str = ""
    mutated_spec: str = ""
    codebase_patch: str = ""
    hash: str = ""

    def __post_init__(self):
        if not self.compiler_timestamp:
            self.compiler_timestamp = datetime.now(timezone.utc).isoformat()
        if not self.hash:
            self.hash = hashlib.sha256(
                json.dumps(self.to_dict(), sort_keys=True).encode()
            ).hexdigest()[:16]
        if not self.mutation_id:
            self.mutation_id = f"mut_{self.hash}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "mutation_id": self.mutation_id,
            "operator": self.operator,
            "operator_class": self.operator_class,
            "strength": self.strength,
            "compiler_model": self.compiler_model,
            "compiler_timestamp": self.compiler_timestamp,
            "original_spec": self.original_spec,
            "mutated_spec": self.mutated_spec,
            "codebase_patch": self.codebase_patch,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MutationArtifact":
        return cls(**d)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, s: str) -> "MutationArtifact":
        return cls.from_dict(json.loads(s))

    def save(self, path: Path) -> None:
        path.write_text(self.to_json())

    @classmethod
    def load(cls, path: Path) -> "MutationArtifact":
        return cls.from_json(path.read_text())

    def would_produce_changes(self) -> bool:
        """Whether applying this artifact would change anything."""
        return bool(self.mutated_spec or self.codebase_patch)


# ── Mutation Compiler ──────────────────────────────────────────

def compile_mutation(
    specification: str,
    operator: str,
    strength: float = 0.5,
    *,
    codebase_path: Path | None = None,
    model: str = "deepseek/deepseek-v4-flash",
    cache_dir: Path | None = None,
    timeout: int = 300,
) -> MutationArtifact:
    """Compile a mutation artifact using Flash V4.

    For specification operators: mutates the prompt text.
    For codebase operators: mutates source files, outputs a unified diff.

    Results are cached by hash in ``cache_dir`` to avoid re-compilation.

    Args:
        specification: Original clean specification text.
        operator: Name of the perturbation operator.
        strength: Perturbation strength 0.0–1.0.
        codebase_path: Path to codebase to mutate (for codebase operators).
        model: Model ID for the mutation compiler.
        cache_dir: Directory for cached mutation artifacts.
        timeout: Timeout for opencode session in seconds.

    Returns:
        Pinned MutationArtifact with mutated content.

    Raises:
        ValueError: If operator is unknown or compiler fails.
    """
    if operator not in ALL_OPERATORS:
        raise ValueError(
            f"Unknown operator: {operator!r}. "
            f"Must be one of {ALL_OPERATORS}"
        )
    if not 0.0 <= strength <= 1.0:
        raise ValueError(f"Strength must be 0.0–1.0, got {strength}")

    op_class = "codebase" if operator in CODEBASE_OPERATORS else "specification"

    # Check cache
    lookup = MutationArtifact(
        mutation_id="",
        operator=operator,
        operator_class=op_class,
        strength=strength,
        original_spec=specification,
        compiler_model=model,
    )
    lookup.hash = hashlib.sha256(
        f"{operator}|{strength}|{specification[:200]}|{model}".encode()
    ).hexdigest()[:16]
    lookup.mutation_id = f"mut_{lookup.hash}"

    if cache_dir:
        cache_path = cache_dir / f"{lookup.mutation_id}.json"
        if cache_path.exists():
            return MutationArtifact.load(cache_path)

    if op_class == "codebase":
        return _compile_codebase_mutation(
            specification, operator, strength, codebase_path, model, lookup
        )
    else:
        return _compile_spec_mutation(
            specification, operator, strength, model, lookup, timeout
        )


def _compile_spec_mutation(
    specification: str,
    operator: str,
    strength: float,
    model: str,
    artifact: MutationArtifact,
    timeout: int,
) -> MutationArtifact:
    """Compile a specification-level mutation via opencode CLI."""
    prompt = _SPEC_MUTATION_PROMPT.format(
        operator=operator,
        strength=strength,
        specification=specification,
    )

    mutated = _call_opencode(prompt, model=model, timeout=timeout)

    artifact.mutated_spec = mutated or specification
    artifact.original_spec = specification
    artifact.compiler_timestamp = datetime.now(timezone.utc).isoformat()
    artifact.hash = hashlib.sha256(
        json.dumps(artifact.to_dict(), sort_keys=True).encode()
    ).hexdigest()[:16]
    artifact.mutation_id = f"mut_{artifact.hash}"

    return artifact


def _compile_codebase_mutation(
    specification: str,
    operator: str,
    strength: float,
    codebase_path: Path | None,
    model: str,
    artifact: MutationArtifact,
) -> MutationArtifact:
    """Compile a codebase-level mutation via opencode CLI."""
    if codebase_path is None or not codebase_path.exists():
        raise ValueError("codebase_path is required for codebase operators")

    profile = detect_language(codebase_path)
    if profile is None:
        raise ValueError(f"No supported language files found in {codebase_path}")

    # Collect files for the prompt
    files_text = _collect_codebase_files(codebase_path, profile)

    prompt = _CODE_MUTATION_PROMPT.format(
        operator=operator,
        strength=strength,
        language=profile.name,
        files=files_text,
    )

    patch = _call_opencode(prompt, model=model, timeout=600)

    artifact.codebase_patch = patch or ""
    artifact.original_spec = specification
    artifact.compiler_timestamp = datetime.now(timezone.utc).isoformat()
    artifact.hash = hashlib.sha256(
        json.dumps(artifact.to_dict(), sort_keys=True).encode()
    ).hexdigest()[:16]
    artifact.mutation_id = f"mut_{artifact.hash}"

    return artifact


def _collect_codebase_files(path: Path, profile) -> str:
    """Collect source file contents for the mutation prompt."""
    parts: list[str] = []
    for ext in profile.extensions:
        for fp in sorted(path.rglob(f"*{ext}"))[:50]:
            try:
                content = fp.read_text()
                if len(content) > 2000:
                    content = content[:2000] + "\n... (truncated)"
                parts.append(f"--- {fp.relative_to(path)} ---\n{content}")
            except (OSError, UnicodeDecodeError):
                pass
    return "\n\n".join(parts)


def _call_opencode(
    prompt: str,
    *,
    model: str = "deepseek/deepseek-v4-flash",
    timeout: int = 300,
    silent: bool = True,
) -> str | None:
    """Run a single-turn prompt through opencode CLI.

    Returns the model's text response, or None on failure.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, prefix="mut_"
    ) as f:
        f.write(prompt)
        prompt_file = f.name

    try:
        args = [
            "open", "code",
            "--model", model,
            "--prompt-file", prompt_file,
            "--timeout", str(timeout),
        ]
        if silent:
            args.append("--silent")

        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout + 30,
        )

        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    finally:
        try:
            Path(prompt_file).unlink()
        except OSError:
            pass


# ── Artifact Application ───────────────────────────────────────

def apply_mutation(
    artifact: MutationArtifact,
    worktree_path: Path,
    *,
    spec_path: str | None = None,
) -> None:
    """Apply a mutation artifact to a worktree.

    For specification mutations: writes ``mutated_spec`` to ``spec_path``
    (or prints it if no path given).

    For codebase mutations: applies ``codebase_patch`` as a unified diff
    using ``patch -p1``.

    Args:
        artifact: The mutation to apply.
        worktree_path: Root of the worktree to mutate.
        spec_path: Relative path within worktree to write mutated spec.
                   Default: "specification.txt"
    """
    import subprocess as sp
    import tempfile

    if artifact.operator_class == "specification" and artifact.mutated_spec:
        target = worktree_path / (spec_path or "specification.txt")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(artifact.mutated_spec)

    elif artifact.operator_class == "codebase" and artifact.codebase_patch:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".diff", delete=False
        ) as f:
            f.write(artifact.codebase_patch)
            patch_file = f.name

        try:
            sp.run(
                ["patch", "-p1", "-i", patch_file, "-d", str(worktree_path)],
                capture_output=True,
                text=True,
                check=False,
            )
        finally:
            try:
                Path(patch_file).unlink()
            except OSError:
                pass
