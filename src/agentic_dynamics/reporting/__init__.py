"""Reporting — research + publication output (critique system 6).

Ownership: the game report (``game_report``), the LLM review pool (``review``), qualitative /
meta-experiment analysis (``ollama_analyzer`` / ``opencode_analyzer``), and the **publication
boundary** — three cooperating modules that decide what may reach the website:

* ``lab_manifest``    — WHICH labs may publish (classification: canonical/historical/quarantined)
* ``canonical_corpus`` — WHAT they may read (the registry resolver; the only lab input door)
* ``lab_contract``    — WHETHER a given artifact is still fresh (embedded lineage + validation)

Output does not steer (rec 8): reporting never imports ``control``.
"""

from . import (
    canonical_corpus,
    game_report,
    lab_contract,
    lab_manifest,
    ollama_analyzer,
    opencode_analyzer,
    review,
)

__all__ = [
    "canonical_corpus",
    "game_report",
    "lab_contract",
    "lab_manifest",
    "ollama_analyzer",
    "opencode_analyzer",
    "review",
]
