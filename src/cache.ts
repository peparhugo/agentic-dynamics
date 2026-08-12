import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import { Page } from './types';

export const CACHE_FILE = '.ssg-cache.json';
export const CACHE_VERSION = 1;

export interface CachedPage {
  sourceHash: string;
  templateHash: string;
  renderMs: number;
  page: Page;
}

export interface CacheManifest {
  version: number;
  templateHash: string;
  pages: Record<string, CachedPage>;
}

export function hashContent(content: string): string {
  return crypto.createHash('sha256').update(content).digest('hex');
}

export function hashFile(file: string): string {
  return hashContent(fs.readFileSync(file, 'utf-8'));
}

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walk(full));
    else if (entry.isFile()) out.push(full);
  }
  return out;
}

export function resolveTemplatesDir(contentDir: string, templatesDir?: string): string {
  return templatesDir ?? path.join(path.dirname(contentDir), 'templates');
}

export function computeTemplateHash(contentDir: string, templatesDir?: string): string {
  const dir = resolveTemplatesDir(contentDir, templatesDir);
  if (!fs.existsSync(dir)) return hashContent('no-templates');
  const files = walk(dir)
    .filter((f) => f.endsWith('.hbs'))
    .sort();
  const parts = files.map((f) => `${path.relative(dir, f)}:${hashFile(f)}`);
  return hashContent(parts.join('\n'));
}

export function loadManifest(outputDir: string): CacheManifest | undefined {
  const file = path.join(outputDir, CACHE_FILE);
  if (!fs.existsSync(file)) return undefined;
  try {
    const parsed = JSON.parse(fs.readFileSync(file, 'utf-8')) as CacheManifest;
    if (!parsed || parsed.version !== CACHE_VERSION || typeof parsed.pages !== 'object') {
      return undefined;
    }
    return parsed;
  } catch {
    return undefined;
  }
}

export function saveManifest(outputDir: string, manifest: CacheManifest): void {
  fs.mkdirSync(outputDir, { recursive: true });
  fs.writeFileSync(path.join(outputDir, CACHE_FILE), JSON.stringify(manifest, null, 2), 'utf-8');
}
