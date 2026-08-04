import { useCallback, useState } from 'react';
import type { CellPosition, ColumnDef } from '../types';

export interface EditState {
  cell: CellPosition | null;
  draft: unknown;
  error: string | null;
}

export const idleEdit: EditState = { cell: null, draft: null, error: null };

export function useInlineEdit<T>(
  columns: readonly ColumnDef<T>[],
  rows: readonly T[],
  onRowsChange: (rows: T[]) => void,
) {
  const [edit, setEdit] = useState<EditState>(idleEdit);

  const begin = useCallback(
    (cell: CellPosition, initial: unknown) => setEdit({ cell, draft: initial, error: null }),
    [],
  );

  const update = useCallback((draft: unknown) => setEdit((e) => ({ ...e, draft })), []);

  const cancel = useCallback(() => setEdit(idleEdit), []);

  const commit = useCallback(() => {
    setEdit((e) => {
      if (!e.cell) return e;
      const col = columns[e.cell.colIndex];
      const row = rows[e.cell.rowIndex];
      if (!col || row === undefined) return idleEdit;
      const error = col.validator ? col.validator(e.draft, row) : null;
      if (error) return { ...e, error };
      const next = [...rows];
      next[e.cell.rowIndex] = { ...(row as object), [col.id]: e.draft } as T;
      onRowsChange(next);
      return idleEdit;
    });
  }, [columns, rows, onRowsChange]);

  return { edit, begin, update, cancel, commit };
}
