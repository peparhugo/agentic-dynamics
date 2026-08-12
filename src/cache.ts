import crypto from 'crypto';
import fs from 'fs';
import path from 'path';
import { Page } from './types';

export const CACHE_VERSION = 1;
export const CACHE_FILE = '.ssg-cache.json';

/**
 * A single cached page: the parsed page (with frontmatter), the rendered
 * HTML, the hashes it was produced from, and how long it took to build.
 */
export interface CacheEntry {
  source: string;
  sourceHash: string;
  templateHash: string;
  page: Page;
  rendered: string;
  pageMs: number;
}

export interface CacheManifest {
  version: number;
  entries: Record<string, CacheEntry>;
}

export function hashString(input: string): string {
  return crypto.createHash('md5').update(input, 'utf8').digest('hex');
}

/**
 * Hash of a file's contents. Used to detect whether a source page changed.
 */
export function hashFile(filePath: string): string {
  return hashString(fs.readFileSync(filePath, 'utf8'));
}

/**
 * Hash of every file under a directory (e.g. the templates directory).
 * The combined template hash is compared so that any template change
 * invalidates every cached page.
 */
export function hashDir(dir: string): string {
  if (!fs.existsSync(dir)) {
    return '';
  }
  const files: string[] = [];
  const walk = (current: string): void => {
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.isFile()) {
        files.push(full);
      }
    }
  };
  walk(dir);
  files.sort();
  const parts = files.map((file) => `${path.relative(dir, file).replace(/\\/g, '/')}:${hashFile(file)}`);
  return hashString(parts.join('\n'));
}

export function cachePathFor(outputDir: string): string {
  return path.join(outputDir, CACHE_FILE);
}

export function emptyManifest(): CacheManifest {
  return { version: CACHE_VERSION, entries: {} };
}

/**
 * Load the cache manifest. Returns undefined when the cache is missing,
 * corrupt, or belongs to an incompatible version.
 */
export function loadCache(cachePath: string): CacheManifest | undefined {
  if (!fs.existsSync(cachePath)) {
    return undefined;
  }
  try {
    const raw = JSON.parse(fs.readFileSync(cachePath, 'utf8')) as CacheManifest;
    if (!raw || raw.version !== CACHE_VERSION || typeof raw.entries !== 'object') {
      return undefined;
    }
    return raw;
  } catch {
    return undefined;
  }
}

export function saveCache(cachePath: string, manifest: CacheManifest): void {
  fs.mkdirSync(path.dirname(cachePath), { recursive: true });
  fs.writeFileSync(cachePath, JSON.stringify(manifest, null, 2), 'utf8');
}

/**
 * A cached entry is reusable when both its source hash and the template hash
 * match the current state of the site.
 */
export function isEntryValid(
  entry: CacheEntry | undefined,
  sourceHash: string,
  templateHash: string
): boolean {
  return !!entry && entry.sourceHash === sourceHash && entry.templateHash === templateHash;
}
