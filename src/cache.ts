import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import type { Page } from './types';

/**
 * The name of the build cache manifest written into the output directory.
 * It records, per content file, the hashes of the source and the templates
 * used, the parsed page (frontmatter + rendered markdown), the final rendered
 * HTML and how long rendering took, so an incremental build can skip pages
 * whose inputs are unchanged.
 */
export const CACHE_FILE_NAME = '.ssg-cache.json';

export const CACHE_VERSION = 1;

export interface CacheEntry {
  slug: string;
  sourceHash: string;
  templateHash: string;
  page: Page;
  renderedHtml: string;
  buildMs: number;
}

export interface BuildCache {
  version: number;
  entries: Record<string, CacheEntry>;
}

/**
 * Statistics reported after an incremental build.
 */
export interface BuildStats {
  total: number;
  built: number;
  skipped: number;
  timeSavedMs: number;
  cacheLoaded: boolean;
  clean: boolean;
}

export function emptyBuildStats(clean = false): BuildStats {
  return {
    total: 0,
    built: 0,
    skipped: 0,
    timeSavedMs: 0,
    cacheLoaded: false,
    clean,
  };
}

export function hashString(input: string): string {
  return crypto.createHash('sha256').update(input).digest('hex');
}

export function hashFile(filePath: string): string {
  const content = fs.readFileSync(filePath);
  return crypto.createHash('sha256').update(content).digest('hex');
}

/**
 * Hash every `*.hbs` file under `templateDir` (recursively, covering
 * layouts and partials) combined with the default template/layout names so a
 * change to any template invalidates every cached page. An absent template
 * directory produces a stable fingerprint.
 */
export function hashTemplateDir(
  templateDir: string | null,
  defaults?: { defaultTemplate?: string; defaultLayout?: string }
): string {
  const parts: string[] = [];
  if (templateDir !== null) {
    const root = path.resolve(templateDir);
    if (fs.existsSync(root) && fs.statSync(root).isDirectory()) {
      const walk = (dir: string, rel: string): void => {
        for (const entry of fs.readdirSync(dir).sort()) {
          const full = path.join(dir, entry);
          if (fs.statSync(full).isDirectory()) {
            walk(full, path.join(rel, entry));
          } else if (entry.toLowerCase().endsWith('.hbs')) {
            parts.push(`${path.join(rel, entry)}:${hashFile(full)}`);
          }
        }
      };
      walk(root, '');
    }
  }
  if (defaults?.defaultTemplate) {
    parts.push(`defaultTemplate:${defaults.defaultTemplate}`);
  }
  if (defaults?.defaultLayout) {
    parts.push(`defaultLayout:${defaults.defaultLayout}`);
  }
  return hashString(parts.join('\n'));
}

/**
 * Load the cache manifest. A missing, corrupted or outdated manifest is
 * treated as an empty cache so the caller performs a clean build.
 */
export function loadBuildCache(cacheFile: string): BuildCache {
  if (!fs.existsSync(cacheFile)) {
    return { version: CACHE_VERSION, entries: {} };
  }
  try {
    const raw: unknown = JSON.parse(fs.readFileSync(cacheFile, 'utf8'));
    if (
      raw !== null &&
      typeof raw === 'object' &&
      (raw as BuildCache).version === CACHE_VERSION &&
      (raw as BuildCache).entries !== null &&
      typeof (raw as BuildCache).entries === 'object'
    ) {
      return raw as BuildCache;
    }
  } catch {
    // fall through to an empty cache
  }
  return { version: CACHE_VERSION, entries: {} };
}

/**
 * Atomically write the cache manifest (`<file>.tmp` then rename) so a
 * crash mid-write never leaves a truncated manifest behind.
 */
export function saveBuildCache(cacheFile: string, cache: BuildCache): void {
  fs.mkdirSync(path.dirname(cacheFile), { recursive: true });
  const tmp = `${cacheFile}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(cache, null, 2));
  fs.renameSync(tmp, cacheFile);
}
