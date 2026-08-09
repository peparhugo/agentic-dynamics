import { useCallback, useState, useRef } from 'react';
import type { SelectionMode } from './types';

interface UseSelectionOptions {
  mode: SelectionMode;
  dataLength: number;
  idAccessor: (index: number) => string;
  externalSelected?: Set<string>;
  onSelectionChange?: (selectedIds: Set<string>) => void;
}

export function useSelection({
  mode,
  dataLength,
  idAccessor,
  externalSelected,
  onSelectionChange,
}: UseSelectionOptions) {
  const [internalSelected, setInternalSelected] = useState<Set<string>>(new Set());
  const [anchorIndex, setAnchorIndex] = useState<number | null>(null);
  const lastClickedRef = useRef<number | null>(null);

  const selectedIds = externalSelected ?? internalSelected;

  const setSelected = useCallback(
    (next: Set<string>) => {
      if (externalSelected !== undefined) {
        onSelectionChange?.(next);
      } else {
        setInternalSelected(next);
      }
    },
    [externalSelected, onSelectionChange]
  );

  const isSelected = useCallback(
    (index: number): boolean => {
      return selectedIds.has(idAccessor(index));
    },
    [selectedIds, idAccessor]
  );

  const toggleRow = useCallback(
    (index: number, event?: React.MouseEvent | React.KeyboardEvent) => {
      const id = idAccessor(index);

      if (mode === 'single') {
        setSelected(new Set([id]));
        setAnchorIndex(index);
        return;
      }

      if (mode === 'range' && event?.shiftKey && anchorIndex != null) {
        const start = Math.min(anchorIndex, index);
        const end = Math.max(anchorIndex, index);
        const newSet = new Set<string>();
        for (let i = start; i <= end; i++) {
          newSet.add(idAccessor(i));
        }
        if (event?.ctrlKey || event?.metaKey) {
          const union = new Set(selectedIds);
          newSet.forEach((id) => union.add(id));
          setSelected(union);
        } else {
          setSelected(newSet);
        }
        setAnchorIndex(index);
        return;
      }

      if (mode === 'multi' && (event?.ctrlKey || event?.metaKey)) {
        const newSet = new Set(selectedIds);
        if (newSet.has(id)) {
          newSet.delete(id);
        } else {
          newSet.add(id);
        }
        setSelected(newSet);
        setAnchorIndex(index);
        return;
      }

      const newSet = new Set<string>();
      newSet.add(id);
      setSelected(newSet);
      setAnchorIndex(index);
    },
    [mode, anchorIndex, selectedIds, idAccessor, setSelected]
  );

  const selectAll = useCallback(() => {
    if (mode === 'single') return;
    const allIds = new Set<string>();
    for (let i = 0; i < dataLength; i++) {
      allIds.add(idAccessor(i));
    }
    setSelected(allIds);
  }, [mode, dataLength, idAccessor, setSelected]);

  const clearSelection = useCallback(() => {
    setSelected(new Set());
    setAnchorIndex(null);
  }, [setSelected]);

  const selectRange = useCallback(
    (start: number, end: number) => {
      if (mode === 'single') return;
      const s = Math.min(start, end);
      const e = Math.max(start, end);
      const newSet = new Set<string>();
      for (let i = s; i <= e; i++) {
        newSet.add(idAccessor(i));
      }
      setSelected(newSet);
    },
    [mode, idAccessor, setSelected]
  );

  return {
    selectedIds,
    anchorIndex,
    isSelected,
    toggleRow,
    selectAll,
    clearSelection,
    selectRange,
    setSelected,
  };
}
