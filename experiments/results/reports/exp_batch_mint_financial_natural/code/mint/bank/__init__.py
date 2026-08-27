"""Bank adapter layer.

Each financial institution exposes a slightly different API: different field
names, date formats, amount sign conventions, and currency codes. Rather than
leaking that inconsistency into the rest of the system, every adapter
normalizes raw API responses into a common ``RawTransaction`` shape. The
aggregation service only ever consumes ``RawTransaction`` objects.
"""

from .base import BankAdapter, RawAccount, RawTransaction, SignConvention
from .adapters import ChaseAdapter, WellsFargoAdapter, CapitalOneAdapter
from .registry import AdapterRegistry, get_adapter

__all__ = [
    "BankAdapter",
    "RawAccount",
    "RawTransaction",
    "SignConvention",
    "ChaseAdapter",
    "WellsFargoAdapter",
    "CapitalOneAdapter",
    "AdapterRegistry",
    "get_adapter",
]
