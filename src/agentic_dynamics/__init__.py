"""Agentic Dynamics — the modular monorepo (consolidation Stage 1).

The former semantic monolith `instrument` is re-homed here as eight bounded planes:
core, experiment, measurement, runtime, adapters, knowledge, control, reporting.
The transient `instrument.*` compat shim and the `legacy/` quarantine (rec 7) were
retired in this stage. See ARCHITECTURE.md for the plane map, the dependency spine,
and the package-boundary rules.
"""
