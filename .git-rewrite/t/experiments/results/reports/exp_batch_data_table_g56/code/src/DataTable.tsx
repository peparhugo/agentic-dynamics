import {
  startTransition,
  useDeferredValue,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from "react";
import "./DataTable.css";

export type SortDirection = "asc" | "desc";

export interface SortDescriptor {
  columnId: string;
  direction: SortDirection;
}

export interface DataColumn<T> {
  id: string;
  header: string;
  accessor?: keyof T | ((row: T) => unknown);
  width?: number;
  minWidth?: number;
  maxWidth?: number;
  sortable?: boolean;
  filterable?: boolean;
  editable?: boolean;
  align?: "left" | "center" | "right";
  render?: (value: unknown, row: T) => ReactNode;
  parse?: (value: string, row: T) => unknown;
  compare?: (left: T, right: T) => number;
}

export interface DataTableProps<T> {
  rows: T[];
  columns: DataColumn<T>[];
  rowKey: keyof T | ((row: T) => string | number);
  height?: number;
  rowHeight?: number;
  overscan?: number;
  ariaLabel?: string;
  totalRowCount?: number;
  sortMode?: "client" | "server";
  filterMode?: "client" | "server";
  selectionMode?: "none" | "single" | "multi";
  selectedRowIds?: ReadonlySet<string | number>;
  onSelectionChange?: (ids: Set<string | number>) => void;
  onSortChange?: (sorts: SortDescriptor[]) => void;
  onFilterChange?: (filters: Record<string, string>) => void;
  onRowUpdate?: (row: T, columnId: string, value: unknown) => void;
  onColumnOrderChange?: (columnIds: string[]) => void;
}

const SELECT_WIDTH = 44;
const HEADER_HEIGHT = 74;

function escapeCsv(value: unknown): string {
  const text = value == null ? "" : String(value);
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function escapeHtml(value: unknown): string {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function download(contents: string, type: string, filename: string): void {
  const url = URL.createObjectURL(new Blob([contents], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function DataTable<T>({
  rows,
  columns,
  rowKey,
  height = 620,
  rowHeight = 42,
  overscan = 8,
  ariaLabel = "Data table",
  totalRowCount,
  sortMode = "client",
  filterMode = "client",
  selectionMode = "multi",
  selectedRowIds,
  onSelectionChange,
  onSortChange,
  onFilterChange,
  onRowUpdate,
  onColumnOrderChange,
}: DataTableProps<T>) {
  const instanceId = useId();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(height);
  const [columnOrder, setColumnOrder] = useState(() => columns.map((column) => column.id));
  const [widths, setWidths] = useState<Record<string, number>>(() =>
    Object.fromEntries(columns.map((column) => [column.id, column.width ?? 180])),
  );
  const [sorts, setSorts] = useState<SortDescriptor[]>([]);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const deferredFilters = useDeferredValue(filters);
  const [internalSelection, setInternalSelection] = useState<Set<string | number>>(new Set());
  const selection = selectedRowIds ?? internalSelection;
  const [selectionAnchor, setSelectionAnchor] = useState<number | null>(null);
  const [focusedCell, setFocusedCell] = useState({ row: 0, column: 0 });
  const [editing, setEditing] = useState<{
    rowId: string | number;
    columnId: string;
    value: string;
  } | null>(null);
  const [draggedColumn, setDraggedColumn] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");

  useEffect(() => {
    setColumnOrder((current) => {
      const valid = current.filter((id) => columns.some((column) => column.id === id));
      const added = columns.map((column) => column.id).filter((id) => !valid.includes(id));
      return [...valid, ...added];
    });
    setWidths((current) => ({
      ...Object.fromEntries(columns.map((column) => [column.id, current[column.id] ?? column.width ?? 180])),
    }));
  }, [columns]);

  useEffect(() => {
    if (filterMode !== "server") return;
    const timeout = window.setTimeout(() => onFilterChange?.(deferredFilters), 250);
    return () => window.clearTimeout(timeout);
  }, [deferredFilters, filterMode, onFilterChange]);

  useEffect(() => {
    const viewport = scrollRef.current;
    if (!viewport) return;
    const observer = new ResizeObserver(([entry]) => setViewportHeight(entry.contentRect.height));
    observer.observe(viewport);
    return () => observer.disconnect();
  }, []);

  const orderedColumns = useMemo(
    () =>
      columnOrder
        .map((id) => columns.find((column) => column.id === id))
        .filter((column): column is DataColumn<T> => Boolean(column)),
    [columnOrder, columns],
  );

  const getValue = (row: T, column: DataColumn<T>): unknown => {
    if (typeof column.accessor === "function") return column.accessor(row);
    if (column.accessor != null) return row[column.accessor];
    return (row as Record<string, unknown>)[column.id];
  };

  const getRowId = (row: T): string | number =>
    typeof rowKey === "function" ? rowKey(row) : (row[rowKey] as string | number);

  const processedRows = useMemo(() => {
    let result = [...rows];
    if (filterMode === "client") {
      result = result.filter((row) =>
        Object.entries(deferredFilters).every(([columnId, query]) => {
          if (!query) return true;
          const column = columns.find((candidate) => candidate.id === columnId);
          return column
            ? String(getValue(row, column) ?? "").toLocaleLowerCase().includes(query.toLocaleLowerCase())
            : true;
        }),
      );
    }
    if (sortMode === "client" && sorts.length) {
      result.sort((left, right) => {
        for (const sort of sorts) {
          const column = columns.find((candidate) => candidate.id === sort.columnId);
          if (!column) continue;
          const compared = column.compare
            ? column.compare(left, right)
            : String(getValue(left, column) ?? "").localeCompare(
                String(getValue(right, column) ?? ""),
                undefined,
                { numeric: true, sensitivity: "base" },
              );
          if (compared) return sort.direction === "asc" ? compared : -compared;
        }
        return 0;
      });
    }
    return result;
  }, [rows, columns, deferredFilters, filterMode, sorts, sortMode]);

  const hasSelection = selectionMode !== "none";
  const template = `${hasSelection ? `${SELECT_WIDTH}px ` : ""}${orderedColumns
    .map((column) => `${widths[column.id] ?? column.width ?? 180}px`)
    .join(" ")}`;
  const totalWidth = (hasSelection ? SELECT_WIDTH : 0) + orderedColumns.reduce(
    (sum, column) => sum + (widths[column.id] ?? column.width ?? 180),
    0,
  );
  const firstVisible = Math.max(0, Math.floor(scrollTop / rowHeight) - overscan);
  const visibleCount = Math.ceil(Math.max(0, viewportHeight - HEADER_HEIGHT) / rowHeight) + overscan * 2;
  const lastVisible = Math.min(processedRows.length, firstVisible + visibleCount);
  const visibleRows = processedRows.slice(firstVisible, lastVisible);

  const setSelection = (next: Set<string | number>): void => {
    if (!selectedRowIds) setInternalSelection(next);
    onSelectionChange?.(next);
    setAnnouncement(`${next.size} row${next.size === 1 ? "" : "s"} selected`);
  };

  const selectRow = (index: number, range: boolean): void => {
    if (selectionMode === "none") return;
    const id = getRowId(processedRows[index]);
    if (selectionMode === "single") {
      setSelection(new Set(selection.has(id) && !range ? [] : [id]));
    } else if (range && selectionAnchor != null) {
      const next = new Set(selection);
      const start = Math.min(selectionAnchor, index);
      const end = Math.max(selectionAnchor, index);
      for (let position = start; position <= end; position += 1) {
        next.add(getRowId(processedRows[position]));
      }
      setSelection(next);
    } else {
      const next = new Set(selection);
      next.has(id) ? next.delete(id) : next.add(id);
      setSelection(next);
      setSelectionAnchor(index);
    }
  };

  const toggleSort = (columnId: string, additive: boolean): void => {
    const current = sorts.find((sort) => sort.columnId === columnId);
    const replacement = !current
      ? { columnId, direction: "asc" as const }
      : current.direction === "asc"
        ? { columnId, direction: "desc" as const }
        : null;
    const next = additive ? sorts.filter((sort) => sort.columnId !== columnId) : [];
    if (replacement) next.push(replacement);
    setSorts(next);
    onSortChange?.(next);
    setAnnouncement(
      replacement ? `${columnId} sorted ${replacement.direction}` : `${columnId} sorting cleared`,
    );
  };

  const reorderColumn = (source: string, target: string): void => {
    if (source === target) return;
    const next = [...columnOrder];
    const sourceIndex = next.indexOf(source);
    const targetIndex = next.indexOf(target);
    next.splice(sourceIndex, 1);
    next.splice(targetIndex, 0, source);
    setColumnOrder(next);
    onColumnOrderChange?.(next);
    setAnnouncement(`${source} column moved to position ${targetIndex + 1}`);
  };

  const moveColumn = (columnId: string, delta: number): void => {
    const index = columnOrder.indexOf(columnId);
    const target = Math.max(0, Math.min(columnOrder.length - 1, index + delta));
    if (target !== index) reorderColumn(columnId, columnOrder[target]);
  };

  const beginResize = (event: React.PointerEvent, column: DataColumn<T>): void => {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = widths[column.id] ?? column.width ?? 180;
    const move = (pointerEvent: PointerEvent) => {
      const nextWidth = Math.max(
        column.minWidth ?? 80,
        Math.min(column.maxWidth ?? 600, startWidth + pointerEvent.clientX - startX),
      );
      setWidths((current) => ({ ...current, [column.id]: nextWidth }));
    };
    const end = () => {
      document.removeEventListener("pointermove", move);
      document.removeEventListener("pointerup", end);
    };
    document.addEventListener("pointermove", move);
    document.addEventListener("pointerup", end);
  };

  const beginEdit = (row: T, column: DataColumn<T>): void => {
    if (!column.editable) return;
    setEditing({ rowId: getRowId(row), columnId: column.id, value: String(getValue(row, column) ?? "") });
  };

  const commitEdit = (row: T, column: DataColumn<T>): void => {
    if (!editing) return;
    const value = column.parse ? column.parse(editing.value, row) : editing.value;
    onRowUpdate?.(row, column.id, value);
    setEditing(null);
    setAnnouncement(`${column.header} updated`);
  };

  const focusCell = (row: number, column: number): void => {
    const nextRow = Math.max(0, Math.min(processedRows.length - 1, row));
    const nextColumn = Math.max(0, Math.min(orderedColumns.length - 1, column));
    setFocusedCell({ row: nextRow, column: nextColumn });
    const viewport = scrollRef.current;
    if (viewport) {
      const top = nextRow * rowHeight;
      const visibleTop = viewport.scrollTop;
      const visibleBottom = visibleTop + viewport.clientHeight - HEADER_HEIGHT;
      if (top < visibleTop) viewport.scrollTop = top;
      else if (top + rowHeight > visibleBottom) viewport.scrollTop = top - viewport.clientHeight + HEADER_HEIGHT + rowHeight;
    }
    window.requestAnimationFrame(() => {
      document
        .querySelector<HTMLElement>(`[data-grid="${CSS.escape(instanceId)}"][data-row="${nextRow}"][data-column="${nextColumn}"]`)
        ?.focus();
    });
  };

  const onCellKeyDown = (
    event: ReactKeyboardEvent,
    rowIndex: number,
    columnIndex: number,
    row: T,
    column: DataColumn<T>,
  ): void => {
    const page = Math.max(1, Math.floor((viewportHeight - HEADER_HEIGHT) / rowHeight));
    const targets: Partial<Record<string, [number, number]>> = {
      ArrowUp: [rowIndex - 1, columnIndex],
      ArrowDown: [rowIndex + 1, columnIndex],
      ArrowLeft: [rowIndex, columnIndex - 1],
      ArrowRight: [rowIndex, columnIndex + 1],
      Home: [event.ctrlKey ? 0 : rowIndex, 0],
      End: [event.ctrlKey ? processedRows.length - 1 : rowIndex, orderedColumns.length - 1],
      PageUp: [rowIndex - page, columnIndex],
      PageDown: [rowIndex + page, columnIndex],
    };
    const target = targets[event.key];
    if (target) {
      event.preventDefault();
      focusCell(...target);
    } else if (event.key === " " && hasSelection) {
      event.preventDefault();
      selectRow(rowIndex, event.shiftKey);
    } else if (event.key === "Enter" || event.key === "F2") {
      event.preventDefault();
      beginEdit(row, column);
    }
  };

  const exportRows = (format: "csv" | "excel"): void => {
    const data = processedRows;
    if (format === "csv") {
      const body = [
        orderedColumns.map((column) => escapeCsv(column.header)).join(","),
        ...data.map((row) => orderedColumns.map((column) => escapeCsv(getValue(row, column))).join(",")),
      ].join("\r\n");
      download(`\uFEFF${body}`, "text/csv;charset=utf-8", "data-export.csv");
      return;
    }
    const table = `<table><thead><tr>${orderedColumns.map((column) => `<th>${escapeHtml(column.header)}</th>`).join("")}</tr></thead><tbody>${data.map((row) => `<tr>${orderedColumns.map((column) => `<td>${escapeHtml(getValue(row, column))}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
    download(`\uFEFF${table}`, "application/vnd.ms-excel", "data-export.xls");
  };

  const allVisibleSelected = processedRows.length > 0 && processedRows.every((row) => selection.has(getRowId(row)));
  const style = { "--dt-height": `${height}px`, "--dt-row-height": `${rowHeight}px` } as CSSProperties;

  return (
    <section className="dt-shell" style={style} aria-label={`${ariaLabel} controls`}>
      <div className="dt-toolbar">
        <div>
          <strong>{ariaLabel}</strong>
          <span className="dt-count">
            {processedRows.length.toLocaleString()} of {(totalRowCount ?? rows.length).toLocaleString()} rows
          </span>
        </div>
        <div className="dt-actions" aria-label="Export options">
          <button type="button" onClick={() => exportRows("csv")}>Export CSV</button>
          <button type="button" onClick={() => exportRows("excel")}>Export Excel</button>
        </div>
      </div>
      <div
        className="dt-scroll"
        ref={scrollRef}
        onScroll={(event) => setScrollTop(event.currentTarget.scrollTop)}
      >
        <div
          className="dt-grid"
          role="grid"
          aria-label={ariaLabel}
          aria-rowcount={(totalRowCount ?? processedRows.length) + 1}
          aria-colcount={orderedColumns.length + (hasSelection ? 1 : 0)}
          aria-multiselectable={selectionMode === "multi" || undefined}
          style={{ width: totalWidth }}
        >
          <div className="dt-header" role="rowgroup">
            <div className="dt-header-row" role="row" style={{ gridTemplateColumns: template }}>
              {hasSelection && (
                <div className="dt-select-header" role="columnheader" aria-label="Select rows">
                  {selectionMode === "multi" && (
                    <input
                      type="checkbox"
                      aria-label="Select all filtered rows"
                      checked={allVisibleSelected}
                      onChange={() =>
                        setSelection(
                          allVisibleSelected ? new Set() : new Set(processedRows.map((row) => getRowId(row))),
                        )
                      }
                    />
                  )}
                </div>
              )}
              {orderedColumns.map((column, columnIndex) => {
                const sortIndex = sorts.findIndex((sort) => sort.columnId === column.id);
                const sort = sorts[sortIndex];
                return (
                  <div
                    className="dt-column-header"
                    role="columnheader"
                    key={column.id}
                    draggable
                    aria-sort={sort ? (sort.direction === "asc" ? "ascending" : "descending") : "none"}
                    onDragStart={() => setDraggedColumn(column.id)}
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={() => {
                      if (draggedColumn) reorderColumn(draggedColumn, column.id);
                      setDraggedColumn(null);
                    }}
                  >
                    <div className="dt-header-title">
                      <button
                        type="button"
                        className="dt-sort"
                        disabled={!column.sortable}
                        onClick={(event) => toggleSort(column.id, event.shiftKey)}
                        title="Click to sort; Shift+click for multi-sort"
                      >
                        <span>{column.header}</span>
                        {sort && <span aria-hidden="true">{sort.direction === "asc" ? "↑" : "↓"}{sorts.length > 1 ? sortIndex + 1 : ""}</span>}
                      </button>
                      <span className="dt-reorder-actions">
                        <button type="button" disabled={columnIndex === 0} onClick={() => moveColumn(column.id, -1)} aria-label={`Move ${column.header} left`}>‹</button>
                        <button type="button" disabled={columnIndex === orderedColumns.length - 1} onClick={() => moveColumn(column.id, 1)} aria-label={`Move ${column.header} right`}>›</button>
                      </span>
                    </div>
                    {column.filterable ? (
                      <input
                        className="dt-filter"
                        type="search"
                        value={filters[column.id] ?? ""}
                        aria-label={`Filter ${column.header}`}
                        placeholder="Filter…"
                        onChange={(event) => {
                          const value = event.target.value;
                          startTransition(() => setFilters((current) => ({ ...current, [column.id]: value })));
                          if (filterMode === "client") onFilterChange?.({ ...filters, [column.id]: value });
                        }}
                      />
                    ) : <span className="dt-filter-spacer" />}
                    <span
                      className="dt-resizer"
                      role="separator"
                      aria-orientation="vertical"
                      aria-label={`Resize ${column.header}`}
                      aria-valuenow={widths[column.id]}
                      tabIndex={0}
                      onPointerDown={(event) => beginResize(event, column)}
                      onKeyDown={(event) => {
                        if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
                        event.preventDefault();
                        const delta = event.key === "ArrowLeft" ? -10 : 10;
                        setWidths((current) => ({
                          ...current,
                          [column.id]: Math.max(column.minWidth ?? 80, Math.min(column.maxWidth ?? 600, current[column.id] + delta)),
                        }));
                      }}
                    />
                  </div>
                );
              })}
            </div>
          </div>
          <div className="dt-body" role="rowgroup" style={{ height: processedRows.length * rowHeight }}>
            {visibleRows.map((row, localIndex) => {
              const rowIndex = firstVisible + localIndex;
              const rowId = getRowId(row);
              const selected = selection.has(rowId);
              return (
                <div
                  className={`dt-row${selected ? " is-selected" : ""}`}
                  role="row"
                  aria-rowindex={rowIndex + 2}
                  aria-selected={hasSelection ? selected : undefined}
                  key={rowId}
                  style={{ gridTemplateColumns: template, transform: `translateY(${rowIndex * rowHeight}px)` }}
                  onClick={(event) => {
                    if ((event.target as HTMLElement).closest("input,button")) return;
                    selectRow(rowIndex, event.shiftKey);
                  }}
                >
                  {hasSelection && (
                    <div className="dt-selection-cell" role="gridcell">
                      <input
                        type={selectionMode === "single" ? "radio" : "checkbox"}
                        name={selectionMode === "single" ? `${instanceId}-selection` : undefined}
                        checked={selected}
                        aria-label={`Select row ${rowIndex + 1}`}
                        onChange={(event) => selectRow(rowIndex, event.nativeEvent instanceof MouseEvent && event.nativeEvent.shiftKey)}
                      />
                    </div>
                  )}
                  {orderedColumns.map((column, columnIndex) => {
                    const activeEdit = editing?.rowId === rowId && editing.columnId === column.id;
                    const value = getValue(row, column);
                    return (
                      <div
                        className={`dt-cell dt-align-${column.align ?? "left"}${column.editable ? " is-editable" : ""}`}
                        role="gridcell"
                        key={column.id}
                        data-grid={instanceId}
                        data-row={rowIndex}
                        data-column={columnIndex}
                        aria-colindex={columnIndex + (hasSelection ? 2 : 1)}
                        tabIndex={focusedCell.row === rowIndex && focusedCell.column === columnIndex ? 0 : -1}
                        onFocus={() => setFocusedCell({ row: rowIndex, column: columnIndex })}
                        onKeyDown={(event) => onCellKeyDown(event, rowIndex, columnIndex, row, column)}
                        onDoubleClick={() => beginEdit(row, column)}
                      >
                        {activeEdit ? (
                          <input
                            className="dt-editor"
                            autoFocus
                            aria-label={`Edit ${column.header}, row ${rowIndex + 1}`}
                            value={editing.value}
                            onChange={(event) => setEditing({ ...editing, value: event.target.value })}
                            onBlur={() => commitEdit(row, column)}
                            onKeyDown={(event) => {
                              event.stopPropagation();
                              if (event.key === "Enter") commitEdit(row, column);
                              if (event.key === "Escape") setEditing(null);
                            }}
                          />
                        ) : column.render ? column.render(value, row) : String(value ?? "")}
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>
      </div>
      <p className="dt-help">Arrow keys navigate. Space selects. Enter edits. Shift+click sorts or selects a range.</p>
      <div className="dt-sr-only" aria-live="polite">{announcement}</div>
    </section>
  );
}
