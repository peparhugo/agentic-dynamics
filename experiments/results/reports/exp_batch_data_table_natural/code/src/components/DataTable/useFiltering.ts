import { useCallback, useState } from 'react';
import type { FilterRule, FilterOperator } from './types';

interface UseFilteringOptions {
  externalFilters?: FilterRule[];
  onFilterChange?: (filterRules: FilterRule[]) => void;
}

export function useFiltering({ externalFilters, onFilterChange }: UseFilteringOptions = {}) {
  const [internalFilters, setInternalFilters] = useState<FilterRule[]>([]);

  const filterRules = externalFilters ?? internalFilters;

  const setFilter = useCallback(
    (columnId: string, operator: FilterOperator, value: string) => {
      const update = (prev: FilterRule[]) => {
        const existingIdx = prev.findIndex((r) => r.columnId === columnId);
        if (existingIdx >= 0) {
          if (value === '') {
            return prev.filter((r) => r.columnId !== columnId);
          }
          const updated = [...prev];
          updated[existingIdx] = { columnId, operator, value };
          return updated;
        }
        if (value === '') return prev;
        return [...prev, { columnId, operator, value }];
      };

      if (externalFilters !== undefined) {
        const next = update(filterRules);
        onFilterChange?.(next);
      } else {
        setInternalFilters((prev) => update(prev));
      }
    },
    [externalFilters, filterRules, onFilterChange]
  );

  const clearFilters = useCallback(() => {
    if (externalFilters !== undefined) {
      onFilterChange?.([]);
    } else {
      setInternalFilters([]);
    }
  }, [externalFilters, onFilterChange]);

  const clearColumnFilter = useCallback(
    (columnId: string) => {
      setFilter(columnId, 'contains', '');
    },
    [setFilter]
  );

  return { filterRules, setFilter, clearFilters, clearColumnFilter };
}
