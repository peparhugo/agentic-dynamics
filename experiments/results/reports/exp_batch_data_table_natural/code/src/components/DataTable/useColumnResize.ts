import { useCallback, useRef, useState } from 'react';
import type { ColumnDef } from './types';

interface UseColumnResizeOptions {
  columns: ColumnDef[];
  onColumnResize?: (columnId: string, width: number) => void;
}

export function useColumnResize({ columns, onColumnResize }: UseColumnResizeOptions) {
  const [columnWidths, setColumnWidths] = useState<Record<string, number>>(() => {
    const widths: Record<string, number> = {};
    columns.forEach((col) => {
      widths[col.id] = col.width;
    });
    return widths;
  });

  const [resizing, setResizing] = useState<{
    columnId: string;
    startX: number;
    startWidth: number;
  } | null>(null);

  const resizeStart = useCallback(
    (columnId: string, event: React.MouseEvent) => {
      event.preventDefault();
      event.stopPropagation();
      const currentWidth = columnWidths[columnId] || columns.find((c) => c.id === columnId)?.width || 100;
      setResizing({ columnId, startX: event.clientX, startWidth: currentWidth });
    },
    [columnWidths, columns]
  );

  const resizeMove = useCallback(
    (event: MouseEvent) => {
      if (!resizing) return;
      const delta = event.clientX - resizing.startX;
      const newWidth = Math.max(50, resizing.startWidth + delta);
      const col = columns.find((c) => c.id === resizing.columnId);
      const clamped = col?.maxWidth ? Math.min(newWidth, col.maxWidth) : newWidth;
      const final = col?.minWidth ? Math.max(clamped, col.minWidth) : clamped;

      setColumnWidths((prev) => ({ ...prev, [resizing.columnId]: final }));
    },
    [resizing, columns]
  );

  const resizeEnd = useCallback(() => {
    if (resizing) {
      onColumnResize?.(resizing.columnId, columnWidths[resizing.columnId]);
    }
    setResizing(null);
  }, [resizing, columnWidths, onColumnResize]);

  const updateColumnWidths = useCallback((newColumns: ColumnDef[]) => {
    const widths: Record<string, number> = {};
    newColumns.forEach((col) => {
      widths[col.id] = col.width;
    });
    setColumnWidths(widths);
  }, []);

  return {
    columnWidths,
    resizing,
    resizeStart,
    resizeMove,
    resizeEnd,
    updateColumnWidths,
  };
}
