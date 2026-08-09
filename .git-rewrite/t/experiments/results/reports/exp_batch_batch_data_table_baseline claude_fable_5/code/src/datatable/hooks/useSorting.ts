import { useCallback, useMemo, useState } from 'react';
import type { ColumnDef, SortSpec } from '../types';

/** Default comparator: nulls last, numbers numerically, strings via localeCompare. */
export function defaultCompare(a: unknown, b: unknown): number {
  const aNull = a === null || a === undefined || a === '';
  const bNull = b === null || b === undefined || b === '';
  if (aNull && bNull) return 0;
  if (aNull) return 1;
  if (bNull) return -1;
  if (typeof a === 'number' && typeof b === 'number') return a - b;
  if (typeof a === 'boolean' && typeof b === 'boolean') return Number(a) - Number(b);
  return String(a).localeCompare(String(b));
}

/** Stable multi-column sort. Returns a new array of original row indices. */
export function multiSort<T>(
  rows: readonly T[],
  sorts: readonly SortSpec[],
  columns: readonly ColumnDef<T>[],
): number[] {
  const colById = new Map(columns.map((c) => [c.id, c]));
  const indices = rows.map((_, i) => i);
  if (sorts.length === 0) return indices;
  indices.sort((ia, ib) => {
    for (const s of sorts) {
      const col = colById.get(s.columnId);
      if (!col) continue;
      const get = col.accessor ?? ((r: T) => (r as Record<string, unknown>)[col.id]);
      const cmp = (col.comparator ?? defaultCompare)(get(rows[ia]), get(rows[ib]));
      if (cmp !== 0) return s.direction === 'asc' ? cmp : -cmp;
    }
    return ia - ib; // stability
  });
  return indices;
}

/** Cycle: none -> asc -> desc -> none. Shift-click appends for multi-sort. */
export function toggleSort(sorts: readonly SortSpec[], columnId: string, additive: boolean): SortSpec[] {
  const existing = sorts.find((s) => s.columnId === columnId);
  const others = additive ? sorts.filter((s) => s.columnId !== columnId) : [];
  if (!existing) return [...others, { columnId, direction: 'asc' }];
  if (existing.direction === 'asc') return [...others, { columnId, direction: 'desc' }];
  return [...others];
}

export function useSorting<T>(rows: readonly T[], columns: readonly ColumnDef<T>[]) {
  const [sorts, setSorts] = useState<SortSpec[]>([]);
  const sortedIndices = useMemo(() => multiSort(rows, sorts, columns), [rows, sorts, columns]);
  const onHeaderClick = useCallback(
    (columnId: string, shiftKey: boolean) => setSorts((s) => toggleSort(s, columnId, shiftKey)),
    [],
  );
  return { sorts, setSorts, sortedIndices, onHeaderClick };
}
