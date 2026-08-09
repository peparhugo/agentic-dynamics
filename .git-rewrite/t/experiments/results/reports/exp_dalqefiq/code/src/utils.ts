import path from 'node:path';
import fs from 'node:fs/promises';
import { cpus } from 'node:os';

export function toUrlPath(relPath: string): string {
  // Convert relative file path to URL path (replace .md with .html)
  const noExt = relPath.replace(/\\/g, '/').replace(/\.md$/i, '.html');
  if (noExt.endsWith('index.html')) return '/' + noExt.replace(/index\.html$/, '');
  return '/' + noExt;
}

export function outPathFor(relPath: string, outDir: string): string {
  const htmlRel = relPath.replace(/\.md$/i, '.html');
  return path.join(outDir, htmlRel);
}

export async function ensureDirForFile(filePath: string): Promise<void> {
  const dir = path.dirname(filePath);
  await fs.mkdir(dir, { recursive: true });
}

export async function writeFileEnsured(filePath: string, data: string | Buffer): Promise<void> {
  await ensureDirForFile(filePath);
  await fs.writeFile(filePath, data);
}

export function pickConcurrency(limit?: number): number {
  const cores = Math.max(1, cpus().length);
  const def = Math.min(8, Math.max(2, cores));
  if (!limit || limit <= 0) return def;
  return Math.max(1, Math.min(64, limit));
}

export function normalizeTags(tags?: unknown): string[] {
  if (!tags) return [];
  if (Array.isArray(tags)) return tags.map(String);
  if (typeof tags === 'string') return tags.split(',').map(t => t.trim()).filter(Boolean);
  return [];
}

export function parseDate(value: unknown): Date | undefined {
  if (!value) return undefined;
  if (value instanceof Date) return value;
  const d = new Date(String(value));
  return isNaN(d.getTime()) ? undefined : d;
}

export function htmlEscape(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
