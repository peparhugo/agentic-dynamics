"""A minimal calculator module.

VERBOSE MODE: This module is intentionally trivial — the p4_activation_gate
proof measures the augmentation outcome (retrieval attempt, constructor
acceptance, fallback mode), not the feature. The functions below exist so the
phase has real, testable application code to deliver.
"""


def add(a: float, b: float) -> float:
    """Return the sum of ``a`` and ``b``."""
    return a + b


def subtract(a: float, b: float) -> float:
    """Return ``a`` minus ``b``."""
    return a - b


def multiply(a: float, b: float) -> float:
    """Return the product of ``a`` and ``b``."""
    return a * b
