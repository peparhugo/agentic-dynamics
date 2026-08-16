/**
 * Incremental build cache.
 *
 * Incremental builds skip pages whose source file and templates have not
 * changed since they were last rendered. To decide that, a JSON manifest
 * (`.ssg-cache.json`) is written into the output directory. For every page
 * it records:
 *
 *   - the hash of the source Markdown file,
 *   - the hash of the templates directory the page was rendered with,
 *   - the parsed page (including its frontmatter) so it does not have to be
 *     re-parsed, and
 *   - the fully rendered HTML so it does not have to be re-rendered.
 *
 * A page is skipped when both hashes still match the cached ones. If the
 * manifest is missing or a `--clean` build is requested, every page is built.
 */

import crypto from 'crypto';
import fs from 'fs';
import path from 'path';

import { DEFAULT_TEMPLATES_DIR, TEMPLATE_EXTENSION } from './templates';
import type { Page } from './types';

/** Name of the cache manifest file written into the output directory. */
export const CACHE_FILE_NAME = '.ssg-cache.json';

/** Version of the cache format. Bump to invalidate every old manifest. */
export const CACHE_VERSION = 1;

/** A single cached output: its hashes plus everything needed to reuse it. */
export interface CacheEntry {
  /** Hash of the source Markdown file contents. */
  sourceHash: string;
  /** Hash of the templates directory this page was rendered with. */
  templateHash: string;
  /** Parsed page (frontmatter and rendered body) when applicable. */
  page?: Page;
  /** Fully rendered HTML document written to the output directory. */
  output: string;
  /** Wall-clock milliseconds the page took to build (for time saved). */
  buildMs: number;
  /** ISO timestamp of when the entry was built. */
  builtAt: string;
}

/** The on-disk cache manifest. */
export interface CacheManifest {
  /** Format version (must match {@link CACHE_VERSION}). */
  version: number;
  /** Cached outputs keyed by output file name (e.g. `post.html`). */
  entries: Record<string, CacheEntry>;
}

/** Build statistics reported after a build. */
export interface BuildStats {
  /** Number of pages that were actually (re)built. */
  pagesBuilt: number;
  /** Number of pages reused from the cache without rebuilding. */
  pagesSkipped: number;
  /** Estimated wall-clock milliseconds saved by skipping pages. */
  timeSavedMs: number;
  /** Total wall-clock milliseconds spent building. */
  totalMs: number;
  /** Whether an existing cache manifest was found and used. */
  cacheLoaded: boolean;
}

/** SHA-256 hex digest of a UTF-8 string. */
export function hashContent(content: string): string {
  return crypto.createHash('sha256').update(content, 'utf8').digest('hex');
}

/** SHA-256 hex digest of a file's contents (empty hash when missing). */
export function hashFile(filePath: string): string {
  if (!fs.existsSync(filePath)) return hashContent('');
  return hashContent(fs.readFileSync(filePath, 'utf8'));
}

/** Hash used when there is no templates directory (or it is empty). */
export const EMPTY_TEMPLATE_HASH = hashContent('');

/** Recursively list every `.hbs` file under the templates directory. */
export function listTemplateFilesRecursive(dir: string): string[] {
  if (!fs.existsSync(dir)) return [];
  const results: string[] = [];
  const extRe = new RegExp(`\\.${TEMPLATE_EXTENSION}$`, 'i');
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...listTemplateFilesRecursive(full));
    } else if (entry.isFile() && extRe.test(entry.name)) {
      results.push(full);
    }
  }
  return results.sort();
}

/**
 * Hash of every template, layout and partial used to render pages. Changing
 * any template file invalidates every cached page rendered with them.
 */
export function computeTemplateHash(templatesDir?: string): string {
  const dir = templatesDir ?? DEFAULT_TEMPLATES_DIR;
  const files = listTemplateFilesRecursive(dir);
  if (files.length === 0) return EMPTY_TEMPLATE_HASH;
  const parts = files.map(
    (file) => `${path.relative(dir, file).split(path.sep).join('/')}:${hashFile(file)}`,
  );
  return hashContent(parts.join('\n'));
}

/** Resolve the cache manifest path for a build output directory. */
export function cacheFilePath(outputDir: string): string {
  return path.join(outputDir, CACHE_FILE_NAME);
}

/**
 * Read a cache manifest, or null when the file is missing, unreadable or in
 * an unknown format. A missing or stale manifest forces a clean build.
 */
export function loadCache(cachePath: string): CacheManifest | null {
  if (!fs.existsSync(cachePath)) return null;
  try {
    const raw = JSON.parse(fs.readFileSync(cachePath, 'utf8')) as Partial<CacheManifest>;
    if (raw.version !== CACHE_VERSION || typeof raw.entries !== 'object' || !raw.entries) {
      return null;
    }
    return { version: CACHE_VERSION, entries: raw.entries as Record<string, CacheEntry> };
  } catch {
    return null;
  }
}

/** Write a cache manifest to disk (atomically, via a temp file). */
export function saveCache(cachePath: string, manifest: CacheManifest): void {
  fs.mkdirSync(path.dirname(cachePath), { recursive: true });
  const tmp = `${cachePath}.${process.pid}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(manifest, null, 2));
  fs.renameSync(tmp, cachePath);
}
