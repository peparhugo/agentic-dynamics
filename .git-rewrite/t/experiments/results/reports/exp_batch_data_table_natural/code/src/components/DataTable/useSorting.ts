import { useCallback, useMemo, useState } from 'react';
import type { SortRule, SortDirection } from './types';

interface UseSortingOptions {
  externalSort?: SortRule[];
  onSortChange?: (sortRules: SortRule[]) => void;
}

export function useSorting({ externalSort, onSortChange }: UseSortingOptions = {}) {
  const [internalSort, setInternalSort] = useState<SortRule[]>([]);

  const sortRules = externalSort ?? internalSort;

  const toggleSort = useCallback(
    (columnId: string, multiSort: boolean = false) => {
      const update = (prev: SortRule[]) => {
        const existingIdx = prev.findIndex((r) => r.columnId === columnId);

        if (existingIdx >= 0) {
          const existing = prev[existingIdx];
          if (existing.direction === 'asc') {
            const updated = [...prev];
            updated[existingIdx] = { columnId, direction: 'desc' as SortDirection };
            return updated;
          } else {
            return prev.filter((r) => r.columnId !== columnId);
          }
        }

        if (!multiSort) {
          return [{ columnId, direction: 'asc' as SortDirection }];
        }

        return [...prev, { columnId, direction: 'asc' as SortDirection }];
      };

      if (externalSort !== undefined) {
        const next = update(sortRules);
        onSortChange?.(next);
      } else {
        setInternalSort((prev) => update(prev));
      }
    },
    [externalSort, sortRules, onSortChange]
  );

  const clearSort = useCallback(() => {
    if (externalSort !== undefined) {
      onSortChange?.([]);
    } else {
      setInternalSort([]);
    }
  }, [externalSort, onSortChange]);

  const sortMap = useMemo(() => {
    const map = new Map<string, SortDirection>();
    sortRules.forEach((r) => map.set(r.columnId, r.direction));
    return map;
  }, [sortRules]);

  return { sortRules, sortMap, toggleSort, clearSort, setInternalSort };
}
