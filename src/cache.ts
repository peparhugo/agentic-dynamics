import * as crypto from 'crypto';
import * as fs from 'fs';
import * as path from 'path';
import { Page } from './types';

/** Name of the build-cache manifest file, written inside the output directory. */
export const CACHE_FILENAME = '.ssg-cache.json';

const CACHE_VERSION = 1;

/**
 * A single cached page: the hashes that determined its last render, plus
 * the parsed Page (frontmatter + rendered markdown->HTML) so an unchanged
 * page can be reused for cross-page rendering (e.g. index/nav listings)
 * without re-reading or re-parsing its source file.
 */
export interface CacheEntry {
  sourceHash: string;
  templatesHash: string;
  page: Page;
}

export interface CacheManifest {
  version: number;
  entries: Record<string, CacheEntry>;
  /** Rolling stats used to estimate time saved when every page is skipped. */
  meta: {
    avgBuildMs?: number;
  };
}

export function emptyManifest(): CacheManifest {
  return { version: CACHE_VERSION, entries: {}, meta: {} };
}

export function hashContent(content: string): string {
  return crypto.createHash('sha256').update(content).digest('hex');
}

/**
 * Hashes every layout/partial file under a templates directory into one
 * digest. Partials are shared across all pages and a page can fall back
 * from its own layout to "default", so per-file invalidation isn't safe;
 * any change anywhere in the templates directory invalidates every cached
 * page.
 */
export function hashTemplatesDir(templatesDir: string | undefined): string {
  if (!templatesDir || !fs.existsSync(templatesDir)) return 'none';

  const files: string[] = [];
  function walk(dir: string): void {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(fullPath);
      } else if (path.extname(entry.name) === '.hbs') {
        files.push(fullPath);
      }
    }
  }
  walk(templatesDir);
  files.sort();

  const hash = crypto.createHash('sha256');
  for (const file of files) {
    hash.update(path.relative(templatesDir, file));
    hash.update(fs.readFileSync(file, 'utf-8'));
  }
  return hash.digest('hex');
}

/** Path of the cache manifest for a given build's output directory. */
export function cachePathFor(outputDir: string): string {
  return path.join(outputDir, CACHE_FILENAME);
}

/**
 * Loads the manifest at `cachePath`, reporting whether a usable cache was
 * actually found. `valid` is false when the file is missing, corrupt, or
 * from an incompatible cache version, in which case `manifest` is an empty
 * one — callers use `valid` to decide whether this counts as a clean build.
 */
export function tryLoadManifest(cachePath: string): { manifest: CacheManifest; valid: boolean } {
  if (fs.existsSync(cachePath)) {
    try {
      const raw = JSON.parse(fs.readFileSync(cachePath, 'utf-8'));
      if (raw && raw.version === CACHE_VERSION && raw.entries) {
        return { manifest: { version: raw.version, entries: raw.entries, meta: raw.meta ?? {} }, valid: true };
      }
    } catch {
      // Corrupt cache file: fall through to a clean build.
    }
  }
  return { manifest: emptyManifest(), valid: false };
}

/**
 * Loads the manifest at `cachePath`. Missing, corrupt, or version-mismatched
 * files all fall back to an empty manifest so callers can treat that
 * uniformly as "no cache, do a clean build" rather than special-casing
 * parse errors.
 */
export function loadManifest(cachePath: string): CacheManifest {
  return tryLoadManifest(cachePath).manifest;
}

export function saveManifest(cachePath: string, manifest: CacheManifest): void {
  fs.mkdirSync(path.dirname(cachePath), { recursive: true });
  fs.writeFileSync(cachePath, JSON.stringify(manifest, null, 2), 'utf-8');
}
