import { useCallback, useState } from 'react';
import type { EditingCell } from './types';

interface UseInlineEditOptions {
  onCellEdit?: (rowIndex: number, columnId: string, value: any) => void;
}

export function useInlineEdit({ onCellEdit }: UseInlineEditOptions = {}) {
  const [editingCell, setEditingCell] = useState<EditingCell | null>(null);

  const startEdit = useCallback((rowIndex: number, columnId: string) => {
    setEditingCell({ rowIndex, columnId });
  }, []);

  const commitEdit = useCallback(
    (value: any) => {
      if (editingCell) {
        onCellEdit?.(editingCell.rowIndex, editingCell.columnId, value);
        setEditingCell(null);
      }
    },
    [editingCell, onCellEdit]
  );

  const cancelEdit = useCallback(() => {
    setEditingCell(null);
  }, []);

  const isEditing = useCallback(
    (rowIndex: number, columnId: string): boolean => {
      return editingCell?.rowIndex === rowIndex && editingCell?.columnId === columnId;
    },
    [editingCell]
  );

  return { editingCell, startEdit, commitEdit, cancelEdit, isEditing };
}
