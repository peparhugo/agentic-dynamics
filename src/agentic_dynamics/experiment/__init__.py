"""Experiment — the experiment platform (critique system 2).

Ownership: the platform's contract + engine — ``ExperimentSpec`` and the
``requires``/``produces`` gate (``experiment_spec``), spec → DAG compilation
(``compile_experiment``), and the derived spec-lifecycle index (``spec_status``).

Reserved (deferred WS-05/06/07 — resume post-consolidation inside this plane): grid/cell/
campaign primitives (``adapt.py``, ``JobRecord``/``AttemptRecord``).
"""

from . import compile_experiment, experiment_spec, spec_status



__all__ = ['compile_experiment', 'experiment_spec', 'spec_status']
