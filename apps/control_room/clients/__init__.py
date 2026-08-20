"""Control Room external-interface clients (refactor-repair Debt-1).

``opencode_client`` wraps the running OpenCode HTTP server; ``claude_agents_client`` wraps the
``claude`` CLI for one-shot background-session control. Extracted from the flat
``apps/control_room/`` into ``clients/`` so the route handlers and services import them from a
stable home.
"""
