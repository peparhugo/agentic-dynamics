import type { ColumnDef } from '../types';

/** RFC 4180 CSV escaping (mirrored by core/export.py). */
export function csvEscape(value: unknown): string {
  const s = value === null || value === undefined ? '' : String(value);
  if (/[",\r\n]/.test(s)) return '"' + s.replace(/"/g, '""') + '"';
  return s;
}

export function toCSV<T>(rows: readonly T[], columns: readonly ColumnDef<T>[]): string {
  const header = columns.map((c) => csvEscape(c.header)).join(',');
  const body = rows.map((row) =>
    columns
      .map((c) => {
        const get = c.accessor ?? ((r: T) => (r as Record<string, unknown>)[c.id]);
        return csvEscape(get(row));
      })
      .join(','),
  );
  return [header, ...body].join('\r\n') + '\r\n';
}

export function downloadCSV<T>(rows: readonly T[], columns: readonly ColumnDef<T>[], filename: string) {
  const blob = new Blob(['\uFEFF' + toCSV(rows, columns)], { type: 'text/csv;charset=utf-8' });
  triggerDownload(blob, filename.endsWith('.csv') ? filename : `${filename}.csv`);
}

/**
 * Excel export. In the browser we delegate to a Worker that builds a real
 * .xlsx (zip of OOXML parts) so the main thread stays responsive with
 * 100k+ rows. The Python mirror (core/export.py) produces byte-identical
 * sheet XML, which is what the pytest suite validates.
 */
export async function downloadExcel<T>(
  rows: readonly T[],
  columns: readonly ColumnDef<T>[],
  filename: string,
) {
  const { buildXlsx } = await import('./xlsx');
  const blob = await buildXlsx(rows, columns);
  triggerDownload(blob, filename.endsWith('.xlsx') ? filename : `${filename}.xlsx`);
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
