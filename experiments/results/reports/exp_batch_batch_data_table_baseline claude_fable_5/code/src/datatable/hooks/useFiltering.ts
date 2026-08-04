import { useMemo, useState } from 'react';
import type { ColumnDef, FilterSpec, ServerQuery, SortSpec } from '../types';

export function matchesFilter(value: unknown, f: FilterSpec): boolean {
  const s = value === null || value === undefined ? '' : String(value).toLowerCase();
  const fv = f.value === null || f.value === undefined ? '' : String(f.value).toLowerCase();
  switch (f.operator) {
    case 'contains':
      return s.includes(fv);
    case 'equals':
      return value === f.value || s === fv;
    case 'startsWith':
      return s.startsWith(fv);
    case 'endsWith':
      return s.endsWith(fv);
    case 'gt':
      return Number(value) > Number(f.value);
    case 'gte':
      return Number(value) >= Number(f.value);
    case 'lt':
      return Number(value) < Number(f.value);
    case 'lte':
      return Number(value) <= Number(f.value);
    case 'between':
      return Number(value) >= Number(f.value) && Number(value) <= Number(f.value2);
    case 'in':
      return Array.isArray(f.value) && f.value.some((v) => v === value || String(v).toLowerCase() === s);
    case 'isEmpty':
      return s === '';
    case 'notEmpty':
      return s !== '';
    default:
      return true;
  }
}

/** AND-combined client-side filtering; returns original row indices. */
export function applyFilters<T>(
  rows: readonly T[],
  filters: readonly FilterSpec[],
  columns: readonly ColumnDef<T>[],
): number[] {
  if (filters.length === 0) return rows.map((_, i) => i);
  const colById = new Map(columns.map((c) => [c.id, c]));
  const out: number[] = [];
  rows.forEach((row, i) => {
    const ok = filters.every((f) => {
      const col = colById.get(f.columnId);
      if (!col) return true;
      const get = col.accessor ?? ((r: T) => (r as Record<string, unknown>)[col.id]);
      return matchesFilter(get(row), f);
    });
    if (ok) out.push(i);
  });
  return out;
}

/** Serialize state into a server query object (mirrored by core/filtering.py). */
export function buildServerQuery(
  sorts: readonly SortSpec[],
  filters: readonly FilterSpec[],
  offset: number,
  limit: number,
): ServerQuery {
  return { sorts: [...sorts], filters: [...filters], offset, limit };
}

export function useFiltering<T>(rows: readonly T[], columns: readonly ColumnDef<T>[]) {
  const [filters, setFilters] = useState<FilterSpec[]>([]);
  const filteredIndices = useMemo(() => applyFilters(rows, filters, columns), [rows, filters, columns]);
  return { filters, setFilters, filteredIndices };
}
