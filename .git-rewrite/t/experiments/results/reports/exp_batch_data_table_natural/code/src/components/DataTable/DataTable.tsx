import React, { useMemo, useCallback, useRef, useImperativeHandle, forwardRef } from 'react';
import type {
  DataTableProps,
  ColumnDef,
  TableBodyRef,
} from './types';
import { useVirtualScroll } from './useVirtualScroll';
import { useSorting } from './useSorting';
import { useFiltering } from './useFiltering';
import { useSelection } from './useSelection';
import { useColumnResize } from './useColumnResize';
import { useColumnReorder } from './useColumnReorder';
import { useKeyboardNavigation } from './useKeyboardNavigation';
import { useInlineEdit } from './useInlineEdit';
import { stableSort, clientFilter, getCellValue, exportToCSV, exportToExcel } from './utils';
import './styles.css';

const DEFAULT_ROW_HEIGHT = 36;
const DEFAULT_HEADER_HEIGHT = 40;
const DEFAULT_FILTER_HEIGHT = 36;
const DEFAULT_OVERSCAN = 10;

function DataTableInner<T extends Record<string, any>>(
  props: DataTableProps<T>,
  ref: React.ForwardedRef<TableBodyRef>
) {
  const {
    data,
    columns: columnsProp,
    rowHeight = DEFAULT_ROW_HEIGHT,
    overscan = DEFAULT_OVERSCAN,
    dataSource = 'client',
    selectionMode = 'multi',
    selectedIds: externalSelected,
    onSelectionChange,
    idAccessor: idAccessorProp,
    className,
    height: heightProp,
    headerHeight = DEFAULT_HEADER_HEIGHT,
    filterHeight = DEFAULT_FILTER_HEIGHT,
    onSortChange,
    onFilterChange,
    onColumnOrderChange,
    onColumnResize,
    onCellEdit,
    onExport,
    serverSort,
    serverFilters,
    serverTotalRows,
    loading = false,
    locale = 'en-US',
    ariaLabel = 'Data Table',
  } = props;

  const containerRef = useRef<HTMLDivElement>(null);
  const tableRef = useRef<HTMLTableElement>(null);

  const [columnOrder, setColumnOrder] = React.useState<string[]>(() => columnsProp.map((c) => c.id));
  const [containerHeight, setContainerHeight] = React.useState(600);

  const idAccessor = useCallback(
    (index: number): string => {
      if (idAccessorProp) {
        const row = data[index];
        if (typeof idAccessorProp === 'function') return idAccessorProp(row);
        return String(row[idAccessorProp] ?? index);
      }
      return String(index);
    },
    [data, idAccessorProp]
  );

  const columnMap = useMemo(() => {
    const map = new Map<string, ColumnDef<T>>();
    columnsProp.forEach((c) => map.set(c.id, c));
    return map;
  }, [columnsProp]);

  const orderedColumns = useMemo(() => {
    return columnOrder.map((id) => columnMap.get(id)!).filter(Boolean);
  }, [columnOrder, columnMap]);

  const {
    sortRules,
    sortMap,
    toggleSort,
    clearSort,
  } = useSorting({
    externalSort: dataSource === 'server' ? serverSort : undefined,
    onSortChange,
  });

  const {
    filterRules,
    setFilter,
    clearFilters,
  } = useFiltering({
    externalFilters: dataSource === 'server' ? serverFilters : undefined,
    onFilterChange,
  });

  const processedData = useMemo(() => {
    if (dataSource === 'server') return data;
    let result = clientFilter(data, filterRules, columnsProp);
    result = stableSort(result, sortRules, columnsProp);
    return result;
  }, [data, filterRules, sortRules, columnsProp, dataSource]);

  const totalRows = dataSource === 'server' ? (serverTotalRows ?? data.length) : processedData.length;

  const containerHeightCalc = useMemo(() => {
    if (typeof heightProp === 'number') return heightProp;
    if (heightProp) {
      try {
        const parsed = parseFloat(heightProp);
        return isNaN(parsed) ? 600 : parsed;
      } catch {
        return 600;
      }
    }
    return containerHeight;
  }, [heightProp, containerHeight]);

  React.useEffect(() => {
    if (!heightProp && containerRef.current) {
      const observer = new ResizeObserver((entries) => {
        for (const entry of entries) {
          setContainerHeight(entry.contentRect.height);
        }
      });
      observer.observe(containerRef.current);
      return () => observer.disconnect();
    }
  }, [heightProp]);

  const {
    startIndex,
    endIndex,
    visibleRows,
    totalHeight,
    offsetY,
    scrollTop,
    containerRef: virtualContainerRef,
    scrollToIndex,
  } = useVirtualScroll({
    totalRows,
    rowHeight,
    overscan,
    containerHeight: containerHeightCalc - headerHeight - filterHeight - 2,
  });

  const {
    selectedIds,
    isSelected,
    toggleRow,
    selectAll,
    clearSelection,
  } = useSelection({
    mode: selectionMode,
    dataLength: totalRows,
    idAccessor,
    externalSelected,
    onSelectionChange,
  });

  const {
    columnWidths,
    resizing,
    resizeStart,
    resizeMove,
    resizeEnd,
    updateColumnWidths,
  } = useColumnResize({ columns: columnsProp, onColumnResize });

  React.useEffect(() => {
    updateColumnWidths(columnsProp);
  }, [columnsProp, updateColumnWidths]);

  const {
    draggedColumn,
    dropTarget,
    handleDragStart,
    handleDragOver,
    handleDrop,
    handleDragEnd,
  } = useColumnReorder({
    columnIds: columnOrder,
    onColumnOrderChange: (ids) => {
      setColumnOrder(ids);
      onColumnOrderChange?.(ids);
    },
  });

  const {
    editingCell,
    startEdit,
    commitEdit,
    cancelEdit,
    isEditing,
  } = useInlineEdit({ onCellEdit });

  const { handleKeyDown, setFocusedCell } = useKeyboardNavigation({
    totalRows,
    totalCols: orderedColumns.length,
    onCellEdit: (rowIdx, colIdx) => {
      const rowData = processedData[rowIdx];
      const col = orderedColumns[colIdx];
      if (col && col.editable) {
        startEdit(rowIdx, col.id);
      }
    },
    onSelectRow: (rowIdx, event) => {
      toggleRow(rowIdx, event as any);
    },
    onSelectAll: selectAll,
    scrollToRow: scrollToIndex,
    containerRef,
  });

  React.useEffect(() => {
    if (resizing) {
      const handleMouseMove = (e: MouseEvent) => resizeMove(e);
      const handleMouseUp = () => resizeEnd();
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
      return () => {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      };
    }
  }, [resizing, resizeMove, resizeEnd]);

  useImperativeHandle(
    ref,
    () => ({
      scrollToRow: scrollToIndex,
      scrollToTop: () => scrollToIndex(0),
      getScrollPosition: () => scrollTop,
      focusCell: (rowIdx: number, colIdx: number) => {
        setFocusedCell(rowIdx, colIdx);
      },
    }),
    [scrollToIndex, scrollTop, setFocusedCell]
  );

  const handleExportCSV = useCallback(() => {
    if (onExport) {
      onExport('csv', processedData, orderedColumns);
    } else {
      exportToCSV(processedData, orderedColumns);
    }
  }, [onExport, processedData, orderedColumns]);

  const handleExportExcel = useCallback(() => {
    if (onExport) {
      onExport('excel', processedData, orderedColumns);
    } else {
      exportToExcel(processedData, orderedColumns);
    }
  }, [onExport, processedData, orderedColumns]);

  const getSortIndicator = (columnId: string): string => {
    const dir = sortMap.get(columnId);
    if (!dir) return '\u2195';
    return dir === 'asc' ? '\u2191' : '\u2193';
  };

  const getSortTitle = (columnId: string): string => {
    const dir = sortMap.get(columnId);
    if (!dir) return 'Click to sort ascending';
    return dir === 'asc' ? 'Click to sort descending' : 'Click to remove sort';
  };

  return (
    <div
      className={`dt-container ${className ?? ''}`}
      role="grid"
      aria-label={ariaLabel}
      aria-rowcount={totalRows + 1}
      aria-colcount={orderedColumns.length}
      onKeyDown={handleKeyDown}
    >
      {loading && (
        <div className="dt-loading-overlay" role="alert" aria-busy="true">
          <div className="dt-spinner" />
        </div>
      )}

      <div className="dt-toolbar" role="toolbar" aria-label="Table toolbar">
        <div className="dt-toolbar-left">
          <span className="dt-row-count" aria-live="polite">
            {totalRows.toLocaleString(locale)} row{totalRows !== 1 ? 's' : ''}
            {selectedIds.size > 0 && ` (${selectedIds.size} selected)`}
          </span>
          {filterRules.length > 0 && (
            <button className="dt-btn dt-btn-sm" onClick={clearFilters} aria-label="Clear all filters">
              Clear Filters
            </button>
          )}
          {sortRules.length > 0 && (
            <button className="dt-btn dt-btn-sm" onClick={clearSort} aria-label="Clear all sorting">
              Clear Sort
            </button>
          )}
        </div>
        <div className="dt-toolbar-right">
          {selectionMode !== 'single' && totalRows > 0 && (
            <>
              <button className="dt-btn dt-btn-sm" onClick={selectAll} aria-label="Select all rows">
                Select All
              </button>
              <button className="dt-btn dt-btn-sm" onClick={clearSelection} aria-label="Clear selection">
                Clear
              </button>
            </>
          )}
          <button className="dt-btn dt-btn-sm" onClick={handleExportCSV} aria-label="Export to CSV">
            CSV
          </button>
          <button className="dt-btn dt-btn-sm" onClick={handleExportExcel} aria-label="Export to Excel">
            Excel
          </button>
        </div>
      </div>

      <div className="dt-table-wrapper" ref={containerRef}>
        <table
          ref={tableRef}
          className="dt-table"
          role="presentation"
          style={{ minWidth: orderedColumns.reduce((s, c) => s + (columnWidths[c.id] ?? c.width), 0) }}
        >
          <thead className="dt-thead">
            <tr className="dt-header-row dt-row-select" role="row" style={{ height: headerHeight }}>
              {(selectionMode === 'multi' || selectionMode === 'range') && (
                <th
                  className="dt-th dt-th-select"
                  style={{ width: 40 }}
                  role="columnheader"
                  aria-label="Select all"
                  scope="col"
                >
                  <input
                    type="checkbox"
                    checked={selectedIds.size > 0 && selectedIds.size === totalRows}
                    ref={(el) => {
                      if (el) el.indeterminate = selectedIds.size > 0 && selectedIds.size < totalRows;
                    }}
                    onChange={(e) => {
                      if (e.target.checked) selectAll();
                      else clearSelection();
                    }}
                    aria-label="Select all rows"
                  />
                </th>
              )}
              {orderedColumns.map((col, colIdx) => {
                const width = columnWidths[col.id] ?? col.width;
                const isDropBefore = dropTarget?.columnId === col.id && dropTarget?.position === 'before';
                const isDropAfter = dropTarget?.columnId === col.id && dropTarget?.position === 'after';
                return (
                  <th
                    key={col.id}
                    className={`dt-th ${draggedColumn === col.id ? 'dt-th-dragging' : ''} ${
                      isDropBefore ? 'dt-drop-before' : ''
                    } ${isDropAfter ? 'dt-drop-after' : ''}`}
                    style={{ width, minWidth: col.minWidth ?? 50, maxWidth: col.maxWidth }}
                    role="columnheader"
                    aria-sort={sortMap.has(col.id) ? (sortMap.get(col.id) === 'asc' ? 'ascending' : 'descending') : 'none'}
                    aria-label={`${col.header}${sortMap.has(col.id) ? ', sorted ' + sortMap.get(col.id) : ''}`}
                    scope="col"
                    draggable
                    onDragStart={(e) => handleDragStart(col.id, e)}
                    onDragOver={(e) => handleDragOver(col.id, e)}
                    onDrop={(e) => handleDrop(col.id, e)}
                    onDragEnd={handleDragEnd}
                  >
                    <div className="dt-th-content">
                      <span
                        className={`dt-header-text ${col.sortable !== false ? 'dt-sortable' : ''}`}
                        onClick={(e) => {
                          if (col.sortable !== false) {
                            toggleSort(col.id, e.ctrlKey || e.metaKey);
                          }
                        }}
                        title={col.sortable !== false ? getSortTitle(col.id) : undefined}
                        role={col.sortable !== false ? 'button' : undefined}
                        tabIndex={col.sortable !== false ? 0 : undefined}
                        onKeyDown={(e) => {
                          if ((e.key === 'Enter' || e.key === ' ') && col.sortable !== false) {
                            e.preventDefault();
                            toggleSort(col.id, e.ctrlKey || e.metaKey);
                          }
                        }}
                      >
                        {col.header}
                      </span>
                      {col.sortable !== false && (
                        <span className="dt-sort-indicator" aria-hidden="true">
                          {getSortIndicator(col.id)}
                        </span>
                      )}
                    </div>
                    {col.resizable !== false && (
                      <div
                        className="dt-resize-handle"
                        onMouseDown={(e) => resizeStart(col.id, e)}
                        role="separator"
                        aria-orientation="vertical"
                        aria-label={`Resize ${col.header} column`}
                        tabIndex={0}
                        onKeyDown={(e) => {
                          if (e.key === 'ArrowLeft') {
                            const newW = Math.max(col.minWidth ?? 50, (columnWidths[col.id] ?? col.width) - 10);
                            setColumnWidths();
                            onColumnResize?.(col.id, newW);
                          } else if (e.key === 'ArrowRight') {
                            const newW = Math.min(col.maxWidth ?? Infinity, (columnWidths[col.id] ?? col.width) + 10);
                            onColumnResize?.(col.id, newW);
                          }
                        }}
                      />
                    )}
                  </th>
                );
              })}
            </tr>

            {orderedColumns.some((c) => c.filterable !== false) && (
              <tr className="dt-filter-row" role="row" style={{ height: filterHeight }}>
                {(selectionMode === 'multi' || selectionMode === 'range') && (
                  <td className="dt-td dt-td-select" style={{ width: 40 }} />
                )}
                {orderedColumns.map((col) => (
                  <td
                    key={col.id}
                    className="dt-td dt-filter-cell"
                    style={{ width: columnWidths[col.id] ?? col.width }}
                  >
                    {col.filterable !== false && (
                      <input
                        className="dt-filter-input"
                        type="text"
                        placeholder={`Filter ${col.header}...`}
                        aria-label={`Filter by ${col.header}`}
                        value={filterRules.find((r) => r.columnId === col.id)?.value ?? ''}
                        onChange={(e) => setFilter(col.id, 'contains', e.target.value)}
                      />
                    )}
                  </td>
                ))}
              </tr>
            )}
          </thead>

          <tbody>
            <tr aria-hidden="true" style={{ height: offsetY }} />
            {visibleRows.map((rowIdx) => {
              const row = processedData[rowIdx];
              const selected = isSelected(rowIdx);
              const rowId = idAccessor(rowIdx);
              return (
                <tr
                  key={rowId}
                  className={`dt-row ${selected ? 'dt-row-selected' : ''} ${rowIdx % 2 === 1 ? 'dt-row-striped' : ''}`}
                  role="row"
                  aria-selected={selected}
                  aria-rowindex={rowIdx + 2}
                  style={{ height: rowHeight }}
                  onClick={(e) => toggleRow(rowIdx, e)}
                >
                  {(selectionMode === 'multi' || selectionMode === 'range') && (
                    <td className="dt-td dt-td-select" style={{ width: 40 }} role="gridcell">
                      {selectionMode === 'single' ? null : (
                        <input
                          type="checkbox"
                          checked={selected}
                          onChange={() => toggleRow(rowIdx)}
                          aria-label={`Select row ${rowIdx + 1}`}
                          tabIndex={-1}
                        />
                      )}
                    </td>
                  )}
                  {orderedColumns.map((col, colIdx) => {
                    const cellValue = getCellValue(row, col);
                    const editing = isEditing(rowIdx, col.id);
                    const width = columnWidths[col.id] ?? col.width;
                    return (
                      <td
                        key={col.id}
                        className={`dt-td ${editing ? 'dt-td-editing' : ''}`}
                        style={{ width, maxWidth: width }}
                        role="gridcell"
                        data-row-index={rowIdx}
                        data-col-index={colIdx}
                        tabIndex={-1}
                        onDoubleClick={() => {
                          if (col.editable) startEdit(rowIdx, col.id);
                        }}
                      >
                        {editing ? (
                          <InlineEditCell
                            value={cellValue}
                            row={row}
                            rowIndex={rowIdx}
                            column={col}
                            onCommit={commitEdit}
                            onCancel={cancelEdit}
                          />
                        ) : col.cell ? (
                          col.cell(row)
                        ) : (
                          <span className="dt-cell-value">{cellValue ?? ''}</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>

        <div aria-hidden="true" style={{ height: totalHeight - offsetY - visibleRows.length * rowHeight }} />
      </div>

      {processingData.length === 0 && !loading && (
        <div className="dt-empty" role="status">
          No data to display
        </div>
      )}
    </div>
  );
}

interface InlineEditCellProps<T = any> {
  value: any;
  row: T;
  rowIndex: number;
  column: ColumnDef<T>;
  onCommit: (value: any) => void;
  onCancel: () => void;
}

function InlineEditCell<T>({ value, row, rowIndex, column, onCommit, onCancel }: InlineEditCellProps<T>) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [editValue, setEditValue] = React.useState(value ?? '');

  React.useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  if (column.editor) {
    return <>{column.editor({ value: editValue, row, rowIndex, column, onCommit, onCancel })}</>;
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      onCommit(editValue);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      onCancel();
    } else if (e.key === 'Tab') {
      e.preventDefault();
      onCommit(editValue);
    }
  };

  return (
    <input
      ref={inputRef}
      className="dt-inline-edit-input"
      value={editValue}
      onChange={(e) => setEditValue(e.target.value)}
      onKeyDown={handleKeyDown}
      onBlur={() => onCommit(editValue)}
      aria-label={`Edit ${column.header}`}
    />
  );
}

export const DataTable = forwardRef(DataTableInner) as <T extends Record<string, any>>(
  props: DataTableProps<T> & { ref?: React.ForwardedRef<TableBodyRef> }
) => React.ReactElement;
