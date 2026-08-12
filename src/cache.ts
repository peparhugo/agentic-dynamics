import { createHash } from 'node:crypto';
import { readdir, readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';

export const CACHE_FILE = '.ssg-cache.json';
export const CACHE_VERSION = 1;

export interface CachedPage {
  source: string;
  slug: string;
  sourceHash: string;
  html: string;
  title: string;
  date: string;
  tags: string[];
  template?: string;
  layout?: string;
  data?: Record<string, unknown>;
  renderTimeMs: number;
}

export interface CacheManifest {
  version: number;
  templateHash: string;
  plugins: string[];
  entries: Record<string, CachedPage>;
}

export function hashString(value: string): string {
  return createHash('sha256').update(value, 'utf8').digest('hex');
}

export async function collectFiles(dir: string): Promise<string[]> {
  const files: string[] = [];
  let entries;
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return files;
  }
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await collectFiles(full)));
    } else if (entry.isFile()) {
      files.push(full);
    }
  }
  return files;
}

export async function computeTemplateHash(templatesDir: string): Promise<string> {
  const files = (await collectFiles(templatesDir)).sort();
  const hash = createHash('sha256');
  for (const file of files) {
    hash.update(path.relative(templatesDir, file), 'utf8');
    hash.update('\u0000');
    hash.update(await readFile(file, 'utf8'), 'utf8');
    hash.update('\u0000');
  }
  return hash.digest('hex');
}

export async function loadManifest(cacheFile: string): Promise<CacheManifest | null> {
  try {
    const raw = await readFile(cacheFile, 'utf8');
    const parsed = JSON.parse(raw) as CacheManifest;
    if (!parsed || parsed.version !== CACHE_VERSION) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export async function saveManifest(cacheFile: string, manifest: CacheManifest): Promise<void> {
  await mkdir(path.dirname(cacheFile), { recursive: true });
  await writeFile(cacheFile, JSON.stringify(manifest, null, 2), 'utf8');
}
