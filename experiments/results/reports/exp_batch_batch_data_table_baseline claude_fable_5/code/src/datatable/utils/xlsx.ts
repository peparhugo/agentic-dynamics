import type { ColumnDef } from '../types';

/** Minimal OOXML (.xlsx) writer using inline strings. */

export function xmlEscape(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/** Convert a zero-based column index to an A1-style column letter. */
export function columnLetter(index: number): string {
  let n = index + 1;
  let out = '';
  while (n > 0) {
    const rem = (n - 1) % 26;
    out = String.fromCharCode(65 + rem) + out;
    n = Math.floor((n - 1) / 26);
  }
  return out;
}

export function sheetXml<T>(rows: readonly T[], columns: readonly ColumnDef<T>[]): string {
  const cell = (r: number, c: number, v: unknown): string => {
    const ref = `${columnLetter(c)}${r + 1}`;
    if (typeof v === 'number' && Number.isFinite(v)) {
      return `<c r="${ref}"><v>${v}</v></c>`;
    }
    const s = v === null || v === undefined ? '' : String(v);
    return `<c r="${ref}" t="inlineStr"><is><t>${xmlEscape(s)}</t></is></c>`;
  };

  const lines: string[] = [];
  lines.push('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>');
  lines.push('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>');
  lines.push(`<row r="1">${columns.map((c, i) => cell(0, i, c.header)).join('')}</row>`);
  rows.forEach((row, ri) => {
    const cells = columns
      .map((c, ci) => {
        const get = c.accessor ?? ((x: T) => (x as Record<string, unknown>)[c.id]);
        return cell(ri + 1, ci, get(row));
      })
      .join('');
    lines.push(`<row r="${ri + 2}">${cells}</row>`);
  });
  lines.push('</sheetData></worksheet>');
  return lines.join('');
}

export async function buildXlsx<T>(rows: readonly T[], columns: readonly ColumnDef<T>[]): Promise<Blob> {
  // Uses the browser-native CompressionStream via a tiny zip builder.
  const { zipSync } = await import('fflate');
  const enc = new TextEncoder();
  const files: Record<string, Uint8Array> = {
    '[Content_Types].xml': enc.encode(CONTENT_TYPES),
    '_rels/.rels': enc.encode(ROOT_RELS),
    'xl/workbook.xml': enc.encode(WORKBOOK),
    'xl/_rels/workbook.xml.rels': enc.encode(WORKBOOK_RELS),
    'xl/worksheets/sheet1.xml': enc.encode(sheetXml(rows, columns)),
  };
  return new Blob([zipSync(files)], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  });
}

const CONTENT_TYPES = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>`;

const ROOT_RELS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>`;

const WORKBOOK = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>`;

const WORKBOOK_RELS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>`;
