"""Reporting — research + publication output (critique system 6).

Ownership: the game report (``game_report``), the LLM review pool (``review``), qualitative /
meta-experiment analysis (``ollama_analyzer`` / ``opencode_analyzer``), and the lab
classification manifest (``lab_manifest``) that gates which lab books run in the default
reproduction and which may reach the website.

Output does not steer (rec 8): reporting never imports ``control``.
"""

from . import game_report, lab_manifest, ollama_analyzer, opencode_analyzer, review


__all__ = ["game_report", "lab_manifest", "ollama_analyzer", "opencode_analyzer", "review"]
