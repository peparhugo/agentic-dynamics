import { useRef, useCallback, useState, useMemo, useEffect } from 'react';

interface VirtualScrollOptions {
  totalRows: number;
  rowHeight: number;
  overscan: number;
  containerHeight: number;
}

interface VirtualScrollResult {
  startIndex: number;
  endIndex: number;
  visibleRows: number[];
  totalHeight: number;
  offsetY: number;
  scrollTop: number;
  containerRef: React.RefCallback<HTMLDivElement>;
  scrollToIndex: (index: number) => void;
}

export function useVirtualScroll({
  totalRows,
  rowHeight,
  overscan,
  containerHeight,
}: VirtualScrollOptions): VirtualScrollResult {
  const [scrollTop, setScrollTop] = useState(0);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const totalHeight = totalRows * rowHeight;

  const setContainerRef = useCallback((node: HTMLDivElement | null) => {
    containerRef.current = node;
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const handleScroll = () => {
      setScrollTop(el.scrollTop);
    };

    el.addEventListener('scroll', handleScroll, { passive: true });
    return () => el.removeEventListener('scroll', handleScroll);
  }, []);

  const startIndex = Math.max(0, Math.floor(scrollTop / rowHeight) - overscan);
  const visibleCount = Math.ceil(containerHeight / rowHeight) + overscan * 2;
  const endIndex = Math.min(totalRows, startIndex + visibleCount);
  const offsetY = startIndex * rowHeight;

  const visibleRows = useMemo(() => {
    const rows: number[] = [];
    for (let i = startIndex; i < endIndex; i++) {
      rows.push(i);
    }
    return rows;
  }, [startIndex, endIndex]);

  const scrollToIndex = useCallback(
    (index: number) => {
      const el = containerRef.current;
      if (!el) return;
      const target = Math.max(0, Math.min(index * rowHeight, totalHeight - containerHeight));
      el.scrollTop = target;
    },
    [rowHeight, totalHeight, containerHeight]
  );

  return {
    startIndex,
    endIndex,
    visibleRows,
    totalHeight,
    offsetY,
    scrollTop,
    containerRef: setContainerRef,
    scrollToIndex,
  };
}
