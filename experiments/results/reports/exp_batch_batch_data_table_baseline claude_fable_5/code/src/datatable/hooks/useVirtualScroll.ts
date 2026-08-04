import { useMemo, useState, useCallback } from 'react';
import type { VirtualWindow } from '../types';

/**
 * Windowing calculation. Pure math mirrored by core/virtual_window.py.
 * Renders only the rows intersecting the viewport plus `overscan` rows
 * on each side, positioned inside a spacer of `totalHeight`.
 */
export function computeVirtualWindow(
  scrollTop: number,
  rowHeight: number,
  viewportHeight: number,
  totalRows: number,
  overscan = 5,
): VirtualWindow {
  const totalHeight = totalRows * rowHeight;
  if (totalRows === 0 || rowHeight <= 0 || viewportHeight <= 0) {
    return { startIndex: 0, endIndex: 0, offsetY: 0, totalHeight };
  }
  const clampedTop = Math.min(Math.max(scrollTop, 0), Math.max(totalHeight - viewportHeight, 0));
  const first = Math.floor(clampedTop / rowHeight);
  const visible = Math.ceil(viewportHeight / rowHeight) + 1;
  const startIndex = Math.max(0, first - overscan);
  const endIndex = Math.min(totalRows, first + visible + overscan);
  return { startIndex, endIndex, offsetY: startIndex * rowHeight, totalHeight };
}

export function useVirtualScroll(rowHeight: number, viewportHeight: number, totalRows: number, overscan = 5) {
  const [scrollTop, setScrollTop] = useState(0);

  const onScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    setScrollTop(e.currentTarget.scrollTop);
  }, []);

  const window = useMemo(
    () => computeVirtualWindow(scrollTop, rowHeight, viewportHeight, totalRows, overscan),
    [scrollTop, rowHeight, viewportHeight, totalRows, overscan],
  );

  const scrollToRow = useCallback(
    (index: number, el: HTMLDivElement | null) => {
      if (!el) return;
      const top = index * rowHeight;
      const bottom = top + rowHeight;
      if (top < el.scrollTop) el.scrollTop = top;
      else if (bottom > el.scrollTop + viewportHeight) el.scrollTop = bottom - viewportHeight;
    },
    [rowHeight, viewportHeight],
  );

  return { window, onScroll, scrollToRow, scrollTop };
}
