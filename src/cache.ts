import crypto from 'crypto';
import fs from 'fs';
import path from 'path';
import type { PageData } from './types';

export const CACHE_FILE = '.ssg-cache.json';
export const CACHE_VERSION = 1;

export interface CacheEntry {
  sourceHash: string;
  data: PageData;
  body: string;
  html: string;
  outputHtml: string;
}

export interface BuildCache {
  version: number;
  templateHash: string;
  entries: Record<string, CacheEntry>;
}

export interface BuildStats {
  totalPages: number;
  builtPages: number;
  skippedPages: number;
  incremental: boolean;
  cached: boolean;
  elapsedMs: number;
  timeSavedMs: number;
}

export function hashContent(content: string): string {
  return crypto.createHash('sha256').update(content).digest('hex');
}

export function computeTemplateHash(templatesDir: string): string {
  if (!fs.existsSync(templatesDir)) {
    return '';
  }
  const files: string[] = [];
  const walk = (dir: string): void => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.isFile() && /\.hbs$/i.test(entry.name)) {
        files.push(full);
      }
    }
  };
  walk(templatesDir);
  files.sort();

  const hash = crypto.createHash('sha256');
  for (const file of files) {
    hash.update(path.relative(templatesDir, file));
    hash.update(fs.readFileSync(file, 'utf-8'));
  }
  return hash.digest('hex');
}

export function loadCache(cachePath: string): BuildCache | null {
  try {
    if (!fs.existsSync(cachePath)) {
      return null;
    }
    const parsed = JSON.parse(fs.readFileSync(cachePath, 'utf-8')) as BuildCache;
    if (
      !parsed ||
      parsed.version !== CACHE_VERSION ||
      typeof parsed.templateHash !== 'string' ||
      typeof parsed.entries !== 'object' ||
      parsed.entries === null
    ) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function saveCache(cachePath: string, cache: BuildCache): void {
  fs.mkdirSync(path.dirname(cachePath), { recursive: true });
  fs.writeFileSync(cachePath, JSON.stringify(cache, null, 2), 'utf-8');
}
