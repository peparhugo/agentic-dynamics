import { useCallback, useState } from 'react';
import type { ColumnDef } from '../types';

/** Move a column from one position to another (drag-and-drop reorder). */
export function reorder(order: readonly string[], fromIndex: number, toIndex: number): string[] {
  const next = [...order];
  if (fromIndex < 0 || fromIndex >= next.length) return next;
  const clampedTo = Math.max(0, Math.min(toIndex, next.length - 1));
  const [moved] = next.splice(fromIndex, 1);
  next.splice(clampedTo, 0, moved);
  return next;
}

/** Clamp a resize delta against min/max width. */
export function resizeWidth(current: number, delta: number, minWidth = 40, maxWidth = 1000): number {
  return Math.max(minWidth, Math.min(maxWidth, current + delta));
}

export function useColumns<T>(columns: readonly ColumnDef<T>[]) {
  const [order, setOrder] = useState<string[]>(() => columns.map((c) => c.id));
  const [widths, setWidths] = useState<Record<string, number>>(() =>
    Object.fromEntries(columns.map((c) => [c.id, c.width ?? 150])),
  );
  const [hidden, setHidden] = useState<ReadonlySet<string>>(new Set());

  const moveColumn = useCallback(
    (from: number, to: number) => setOrder((o) => reorder(o, from, to)),
    [],
  );

  const resizeColumn = useCallback(
    (id: string, delta: number) => {
      const col = columns.find((c) => c.id === id);
      setWidths((w) => ({
        ...w,
        [id]: resizeWidth(w[id] ?? 150, delta, col?.minWidth ?? 40, col?.maxWidth ?? 1000),
      }));
    },
    [columns],
  );

  const toggleVisibility = useCallback((id: string) => {
    setHidden((h) => {
      const next = new Set(h);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const visibleColumns = order
    .filter((id) => !hidden.has(id))
    .map((id) => columns.find((c) => c.id === id))
    .filter((c): c is ColumnDef<T> => Boolean(c));

  return { order, widths, hidden, visibleColumns, moveColumn, resizeColumn, toggleVisibility };
}
