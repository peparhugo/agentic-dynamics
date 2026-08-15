import fs from 'fs';
import path from 'path';
import { hashString } from './hash';
import { Page } from './types';

export const CACHE_FILE_NAME = '.ssg-cache.json';
export const CACHE_VERSION = 1;

/** Everything needed to reuse a page without re-running the plugin pipeline. */
export interface PageCacheEntry {
  sourceHash: string;
  templateHash: string;
  page: Page;
}

export interface CacheManifest {
  version: number;
  /** Rolling average build time per page, kept so `--incremental` can still estimate
   *  time saved on a run where every page was skipped (i.e. nothing was timed). */
  avgPageBuildMs: number;
  pages: Record<string, PageCacheEntry>;
}

export function emptyCacheManifest(): CacheManifest {
  return { version: CACHE_VERSION, avgPageBuildMs: 0, pages: {} };
}

export function defaultCacheFile(cwd: string): string {
  return path.join(cwd, CACHE_FILE_NAME);
}

/**
 * Loads the incremental-build manifest. A missing file, unreadable JSON, or a
 * version mismatch all fall back to an empty manifest so callers can simply
 * treat that as "no cache" and do a clean build, per the --clean/missing-cache spec.
 */
export function loadCacheManifest(cacheFile: string): CacheManifest {
  if (!fs.existsSync(cacheFile)) return emptyCacheManifest();
  try {
    const parsed = JSON.parse(fs.readFileSync(cacheFile, 'utf-8'));
    if (!parsed || parsed.version !== CACHE_VERSION || typeof parsed.pages !== 'object' || parsed.pages === null) {
      return emptyCacheManifest();
    }
    return {
      version: CACHE_VERSION,
      avgPageBuildMs: typeof parsed.avgPageBuildMs === 'number' ? parsed.avgPageBuildMs : 0,
      pages: parsed.pages,
    };
  } catch {
    return emptyCacheManifest();
  }
}

export function saveCacheManifest(cacheFile: string, manifest: CacheManifest): void {
  fs.writeFileSync(cacheFile, JSON.stringify(manifest, null, 2), 'utf-8');
}

/** Combined hash of every partial, since partials are shared across all page layouts. */
export function hashPartials(templatesDir: string): string {
  const partialsDir = path.join(templatesDir, 'partials');
  if (!fs.existsSync(partialsDir)) return 'none';
  const files = fs
    .readdirSync(partialsDir)
    .filter((file) => file.toLowerCase().endsWith('.hbs'))
    .sort();
  const combined = files.map((file) => `${file}:${fs.readFileSync(path.join(partialsDir, file), 'utf-8')}`).join('\n');
  return hashString(combined);
}

/**
 * Hashes the layout a page renders with, combined with the shared partials hash,
 * so changing either the specific layout or any partial invalidates the page.
 */
export function hashTemplate(templatesDir: string, templateName: string, partialsHash: string): string {
  const layoutPath = path.join(templatesDir, 'layouts', `${templateName}.hbs`);
  const layoutSource = fs.existsSync(layoutPath) ? fs.readFileSync(layoutPath, 'utf-8') : `__fallback:${templateName}`;
  return hashString(`${layoutSource}::${partialsHash}`);
}
