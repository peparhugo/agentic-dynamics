"""Adapters — model backends (critique system 3).

Ownership: OpenCode (``opencode``) and Claude CLI (``claude_adapter``) drivers, and the
model → backend router (``backends``).

Pinned execution→control observation edge: ``opencode`` / ``claude_adapter`` → ``control.live``
— adapters publish telemetry, observe-only.
"""
