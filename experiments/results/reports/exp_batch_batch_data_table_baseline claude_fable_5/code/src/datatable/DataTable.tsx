import React, { useEffect, useMemo, useRef, useState } from 'react';
import type { DataTableProps } from './types';
import { useVirtualScroll } from './hooks/useVirtualScroll';
import { useSorting } from './hooks/useSorting';
import { useFiltering, buildServerQuery } from './hooks/useFiltering';
import { useSelection } from './hooks/useSelection';
import { useColumns } from './hooks/useColumns';
import { useKeyboardNav } from './hooks/useKeyboardNav';
import { useInlineEdit } from './hooks/useInlineEdit';

/**
 * DataTable — virtualized, accessible (WCAG 2.1 AA / WAI-ARIA grid) data grid.
 *
 * Accessibility notes:
 * - role="grid" with aria-rowcount/aria-colcount reflecting the FULL dataset,
 *   since only a window of rows is in the DOM (virtual scrolling).
 * - Each rendered row carries aria-rowindex; cells carry aria-colindex.
 * - Roving tabindex: exactly one cell has tabIndex=0; arrows/Home/End/Page
 *   keys move focus (WAI-ARIA grid keyboard pattern).
 * - Sort state exposed via aria-sort on column headers.
 * - Selection exposed via aria-selected + aria-multiselectable.
 * - Edits announced through an aria-live polite region.
 * - All interactive targets meet 24px minimum; color is never the only
 *   selected-state indicator (checkmark + background).
 */
export function DataTable<T>(props: DataTableProps<T>) {
  const {
    columns,
    rows,
    rowKey,
    rowHeight = 36,
    height = 600,
    overscan = 8,
    selectionMode = 'multi',
    filterMode = 'client',
    onServerQuery,
    onRowsChange,
    onSelectionChange,
    ariaLabel,
  } = props;

  const containerRef = useRef<HTMLDivElement>(null);
  const [serverRows, setServerRows] = useState<T[] | null>(null);
  const [serverTotal, setServerTotal] = useState(0);
  const [liveMessage, setLiveMessage] = useState('');

  const { visibleColumns, widths, moveColumn, resizeColumn } = useColumns(columns);
  const { sorts, sortedIndices, onHeaderClick } = useSorting(rows, columns);
  const { filters, setFilters, filteredIndices } = useFiltering(rows, columns);

  // Compose filter -> sort for client mode.
  const viewIndices = useMemo(() => {
    if (filterMode === 'server') return null;
    const filtered = new Set(filteredIndices);
    return sortedIndices.filter((i) => filtered.has(i));
  }, [filterMode, filteredIndices, sortedIndices]);

  const effectiveRows = filterMode === 'server' ? serverRows ?? [] : rows;
  const rowCount = filterMode === 'server' ? serverTotal : viewIndices?.length ?? 0;

  const { window: vw, onScroll } = useVirtualScroll(rowHeight, height, rowCount, overscan);

  // Server-side querying: refetch on sort/filter/window change.
  useEffect(() => {
    if (filterMode !== 'server' || !onServerQuery) return;
    let cancelled = false;
    const q = buildServerQuery(sorts, filters, vw.startIndex, vw.endIndex - vw.startIndex);
    onServerQuery(q).then(({ rows: r, total }) => {
      if (cancelled) return;
      setServerRows(r);
      setServerTotal(total);
    });
    return () => {
      cancelled = true;
    };
  }, [filterMode, onServerQuery, sorts, filters, vw.startIndex, vw.endIndex]);

  const visibleKeys = useMemo(() => {
    if (filterMode === 'server') return (serverRows ?? []).map(rowKey);
    return (viewIndices ?? []).map((i) => rowKey(rows[i]));
  }, [filterMode, serverRows, viewIndices, rows, rowKey]);

  const selection = useSelection(selectionMode, visibleKeys);
  useEffect(() => onSelectionChange?.(selection.state.selected), [selection.state.selected, onSelectionChange]);

  const pageSize = Math.max(1, Math.floor(height / rowHeight));
  const nav = useKeyboardNav(rowCount, visibleColumns.length, pageSize);

  const editor = useInlineEdit(visibleColumns, rows, (next) => {
    onRowsChange?.(next);
    setLiveMessage('Cell value updated');
  });

  const rowAt = (viewIndex: number): T | undefined => {
    if (filterMode === 'server') return serverRows?.[viewIndex - vw.startIndex];
    const orig = viewIndices?.[viewIndex];
    return orig === undefined ? undefined : rows[orig];
  };

  const gridTemplate = visibleColumns.map((c) => `${widths[c.id] ?? 150}px`).join(' ');

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (editor.edit.cell) {
      if (e.key === 'Escape') editor.cancel();
      if (e.key === 'Enter') editor.commit();
      return;
    }
    if (e.key === 'Enter' || e.key === 'F2') {
      const col = visibleColumns[nav.focus.colIndex];
      const row = rowAt(nav.focus.rowIndex);
      if (col?.editable && row !== undefined) {
        const get = col.accessor ?? ((r: T) => (r as Record<string, unknown>)[col.id]);
        editor.begin(nav.focus, get(row));
        e.preventDefault();
        return;
      }
    }
    if (e.key === ' ' && selectionMode !== 'single') {
      selection.onRowClick(nav.focus.rowIndex, { ctrl: true, shift: e.shiftKey });
      e.preventDefault();
      return;
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a' && selectionMode !== 'single') {
      selection.selectAll();
      e.preventDefault();
      return;
    }
    nav.onKeyDown(e);
  };

  return (
    <div className="dt-root">
      <div aria-live="polite" className="dt-visually-hidden">
        {liveMessage}
      </div>
      <div
        ref={containerRef}
        role="grid"
        aria-label={ariaLabel}
        aria-rowcount={rowCount + 1}
        aria-colcount={visibleColumns.length}
        aria-multiselectable={selectionMode !== 'single'}
        className="dt-scroll"
        style={{ height, overflow: 'auto', position: 'relative' }}
        onScroll={onScroll}
        onKeyDown={handleKeyDown}
      >
        <div role="row" aria-rowindex={1} className="dt-header" style={{ display: 'grid', gridTemplateColumns: gridTemplate, position: 'sticky', top: 0, zIndex: 2 }}>
          {visibleColumns.map((col, ci) => {
            const sort = sorts.find((s) => s.columnId === col.id);
            return (
              <div
                key={col.id}
                role="columnheader"
                aria-colindex={ci + 1}
                aria-sort={sort ? (sort.direction === 'asc' ? 'ascending' : 'descending') : 'none'}
                draggable
                onDragStart={(e) => e.dataTransfer.setData('text/dt-col', String(ci))}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  const from = Number(e.dataTransfer.getData('text/dt-col'));
                  if (!Number.isNaN(from)) moveColumn(from, ci);
                }}
                className="dt-headercell"
              >
                <button
                  type="button"
                  className="dt-sortbutton"
                  disabled={col.sortable === false}
                  onClick={(e) => onHeaderClick(col.id, e.shiftKey)}
                >
                  {col.header}
                  {sort && <span aria-hidden="true">{sort.direction === 'asc' ? ' ▲' : ' ▼'}</span>}
                </button>
                {col.filterable !== false && (
                  <input
                    aria-label={`Filter ${col.header}`}
                    className="dt-filterinput"
                    onChange={(e) =>
                      setFilters((fs) => [
                        ...fs.filter((f) => f.columnId !== col.id),
                        ...(e.target.value ? [{ columnId: col.id, operator: 'contains' as const, value: e.target.value }] : []),
                      ])
                    }
                  />
                )}
                {col.resizable !== false && (
                  <span
                    role="separator"
                    aria-orientation="vertical"
                    aria-label={`Resize ${col.header}`}
                    tabIndex={0}
                    className="dt-resizer"
                    onKeyDown={(e) => {
                      if (e.key === 'ArrowLeft') resizeColumn(col.id, -10);
                      if (e.key === 'ArrowRight') resizeColumn(col.id, 10);
                    }}
                    onPointerDown={(e) => {
                      const startX = e.clientX;
                      const move = (ev: PointerEvent) => resizeColumn(col.id, ev.clientX - startX);
                      const up = () => {
                        window.removeEventListener('pointermove', move);
                        window.removeEventListener('pointerup', up);
                      };
                      window.addEventListener('pointermove', move);
                      window.addEventListener('pointerup', up);
                    }}
                  />
                )}
              </div>
            );
          })}
        </div>

        <div style={{ height: vw.totalHeight, position: 'relative' }}>
          <div style={{ transform: `translateY(${vw.offsetY}px)` }}>
            {Array.from({ length: vw.endIndex - vw.startIndex }, (_, k) => {
              const vi = vw.startIndex + k;
              const row = rowAt(vi);
              if (row === undefined) return null;
              const key = rowKey(row);
              const isSelected = selection.state.selected.has(key);
              return (
                <div
                  key={key}
                  role="row"
                  aria-rowindex={vi + 2}
                  aria-selected={isSelected}
                  className={isSelected ? 'dt-row dt-row--selected' : 'dt-row'}
                  style={{ display: 'grid', gridTemplateColumns: gridTemplate, height: rowHeight }}
                  onClick={(e) => selection.onRowClick(vi, { ctrl: e.ctrlKey || e.metaKey, shift: e.shiftKey })}
                >
                  {visibleColumns.map((col, ci) => {
                    const get = col.accessor ?? ((r: T) => (r as Record<string, unknown>)[col.id]);
                    const value = get(row);
                    const isFocused = nav.focus.rowIndex === vi && nav.focus.colIndex === ci;
                    const isEditing =
                      editor.edit.cell?.rowIndex === vi && editor.edit.cell?.colIndex === ci;
                    return (
                      <div
                        key={col.id}
                        role="gridcell"
                        aria-colindex={ci + 1}
                        tabIndex={isFocused ? 0 : -1}
                        className={isFocused ? 'dt-cell dt-cell--focus' : 'dt-cell'}
                        style={{ textAlign: col.align ?? 'left' }}
                        onDoubleClick={() => col.editable && editor.begin({ rowIndex: vi, colIndex: ci }, value)}
                      >
                        {isEditing ? (
                          <input
                            autoFocus
                            aria-label={`Edit ${col.header}`}
                            aria-invalid={Boolean(editor.edit.error)}
                            defaultValue={String(editor.edit.draft ?? '')}
                            onChange={(e) => editor.update(e.target.value)}
                            onBlur={() => editor.commit()}
                          />
                        ) : col.renderCell ? (
                          col.renderCell(value, row)
                        ) : (
                          String(value ?? '')
                        )}
                        {isSelected && ci === 0 && <span aria-hidden="true" className="dt-checkmark">✓</span>}
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

export default DataTable;
