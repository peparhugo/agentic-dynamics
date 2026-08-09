import fs from 'fs';
import path from 'path';

export function ensureDir(p: string) {
  fs.mkdirSync(p, { recursive: true });
}

export function writeFileAtomic(filePath: string, content: string | Buffer) {
  ensureDir(path.dirname(filePath));
  const tmp = filePath + ".tmp";
  fs.writeFileSync(tmp, content);
  fs.renameSync(tmp, filePath);
}

export function toSlug(input: string): string {
  return input
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

export function withHtmlExt(relPath: string): string {
  const ext = path.extname(relPath);
  return relPath.slice(0, relPath.length - ext.length) + '.html';
}

export function htmlInjectBeforeBodyEnd(html: string, inject: string): string {
  const idx = html.lastIndexOf('</body>');
  if (idx === -1) return html + inject;
  return html.slice(0, idx) + inject + html.slice(idx);
}

export function normalizeBaseUrl(baseUrl?: string): string | undefined {
  if (!baseUrl) return undefined;
  if (baseUrl === '/') return '';
  return baseUrl.replace(/\/$/, '');
}

export function pathToUrlPath(p: string): string {
  return p.split(path.sep).join('/');
}
