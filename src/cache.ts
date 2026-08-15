import * as crypto from 'crypto';
import * as fs from 'fs';
import * as path from 'path';
import type { Page } from './types';

export const CACHE_VERSION = 1;

export interface CacheEntry {
  /** Hash of the Markdown source file's contents at the time this entry was recorded. */
  sourceHash: string;
  /** How long (ms) the plugin pipeline took to produce this page, used to estimate time saved by skipping it later. */
  buildTimeMs: number;
  /** The fully-built page (post-plugin-pipeline), reused verbatim when the entry is still valid. */
  page: Page;
}

export interface CacheManifest {
  version: number;
  /** Combined hash of every file under the templates directory; any layout/partial change invalidates every entry. */
  templatesHash: string;
  /** Identifies the plugin pipeline (by name, in order) an entry was built with, so a config change invalidates stale entries. */
  pluginsSignature: string;
  /** Keyed by source path relative to the content directory. */
  pages: Record<string, CacheEntry>;
}

export function hashString(value: string): string {
  return crypto.createHash('sha256').update(value).digest('hex');
}

export function hashFile(filePath: string): string {
  return hashString(fs.readFileSync(filePath, 'utf8'));
}

/**
 * Hashes every file under `dir` (recursively) into a single digest, so any
 * addition, removal, rename, or content edit anywhere in the tree changes
 * the result. Used to treat the templates directory (layouts + partials) as
 * a single invalidation unit, since a partial can be pulled into any layout.
 */
export function hashDirectory(dir: string): string {
  if (!fs.existsSync(dir)) return '';

  const relativePaths = listFilesRecursive(dir)
    .map((filePath) => path.relative(dir, filePath).split(path.sep).join('/'))
    .sort();

  const hash = crypto.createHash('sha256');
  for (const relPath of relativePaths) {
    hash.update(relPath);
    hash.update('\0');
    hash.update(fs.readFileSync(path.join(dir, relPath)));
    hash.update('\0');
  }
  return hash.digest('hex');
}

function listFilesRecursive(dir: string): string[] {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const files: string[] = [];

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...listFilesRecursive(fullPath));
    } else if (entry.isFile()) {
      files.push(fullPath);
    }
  }

  return files;
}

/** Loads the manifest at `cachePath`, returning undefined if it is missing, unreadable, or from an incompatible cache version. */
export function loadCacheManifest(cachePath: string): CacheManifest | undefined {
  if (!fs.existsSync(cachePath)) return undefined;

  try {
    const parsed = JSON.parse(fs.readFileSync(cachePath, 'utf8')) as CacheManifest;
    if (parsed.version !== CACHE_VERSION || !parsed.pages) return undefined;
    return parsed;
  } catch {
    return undefined;
  }
}

export function saveCacheManifest(cachePath: string, manifest: CacheManifest): void {
  fs.mkdirSync(path.dirname(cachePath), { recursive: true });
  fs.writeFileSync(cachePath, JSON.stringify(manifest, null, 2), 'utf8');
}

export function deleteCacheManifest(cachePath: string): void {
  if (fs.existsSync(cachePath)) fs.rmSync(cachePath);
}
