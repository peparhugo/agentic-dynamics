import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent as ReactPointerEvent } from 'react';
import { CheckIcon, SortIcon } from './icons';
import type { CellValue, Column, DataRow, SelectionMode, SortRule } from './types';

const ROW_HEIGHT = 42;
const HEADER_HEIGHT = 43;
const OVERSCAN = 8;

interface DataGridProps {
  rows: DataRow[];
  columns: Column<DataRow>[];
  sortRules: SortRule[];
  onSortChange: (rules: SortRule[]) => void;
  selectionMode: SelectionMode;
  onSelectionCountChange?: (count: number) => void;
  loading?: boolean;
}

function displayValue(column: Column<DataRow>, value: CellValue, row: DataRow) {
  return column.format ? column.format(value, row) : String(value ?? '');
}

export function DataGrid({ rows, columns: initialColumns, sortRules, onSortChange, selectionMode, onSelectionCountChange, loading }: DataGridProps) {
  const [columnOrder, setColumnOrder] = useState(() => initialColumns.map((column) => column.id));
  const [widths, setWidths] = useState<Record<string, number>>(() => Object.fromEntries(initialColumns.map((column) => [column.id, column.width])));
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [anchor, setAnchor] = useState<number | null>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(500);
  const [activeCell, setActiveCell] = useState({ row: 0, column: 0 });
  const [editing, setEditing] = useState<{ rowId: number; columnId: string } | null>(null);
  const [edits, setEdits] = useState<Map<string, CellValue>>(new Map());
  const [dragging, setDragging] = useState<string | null>(null);
  const scrollerRef = useRef<HTMLDivElement>(null);
  const orderedColumns = columnOrder.map((id) => initialColumns.find((column) => column.id === id)!).filter(Boolean);
  const gridWidth = 44 + orderedColumns.reduce((sum, column) => sum + widths[column.id], 0);
  const startIndex = Math.max(0, Math.floor((scrollTop - HEADER_HEIGHT) / ROW_HEIGHT) - OVERSCAN);
  const visibleCount = Math.ceil(viewportHeight / ROW_HEIGHT) + OVERSCAN * 2;
  const endIndex = Math.min(rows.length, startIndex + visibleCount);
  const visibleRows = rows.slice(startIndex, endIndex);

  useEffect(() => {
    const element = scrollerRef.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => setViewportHeight(entry.contentRect.height));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    setSelected(new Set());
    setAnchor(null);
  }, [selectionMode]);

  const valueFor = (row: DataRow, column: Column<DataRow>) => {
    const key = `${row.id}:${column.id}`;
    return edits.has(key) ? edits.get(key)! : column.value(row);
  };

  const updateSelection = (rowIndex: number, additive = false, range = false) => {
    const rowId = rows[rowIndex]?.id;
    if (rowId === undefined) return;
    setSelected((current) => {
      let next: Set<number>;
      if ((range || selectionMode === 'range') && anchor !== null) {
        next = additive ? new Set(current) : new Set<number>();
        const [from, to] = [anchor, rowIndex].sort((a, b) => a - b);
        rows.slice(from, to + 1).forEach((row) => next.add(row.id));
      } else if (selectionMode === 'single') {
        next = current.has(rowId) ? new Set<number>() : new Set([rowId]);
      } else {
        next = new Set(current);
        next.has(rowId) ? next.delete(rowId) : next.add(rowId);
      }
      onSelectionCountChange?.(next.size);
      return next;
    });
    setAnchor(rowIndex);
  };

  const toggleAllVisible = () => {
    setSelected((current) => {
      const allSelected = rows.length > 0 && rows.every((row) => current.has(row.id));
      const next = allSelected ? new Set<number>() : new Set(rows.map((row) => row.id));
      onSelectionCountChange?.(next.size);
      return next;
    });
  };

  const changeSort = (columnId: string, additive: boolean) => {
    const existing = sortRules.find((rule) => rule.columnId === columnId);
    let rules = additive ? sortRules.filter((rule) => rule.columnId !== columnId) : [];
    if (!existing) rules = [...rules, { columnId, direction: 'asc' }];
    else if (existing.direction === 'asc') rules = [...rules, { columnId, direction: 'desc' }];
    onSortChange(rules);
  };

  const beginResize = (event: ReactPointerEvent, columnId: string) => {
    event.preventDefault();
    event.stopPropagation();
    const startX = event.clientX;
    const startWidth = widths[columnId];
    const column = initialColumns.find((item) => item.id === columnId)!;
    const onMove = (moveEvent: PointerEvent) => setWidths((current) => ({ ...current, [columnId]: Math.max(column.minWidth ?? 80, startWidth + moveEvent.clientX - startX) }));
    const onUp = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  };

  const moveColumn = (targetId: string) => {
    if (!dragging || dragging === targetId) return;
    setColumnOrder((current) => {
      const next = current.filter((id) => id !== dragging);
      next.splice(next.indexOf(targetId), 0, dragging);
      return next;
    });
    setDragging(null);
  };

  const focusCell = (row: number, column: number) => {
    const nextRow = Math.max(0, Math.min(rows.length - 1, row));
    const nextColumn = Math.max(0, Math.min(orderedColumns.length - 1, column));
    setActiveCell({ row: nextRow, column: nextColumn });
    const scroller = scrollerRef.current;
    if (!scroller) return;
    const top = HEADER_HEIGHT + nextRow * ROW_HEIGHT;
    if (top < scroller.scrollTop + HEADER_HEIGHT) scroller.scrollTop = top - HEADER_HEIGHT;
    if (top + ROW_HEIGHT > scroller.scrollTop + scroller.clientHeight) scroller.scrollTop = top + ROW_HEIGHT - scroller.clientHeight;
    const left = 44 + orderedColumns.slice(0, nextColumn).reduce((sum, item) => sum + widths[item.id], 0);
    const right = left + widths[orderedColumns[nextColumn].id];
    if (left < scroller.scrollLeft + 44) scroller.scrollLeft = left - 44;
    if (right > scroller.scrollLeft + scroller.clientWidth) scroller.scrollLeft = right - scroller.clientWidth;
    requestAnimationFrame(() => scroller.querySelector<HTMLElement>(`[data-cell="${nextRow}:${nextColumn}"]`)?.focus());
  };

  const onCellKeyDown = (event: KeyboardEvent, rowIndex: number, columnIndex: number, column: Column<DataRow>) => {
    if (editing) return;
    const movement: Record<string, [number, number]> = {
      ArrowUp: [rowIndex - 1, columnIndex], ArrowDown: [rowIndex + 1, columnIndex],
      ArrowLeft: [rowIndex, columnIndex - 1], ArrowRight: [rowIndex, columnIndex + 1],
      Home: [rowIndex, 0], End: [rowIndex, orderedColumns.length - 1],
    };
    if (movement[event.key]) {
      event.preventDefault();
      focusCell(...movement[event.key]);
    } else if (event.key === ' ' && event.shiftKey) {
      event.preventDefault();
      updateSelection(rowIndex, event.ctrlKey || event.metaKey, true);
    } else if (event.key === ' ') {
      event.preventDefault();
      updateSelection(rowIndex, event.ctrlKey || event.metaKey);
    } else if (event.key === 'Enter' && column.editable) {
      event.preventDefault();
      setEditing({ rowId: rows[rowIndex].id, columnId: column.id });
    }
  };

  const commitEdit = (rowId: number, columnId: string, value: string) => {
    const column = initialColumns.find((item) => item.id === columnId)!;
    const original = column.value(rows.find((row) => row.id === rowId)!);
    setEdits((current) => new Map(current).set(`${rowId}:${columnId}`, typeof original === 'number' ? Number(value) : value));
    setEditing(null);
  };

  return (
    <div className="grid-shell">
      <div
        className="grid-scroller"
        ref={scrollerRef}
        onScroll={(event) => setScrollTop(event.currentTarget.scrollTop)}
        role="grid"
        aria-label="Customer accounts"
        aria-rowcount={rows.length + 1}
        aria-colcount={orderedColumns.length + 1}
        aria-multiselectable={selectionMode !== 'single'}
        aria-busy={loading}
      >
        <div className="grid-head" role="row" style={{ width: gridWidth }}>
          <div className="select-head" role="columnheader">
            <button className={`checkbox ${selected.size > 0 ? 'checked' : ''}`} onClick={toggleAllVisible} aria-label={selected.size ? 'Clear row selection' : 'Select all filtered rows'} aria-pressed={selected.size > 0}>
              {selected.size > 0 && <CheckIcon />}
            </button>
          </div>
          {orderedColumns.map((column) => {
            const sortIndex = sortRules.findIndex((rule) => rule.columnId === column.id);
            const rule = sortRules[sortIndex];
            return (
              <div
                className={`column-head ${dragging === column.id ? 'dragging' : ''}`}
                role="columnheader"
                aria-sort={rule ? (rule.direction === 'asc' ? 'ascending' : 'descending') : 'none'}
                style={{ width: widths[column.id], textAlign: column.align ?? 'left' }}
                draggable
                onDragStart={() => setDragging(column.id)}
                onDragOver={(event) => event.preventDefault()}
                onDrop={() => moveColumn(column.id)}
              >
                <button className="sort-button" onClick={(event) => changeSort(column.id, event.shiftKey)} title="Sort; hold Shift for multi-sort">
                  <span>{column.label}</span>
                  {rule ? <span className={`sort-direction ${rule.direction}`}>↑</span> : <SortIcon />}
                  {sortRules.length > 1 && rule && <span className="sort-rank">{sortIndex + 1}</span>}
                </button>
                <button className="resize-handle" onPointerDown={(event) => beginResize(event, column.id)} aria-label={`Resize ${column.label} column`} />
              </div>
            );
          })}
        </div>

        <div className="virtual-space" style={{ height: rows.length * ROW_HEIGHT, width: gridWidth }}>
          {visibleRows.map((row, visibleIndex) => {
            const rowIndex = startIndex + visibleIndex;
            const isSelected = selected.has(row.id);
            return (
              <div
                className={`grid-row ${isSelected ? 'selected' : ''}`}
                role="row"
                aria-rowindex={rowIndex + 2}
                aria-selected={isSelected}
                key={row.id}
                style={{ width: gridWidth, height: ROW_HEIGHT, transform: `translateY(${rowIndex * ROW_HEIGHT}px)` }}
                onClick={(event) => updateSelection(rowIndex, event.ctrlKey || event.metaKey, event.shiftKey)}
              >
                <div className="select-cell" role="gridcell">
                  <span className={`checkbox ${isSelected ? 'checked' : ''}`}>{isSelected && <CheckIcon />}</span>
                </div>
                {orderedColumns.map((column, columnIndex) => {
                  const value = valueFor(row, column);
                  const isEditing = editing?.rowId === row.id && editing.columnId === column.id;
                  return (
                    <div
                      className={`grid-cell align-${column.align ?? 'left'} ${activeCell.row === rowIndex && activeCell.column === columnIndex ? 'active' : ''}`}
                      role="gridcell"
                      aria-colindex={columnIndex + 2}
                      style={{ width: widths[column.id] }}
                      key={column.id}
                      data-cell={`${rowIndex}:${columnIndex}`}
                      tabIndex={activeCell.row === rowIndex && activeCell.column === columnIndex ? 0 : -1}
                      onFocus={() => setActiveCell({ row: rowIndex, column: columnIndex })}
                      onKeyDown={(event) => onCellKeyDown(event, rowIndex, columnIndex, column)}
                      onDoubleClick={(event) => { event.stopPropagation(); if (column.editable) setEditing({ rowId: row.id, columnId: column.id }); }}
                    >
                      {isEditing ? (
                        <input
                          className="cell-editor"
                          aria-label={`Edit ${column.label}`}
                          defaultValue={String(value ?? '')}
                          autoFocus
                          onClick={(event) => event.stopPropagation()}
                          onBlur={(event) => commitEdit(row.id, column.id, event.currentTarget.value)}
                          onKeyDown={(event) => {
                            event.stopPropagation();
                            if (event.key === 'Enter') commitEdit(row.id, column.id, event.currentTarget.value);
                            if (event.key === 'Escape') setEditing(null);
                          }}
                        />
                      ) : column.id === 'status' ? (
                        <span className={`status status-${String(value).toLowerCase().replace(' ', '-')}`}><i />{String(value)}</span>
                      ) : column.id === 'health' ? (
                        <span className="health-cell"><span>{value}%</span><i><b style={{ width: `${value}%` }} /></i></span>
                      ) : (
                        <span className="cell-text" title={displayValue(column, value, row)}>{displayValue(column, value, row)}</span>
                      )}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
        {loading && <div className="loading-veil"><span /><strong>Querying server</strong></div>}
      </div>
      <div className="grid-footer">
        <span><strong>{rows.length.toLocaleString()}</strong> matching rows</span>
        <span className="virtual-note"><i /> Virtualized · {visibleRows.length} rows rendered</span>
        <span className="key-hint"><kbd>↑</kbd><kbd>↓</kbd><kbd>←</kbd><kbd>→</kbd> Navigate <kbd>Enter</kbd> Edit <kbd>Space</kbd> Select</span>
      </div>
    </div>
  );
}
