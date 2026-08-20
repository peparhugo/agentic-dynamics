"""Single source of truth for the knowledge-base and registry filesystem paths.

canonical-state R6: two repo-root-relative literals — the durable per-record artifact
directory (``experiments/results/kb``) and the flat append-only registry index
(``experiments/results/registry_index.jsonl``) — were hand-duplicated across the
``kb_produce*`` producers, ``kb_worker``, ``generate_manifest``, and
``knowledge_ingestion``, each with a "keep in sync by hand" comment. This module owns
them so a path change can never silently desync a producer (which writes an artifact)
from a consumer (which reads it back at the same location — a real data-loss vector).

Deliberately a *leaf* module: it imports only :mod:`pathlib` — no ``redis``/``chromadb``/
``neo4j``. ``scripts/generate_manifest.py`` imports it as a value-only top-level module
(pointing ``sys.path`` straight at ``src/instrument``) so that dependency-light script
never pulls in the heavy ``instrument/__init__.py`` — see that script's comment.
"""

from pathlib import Path

#: Repo root, resolved from this module's location (``src/instrument/`` → repo root).
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

#: Durable per-record artifact directory, repo-root-RELATIVE. This relative form is the
#: ``file://`` URI contract ``knowledge_ingestion.artifact_uri`` builds (a consumer's
#: ``knowledge_stream.read_artifact`` resolves it against the checkout root); the absolute
#: :data:`KB_ARTIFACT_DIR` below is what on-disk writers use.
KB_ARTIFACT_DIR_REL = "experiments/results/kb"

#: Absolute filesystem path to the durable per-record artifact directory.
KB_ARTIFACT_DIR = PROJECT_ROOT / KB_ARTIFACT_DIR_REL

#: Flat, append-only registry index the ``kb-registry-v1`` consumer appends one compacted
#: JSON line to per indexed record (``scripts/kb_worker.py``), and that
#: ``scripts/generate_manifest.py`` later compacts into one row per entity_id.
REGISTRY_INDEX_PATH = PROJECT_ROOT / "experiments" / "results" / "registry_index.jsonl"
