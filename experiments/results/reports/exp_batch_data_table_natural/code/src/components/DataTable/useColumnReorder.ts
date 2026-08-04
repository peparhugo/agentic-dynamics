import { useCallback, useState, useRef } from 'react';

interface UseColumnReorderOptions {
  columnIds: string[];
  onColumnOrderChange?: (columnIds: string[]) => void;
}

export function useColumnReorder({ columnIds, onColumnOrderChange }: UseColumnReorderOptions) {
  const [draggedColumn, setDraggedColumn] = useState<string | null>(null);
  const [dropTarget, setDropTarget] = useState<{ columnId: string; position: 'before' | 'after' } | null>(null);
  const dragOverRef = useRef<number>(0);

  const handleDragStart = useCallback(
    (columnId: string, event: React.DragEvent) => {
      setDraggedColumn(columnId);
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', columnId);
    },
    []
  );

  const handleDragOver = useCallback(
    (columnId: string, event: React.DragEvent) => {
      event.preventDefault();
      if (!draggedColumn || draggedColumn === columnId) return;

      const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
      const mid = rect.left + rect.width / 2;
      const position = event.clientX < mid ? 'before' : 'after';

      setDropTarget({ columnId, position });
    },
    [draggedColumn]
  );

  const handleDrop = useCallback(
    (targetColumnId: string, event: React.DragEvent) => {
      event.preventDefault();
      if (!draggedColumn || draggedColumn === targetColumnId) {
        setDraggedColumn(null);
        setDropTarget(null);
        return;
      }

      const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
      const mid = rect.left + rect.width / 2;
      const position: 'before' | 'after' = event.clientX < mid ? 'before' : 'after';

      const reordered = [...columnIds];
      const dragIdx = reordered.indexOf(draggedColumn);
      let targetIdx = reordered.indexOf(targetColumnId);

      if (dragIdx >= 0 && targetIdx >= 0) {
        reordered.splice(dragIdx, 1);
        if (position === 'after') targetIdx++;
        if (dragIdx < targetIdx) targetIdx--;
        reordered.splice(Math.max(0, targetIdx), 0, draggedColumn);
      }

      onColumnOrderChange?.(reordered);

      setDraggedColumn(null);
      setDropTarget(null);
    },
    [draggedColumn, columnIds, onColumnOrderChange]
  );

  const handleDragEnd = useCallback(() => {
    setDraggedColumn(null);
    setDropTarget(null);
  }, []);

  const reorderColumns = useCallback(
    (fromIndex: number, toIndex: number) => {
      const reordered = [...columnIds];
      const [moved] = reordered.splice(fromIndex, 1);
      reordered.splice(toIndex, 0, moved);
      onColumnOrderChange?.(reordered);
      return reordered;
    },
    [columnIds, onColumnOrderChange]
  );

  return {
    draggedColumn,
    dropTarget,
    handleDragStart,
    handleDragOver,
    handleDrop,
    handleDragEnd,
    reorderColumns,
  };
}
