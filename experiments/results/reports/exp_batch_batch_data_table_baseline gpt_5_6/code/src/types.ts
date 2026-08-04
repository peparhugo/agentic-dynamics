export type CellValue = string | number | boolean | null;

export interface DataRow {
  id: number;
  company: string;
  owner: string;
  region: string;
  status: string;
  plan: string;
  seats: number;
  mrr: number;
  health: number;
  renewal: string;
  created: string;
}

export interface Column<T> {
  id: string;
  label: string;
  width: number;
  minWidth?: number;
  align?: 'left' | 'right' | 'center';
  editable?: boolean;
  value: (row: T) => CellValue;
  format?: (value: CellValue, row: T) => string;
}

export interface SortRule {
  columnId: string;
  direction: 'asc' | 'desc';
}

export type SelectionMode = 'single' | 'multi' | 'range';
export type FilterMode = 'client' | 'server';
