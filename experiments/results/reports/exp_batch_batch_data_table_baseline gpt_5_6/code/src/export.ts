import type { CellValue, Column } from './types';

function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

const csvCell = (value: CellValue) => `"${String(value ?? '').replaceAll('"', '""')}"`;

export function exportCsv<T>(rows: T[], columns: Column<T>[]) {
  const body = [columns.map((column) => csvCell(column.label)).join(',')];
  rows.forEach((row) => body.push(columns.map((column) => csvCell(column.value(row))).join(',')));
  download(new Blob([body.join('\r\n')], { type: 'text/csv;charset=utf-8' }), 'atlas-accounts.csv');
}

const xmlCell = (value: CellValue) => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');

export function exportExcel<T>(rows: T[], columns: Column<T>[]) {
  const tableRows = [columns.map((column) => `<Cell><Data ss:Type="String">${xmlCell(column.label)}</Data></Cell>`).join('')];
  rows.forEach((row) => tableRows.push(columns.map((column) => `<Cell><Data ss:Type="String">${xmlCell(column.value(row))}</Data></Cell>`).join('')));
  const xml = `<?xml version="1.0"?><Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"><Worksheet ss:Name="Accounts"><Table>${tableRows.map((cells) => `<Row>${cells}</Row>`).join('')}</Table></Worksheet></Workbook>`;
  download(new Blob([xml], { type: 'application/vnd.ms-excel' }), 'atlas-accounts.xls');
}
