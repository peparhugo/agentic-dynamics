"""Client-side filtering + server query building. Mirrors hooks/useFiltering.ts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence
from urllib.parse import urlencode

from .sorting import SortSpec


@dataclass(frozen=True)
class FilterSpec:
    column_id: str
    operator: str
    value: Any = None
    value2: Any = None  # for "between"


def _as_number(v: Any) -> float | None:
    try:
        if isinstance(v, bool):
            return float(v)
        return float(v)
    except (TypeError, ValueError):
        return None


def matches_filter(value: Any, f: FilterSpec) -> bool:
    s = "" if value is None else str(value).lower()
    fv = "" if f.value is None else str(f.value).lower()
    op = f.operator

    if op == "contains":
        return fv in s
    if op == "equals":
        return value == f.value or s == fv
    if op == "startsWith":
        return s.startswith(fv)
    if op == "endsWith":
        return s.endswith(fv)
    if op in ("gt", "gte", "lt", "lte"):
        n, fn = _as_number(value), _as_number(f.value)
        if n is None or fn is None:
            return False
        return {"gt": n > fn, "gte": n >= fn, "lt": n < fn, "lte": n <= fn}[op]
    if op == "between":
        n, lo, hi = _as_number(value), _as_number(f.value), _as_number(f.value2)
        if n is None or lo is None or hi is None:
            return False
        return lo <= n <= hi
    if op == "in":
        if not isinstance(f.value, (list, tuple, set)):
            return False
        return any(v == value or str(v).lower() == s for v in f.value)
    if op == "isEmpty":
        return s == ""
    if op == "notEmpty":
        return s != ""
    return True


def apply_filters(
    rows: Sequence[Mapping[str, Any]],
    filters: Sequence[FilterSpec],
) -> list[int]:
    """AND-combined filters; returns matching original row indices."""
    if not filters:
        return list(range(len(rows)))
    return [
        i
        for i, row in enumerate(rows)
        if all(matches_filter(row.get(f.column_id), f) for f in filters)
    ]


@dataclass(frozen=True)
class ServerQuery:
    sorts: tuple[SortSpec, ...] = ()
    filters: tuple[FilterSpec, ...] = ()
    offset: int = 0
    limit: int = 100

    def to_params(self) -> dict[str, str]:
        """Serialize for a REST backend (deterministic ordering)."""
        params: dict[str, str] = {
            "offset": str(self.offset),
            "limit": str(self.limit),
        }
        if self.sorts:
            params["sort"] = ",".join(
                f"{s.column_id}:{s.direction}" for s in self.sorts
            )
        for i, f in enumerate(self.filters):
            base = f"filter[{i}]"
            params[f"{base}[col]"] = f.column_id
            params[f"{base}[op]"] = f.operator
            if f.value is not None:
                if isinstance(f.value, (list, tuple, set)):
                    params[f"{base}[value]"] = ",".join(str(v) for v in f.value)
                else:
                    params[f"{base}[value]"] = str(f.value)
            if f.value2 is not None:
                params[f"{base}[value2]"] = str(f.value2)
        return params

    def to_query_string(self) -> str:
        return urlencode(self.to_params())


def build_server_query(
    sorts: Sequence[SortSpec],
    filters: Sequence[FilterSpec],
    offset: int,
    limit: int,
) -> ServerQuery:
    return ServerQuery(tuple(sorts), tuple(filters), offset, limit)
