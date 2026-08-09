import { useCallback, useState } from 'react';
import type { CellPosition } from '../types';

export type NavKey =
  | 'ArrowUp'
  | 'ArrowDown'
  | 'ArrowLeft'
  | 'ArrowRight'
  | 'Home'
  | 'End'
  | 'PageUp'
  | 'PageDown';

/**
 * Grid keyboard navigation per WAI-ARIA grid pattern (mirrored by
 * core/keyboard_nav.py). Ctrl+Home/End jump to grid corners; Home/End
 * move within the row; PageUp/PageDown move by one viewport page.
 */
export function navigate(
  pos: CellPosition,
  key: NavKey,
  rowCount: number,
  colCount: number,
  pageSize: number,
  ctrl = false,
): CellPosition {
  if (rowCount === 0 || colCount === 0) return pos;
  const clamp = (r: number, c: number): CellPosition => ({
    rowIndex: Math.max(0, Math.min(rowCount - 1, r)),
    colIndex: Math.max(0, Math.min(colCount - 1, c)),
  });
  switch (key) {
    case 'ArrowUp':
      return clamp(pos.rowIndex - 1, pos.colIndex);
    case 'ArrowDown':
      return clamp(pos.rowIndex + 1, pos.colIndex);
    case 'ArrowLeft':
      return clamp(pos.rowIndex, pos.colIndex - 1);
    case 'ArrowRight':
      return clamp(pos.rowIndex, pos.colIndex + 1);
    case 'Home':
      return ctrl ? clamp(0, 0) : clamp(pos.rowIndex, 0);
    case 'End':
      return ctrl ? clamp(rowCount - 1, colCount - 1) : clamp(pos.rowIndex, colCount - 1);
    case 'PageUp':
      return clamp(pos.rowIndex - pageSize, pos.colIndex);
    case 'PageDown':
      return clamp(pos.rowIndex + pageSize, pos.colIndex);
    default:
      return pos;
  }
}

export function useKeyboardNav(rowCount: number, colCount: number, pageSize: number) {
  const [focus, setFocus] = useState<CellPosition>({ rowIndex: 0, colIndex: 0 });
  const onKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      const keys: string[] = ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Home', 'End', 'PageUp', 'PageDown'];
      if (!keys.includes(e.key)) return;
      e.preventDefault();
      setFocus((p) => navigate(p, e.key as NavKey, rowCount, colCount, pageSize, e.ctrlKey || e.metaKey));
    },
    [rowCount, colCount, pageSize],
  );
  return { focus, setFocus, onKeyDown };
}
