export type SortDirection = 'asc' | 'desc';

export interface SortRule {
  columnId: string;
  direction: SortDirection;
}

export type FilterOperator =
  | 'eq'
  | 'neq'
  | 'gt'
  | 'gte'
  | 'lt'
  | 'lte'
  | 'contains'
  | 'notContains'
  | 'startsWith'
  | 'endsWith'
  | 'isEmpty'
  | 'isNotEmpty';

export interface FilterRule {
  columnId: string;
  operator: FilterOperator;
  value: string;
}

export interface ColumnDef<T = any> {
  id: string;
  header: string;
  accessor: keyof T | ((row: T) => any);
  width: number;
  minWidth?: number;
  maxWidth?: number;
  sortable?: boolean;
  filterable?: boolean;
  resizable?: boolean;
  editable?: boolean;
  cell?: (row: T) => React.ReactNode;
  editor?: (props: CellEditProps<T>) => React.ReactNode;
}

export interface CellEditProps<T = any> {
  value: any;
  row: T;
  rowIndex: number;
  column: ColumnDef<T>;
  onCommit: (value: any) => void;
  onCancel: () => void;
}

export interface EditingCell {
  rowIndex: number;
  columnId: string;
}

export type SelectionMode = 'single' | 'multi' | 'range';

export interface SelectionState {
  mode: SelectionMode;
  selectedIds: Set<string>;
  anchorIndex: number | null;
  rangeEndIndex: number | null;
}

export type DataSource = 'client' | 'server';

export interface DataTableProps<T = any> {
  data: T[];
  columns: ColumnDef<T>[];
  rowHeight?: number;
  overscan?: number;
  dataSource?: DataSource;
  selectionMode?: SelectionMode;
  selectedIds?: Set<string>;
  onSelectionChange?: (selectedIds: Set<string>) => void;
  idAccessor?: keyof T | ((row: T) => string);
  className?: string;
  height?: number | string;
  headerHeight?: number;
  filterHeight?: number;
  onSortChange?: (sortRules: SortRule[]) => void;
  onFilterChange?: (filterRules: FilterRule[]) => void;
  onColumnOrderChange?: (columnIds: string[]) => void;
  onColumnResize?: (columnId: string, width: number) => void;
  onCellEdit?: (rowIndex: number, columnId: string, value: any) => void;
  onExport?: (format: 'csv' | 'excel', data: T[], columns: ColumnDef<T>[]) => void;
  serverSort?: SortRule[];
  serverFilters?: FilterRule[];
  serverTotalRows?: number;
  loading?: boolean;
  locale?: string;
  ariaLabel?: string;
}

export interface TableBodyRef {
  scrollToRow: (index: number) => void;
  scrollToTop: () => void;
  getScrollPosition: () => number;
  focusCell: (rowIndex: number, columnIndex: number) => void;
}
