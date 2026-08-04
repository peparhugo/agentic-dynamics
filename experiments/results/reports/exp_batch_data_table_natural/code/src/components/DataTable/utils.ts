import type { SortRule, FilterRule, ColumnDef, SortDirection } from './types';

export function getCellValue<T>(row: T, column: ColumnDef<T>): any {
  if (typeof column.accessor === 'function') {
    return column.accessor(row);
  }
  return row[column.accessor];
}

export function stableSort<T>(data: T[], sortRules: SortRule[], columns: ColumnDef<T>[]): T[] {
  if (!sortRules.length) return [...data];

  const colMap = new Map(columns.map((c) => [c.id, c]));

  return [...data].sort((a, b) => {
    for (const rule of sortRules) {
      const col = colMap.get(rule.columnId);
      if (!col) continue;
      const aVal = getCellValue(a, col);
      const bVal = getCellValue(b, col);

      const cmp = compareValues(aVal, bVal);
      if (cmp !== 0) {
        return rule.direction === 'asc' ? cmp : -cmp;
      }
    }
    return 0;
  });
}

function compareValues(a: any, b: any): number {
  if (a == null && b == null) return 0;
  if (a == null) return -1;
  if (b == null) return 1;

  if (typeof a === 'number' && typeof b === 'number') return a - b;
  if (typeof a === 'string' && typeof b === 'string') return a.localeCompare(b, undefined, { sensitivity: 'base' });
  if (a instanceof Date && b instanceof Date) return a.getTime() - b.getTime();

  const aStr = String(a);
  const bStr = String(b);
  return aStr.localeCompare(bStr, undefined, { sensitivity: 'base' });
}

export function clientFilter<T>(data: T[], filterRules: FilterRule[], columns: ColumnDef<T>[]): T[] {
  if (!filterRules.length) return data;

  const colMap = new Map(columns.map((c) => [c.id, c]));

  return data.filter((row) => {
    for (const rule of filterRules) {
      const col = colMap.get(rule.columnId);
      if (!col) continue;
      const cellValue = getCellValue(row, col);
      if (!matchesFilter(cellValue, rule)) return false;
    }
    return true;
  });
}

function matchesFilter(value: any, rule: FilterRule): boolean {
  const strVal = value == null ? '' : String(value);
  const filterVal = rule.value;

  switch (rule.operator) {
    case 'eq':
      return strVal === filterVal;
    case 'neq':
      return strVal !== filterVal;
    case 'gt':
      return Number(value) > Number(filterVal);
    case 'gte':
      return Number(value) >= Number(filterVal);
    case 'lt':
      return Number(value) < Number(filterVal);
    case 'lte':
      return Number(value) <= Number(filterVal);
    case 'contains':
      return strVal.toLowerCase().includes(filterVal.toLowerCase());
    case 'notContains':
      return !strVal.toLowerCase().includes(filterVal.toLowerCase());
    case 'startsWith':
      return strVal.toLowerCase().startsWith(filterVal.toLowerCase());
    case 'endsWith':
      return strVal.toLowerCase().endsWith(filterVal.toLowerCase());
    case 'isEmpty':
      return strVal.trim() === '';
    case 'isNotEmpty':
      return strVal.trim() !== '';
    default:
      return true;
  }
}

export function cycleSortDirection(
  current: SortDirection | null,
  multiSort: boolean
): SortDirection | null {
  if (!current) return 'asc';
  if (multiSort && current === 'asc') return 'desc';
  if (multiSort && current === 'desc') return null;
  if (!multiSort && current === 'asc') return 'desc';
  if (!multiSort && current === 'desc') return 'asc';
  return null;
}

export function generateId(): string {
  return `row_${Math.random().toString(36).slice(2, 11)}_${Date.now().toString(36)}`;
}

export function exportToCSV<T>(data: T[], columns: ColumnDef<T>[], filename: string = 'export.csv'): void {
  const headers = columns.map((c) => c.header).join(',');
  const rows = data.map((row) =>
    columns
      .map((col) => {
        const val = getCellValue(row, col);
        const str = val == null ? '' : String(val);
        if (str.includes(',') || str.includes('"') || str.includes('\n')) {
          return `"${str.replace(/"/g, '""')}"`;
        }
        return str;
      })
      .join(',')
  );
  const csv = [headers, ...rows].join('\n');
  downloadBlob(csv, filename, 'text/csv;charset=utf-8;');
}

export function exportToExcel<T>(data: T[], columns: ColumnDef<T>[], filename: string = 'export.xlsx'): void {
  let html = `<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel" xmlns="http://www.w3.org/TR/REC-html40"><head><meta charset="utf-8"><!--[if gte mso 9]><xml><x:ExcelWorkbook><x:ExcelWorksheets><x:ExcelWorksheet><x:Name>Sheet1</x:Name><x:WorksheetOptions><x:DisplayGridlines/></x:WorksheetOptions></x:ExcelWorksheet></x:ExcelWorksheets></x:ExcelWorkbook></xml><![endif]--></head><body><table>`;
  html += '<tr>' + columns.map((c) => `<th>${escapeHtml(c.header)}</th>`).join('') + '</tr>';
  for (const row of data) {
    html += '<tr>' + columns.map((col) => `<td>${escapeHtml(String(getCellValue(row, col) ?? ''))}</td>`).join('') + '</tr>';
  }
  html += '</table></body></html>';
  downloadBlob(html, filename, 'application/vnd.ms-excel');
}

function escapeHtml(str: string): string {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function downloadBlob(content: string, filename: string, mimeType: string): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}
