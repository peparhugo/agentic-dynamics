import { useCallback, useState } from 'react';
import type { SelectionMode } from '../types';

export interface SelectionState {
  selected: ReadonlySet<string>;
  anchorIndex: number | null;
}

export interface ClickModifiers {
  ctrl: boolean;
  shift: boolean;
}

/**
 * Selection reducer mirrored by core/selection.py.
 * - single: click replaces selection
 * - multi: ctrl/cmd toggles; plain click replaces
 * - range: shift extends from anchor over the *visible* order
 */
export function reduceSelection(
  state: SelectionState,
  mode: SelectionMode,
  clickedIndex: number,
  visibleKeys: readonly string[],
  mods: ClickModifiers,
): SelectionState {
  const key = visibleKeys[clickedIndex];
  if (key === undefined) return state;

  if (mode === 'single') {
    return { selected: new Set([key]), anchorIndex: clickedIndex };
  }

  if (mods.shift && state.anchorIndex !== null) {
    const lo = Math.min(state.anchorIndex, clickedIndex);
    const hi = Math.max(state.anchorIndex, clickedIndex);
    const range = visibleKeys.slice(lo, hi + 1);
    const base = mods.ctrl ? new Set(state.selected) : new Set<string>();
    range.forEach((k) => base.add(k));
    return { selected: base, anchorIndex: state.anchorIndex };
  }

  if (mods.ctrl) {
    const next = new Set(state.selected);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    return { selected: next, anchorIndex: clickedIndex };
  }

  return { selected: new Set([key]), anchorIndex: clickedIndex };
}

export function selectAll(visibleKeys: readonly string[]): SelectionState {
  return { selected: new Set(visibleKeys), anchorIndex: visibleKeys.length ? 0 : null };
}

export function clearSelection(): SelectionState {
  return { selected: new Set(), anchorIndex: null };
}

export function useSelection(mode: SelectionMode, visibleKeys: readonly string[]) {
  const [state, setState] = useState<SelectionState>({ selected: new Set(), anchorIndex: null });
  const onRowClick = useCallback(
    (index: number, mods: ClickModifiers) =>
      setState((s) => reduceSelection(s, mode, index, visibleKeys, mods)),
    [mode, visibleKeys],
  );
  return {
    state,
    onRowClick,
    selectAll: () => setState(selectAll(visibleKeys)),
    clear: () => setState(clearSelection()),
  };
}
