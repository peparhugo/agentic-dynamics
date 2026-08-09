export type SortDirection = 'asc' | 'desc';

export interface SortSpec {
  columnId: string;
  direction: SortDirection;
}

export type FilterOperator =
  | 'contains'
  | 'equals'
  | 'startsWith'
  | 'endsWith'
  | 'gt'
  | 'gte'
  | 'lt'
  | 'lte'
  | 'between'
  | 'in'
  | 'isEmpty'
  | 'notEmpty';

export interface FilterSpec {
  columnId: string;
  operator: FilterOperator;
  value?: unknown;
  value2?: unknown; // for 'between'
}

export type FilterMode = 'client' | 'server';

export type SelectionMode = 'single' | 'multi' | 'range';

export interface ColumnDef<T = Record<string, unknown>> {
  id: string;
  header: string;
  accessor?: (row: T) => unknown;
  width?: number;
  minWidth?: number;
  maxWidth?: number;
  sortable?: boolean;
  filterable?: boolean;
  editable?: boolean;
  resizable?: boolean;
  align?: 'left' | 'center' | 'right';
  comparator?: (a: unknown, b: unknown) => number;
  validator?: (value: unknown, row: T) => string | null;
  renderCell?: (value: unknown, row: T) => React.ReactNode;
  renderEditor?: (props: EditorProps<T>) => React.ReactNode;
}

export interface EditorProps<T> {
  value: unknown;
  row: T;
  onCommit: (value: unknown) => void;
  onCancel: () => void;
}

export interface VirtualWindow {
  startIndex: number;
  endIndex: number; // exclusive
  offsetY: number;
  totalHeight: number;
}

export interface CellPosition {
  rowIndex: number;
  colIndex: number;
}

export interface DataTableProps<T> {
  columns: ColumnDef<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  rowHeight?: number;
  height?: number;
  overscan?: number;
  selectionMode?: SelectionMode;
  filterMode?: FilterMode;
  onServerQuery?: (query: ServerQuery) => Promise<{ rows: T[]; total: number }>;
  onRowsChange?: (rows: T[]) => void;
  onSelectionChange?: (keys: ReadonlySet<string>) => void;
  ariaLabel: string;
}

export interface ServerQuery {
  sorts: SortSpec[];
  filters: FilterSpec[];
  offset: number;
  limit: number;
}
