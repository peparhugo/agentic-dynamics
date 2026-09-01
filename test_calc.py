"""Tests for the calc module.

VERBOSE MODE: Three tests cover the three functions — add, subtract, and
multiply. Each test asserts a single, easy-to-reason-about case.
"""

import calc


def test_add() -> None:
    """Add should return the sum of its operands."""
    assert calc.add(2, 3) == 5


def test_subtract() -> None:
    """Subtract should return the difference of its operands."""
    assert calc.subtract(5, 3) == 2


def test_multiply() -> None:
    """Multiply should return the product of its operands."""
    assert calc.multiply(2, 3) == 6
