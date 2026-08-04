import { useCallback, useRef } from 'react';

interface UseKeyboardNavigationOptions {
  totalRows: number;
  totalCols: number;
  onCellEdit?: (rowIndex: number, colIndex: number) => void;
  onSelectRow?: (rowIndex: number, event: React.KeyboardEvent) => void;
  onSelectAll?: () => void;
  scrollToRow?: (rowIndex: number) => void;
  containerRef: React.RefObject<HTMLDivElement | null>;
}

export function useKeyboardNavigation({
  totalRows,
  totalCols,
  onCellEdit,
  onSelectRow,
  onSelectAll,
  scrollToRow,
  containerRef,
}: UseKeyboardNavigationOptions) {
  const focusState = useRef({ row: 0, col: 0 });

  const moveFocus = useCallback(
    (rowDelta: number, colDelta: number) => {
      const next = focusState.current;
      const newRow = Math.max(0, Math.min(totalRows - 1, next.row + rowDelta));
      const newCol = Math.max(0, Math.min(totalCols - 1, next.col + colDelta));
      focusState.current = { row: newRow, col: newCol };

      if (rowDelta !== 0) {
        scrollToRow?.(newRow);
      }

      const activeElement = document.activeElement as HTMLElement;
      if (activeElement) {
        activeElement.blur();
      }

      requestAnimationFrame(() => {
        const cell = containerRef.current?.querySelector(
          `[data-row-index="${newRow}"][data-col-index="${newCol}"]`
        ) as HTMLElement;
        cell?.focus();
      });
    },
    [totalRows, totalCols, scrollToRow, containerRef]
  );

  const setFocusedCell = useCallback((row: number, col: number) => {
    focusState.current = { row, col };
  }, []);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      const { row, col } = focusState.current;
      let handled = true;

      switch (event.key) {
        case 'ArrowUp':
          moveFocus(-1, 0);
          event.preventDefault();
          break;
        case 'ArrowDown':
          moveFocus(1, 0);
          event.preventDefault();
          break;
        case 'ArrowLeft':
          moveFocus(0, -1);
          event.preventDefault();
          break;
        case 'ArrowRight':
          moveFocus(0, 1);
          event.preventDefault();
          break;
        case 'Home':
          if (event.ctrlKey) {
            moveFocus(-row, -col);
          } else {
            moveFocus(0, -col);
          }
          event.preventDefault();
          break;
        case 'End':
          if (event.ctrlKey) {
            moveFocus(totalRows - 1 - row, totalCols - 1 - col);
          } else {
            moveFocus(0, totalCols - 1 - col);
          }
          event.preventDefault();
          break;
        case 'PageUp':
          moveFocus(-20, 0);
          event.preventDefault();
          break;
        case 'PageDown':
          moveFocus(20, 0);
          event.preventDefault();
          break;
        case 'Enter':
        case 'F2':
          if (onCellEdit) {
            onCellEdit(row, col);
          }
          event.preventDefault();
          break;
        case ' ':
          if (onSelectRow) {
            onSelectRow(row, event);
          }
          event.preventDefault();
          break;
        case 'a':
          if (event.ctrlKey && onSelectAll) {
            onSelectAll();
            event.preventDefault();
          }
          break;
        default:
          handled = false;
      }

      if (handled) {
        event.stopPropagation();
      }
    },
    [totalRows, totalCols, moveFocus, onCellEdit, onSelectRow, onSelectAll]
  );

  return { handleKeyDown, moveFocus, setFocusedCell, focusState };
}
