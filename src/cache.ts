import fs from 'fs';
import path from 'path';

export const CACHE_FILENAME = '.ssg-cache.json';
export const CACHE_VERSION = 1;

/**
 * A single cached page. It captures every field the build pipeline produces so
 * that an unchanged page can be reconstructed without re-running the plugins.
 */
export interface CachedPage {
  slug: string;
  /** SHA-256 digest of the raw Markdown source file. */
  sourceHash: string;
  /** SHA-256 digest of the layout + partials the page resolves to. */
  templateHash: string;
  title: string;
  date?: string;
  tags: string[];
  template?: string;
  /** Stripped Markdown body (frontmatter removed). */
  content: string;
  /** Rendered body HTML. */
  html: string;
  /** Final full-page HTML written to disk. */
  rendered: string;
}

export interface CacheManifest {
  version: number;
  pages: Record<string, CachedPage>;
}

/** Returns the default location of the manifest within the output directory. */
export function defaultCacheFile(outputDir: string): string {
  return path.join(outputDir, CACHE_FILENAME);
}

/** Loads the manifest from disk, returning an empty one when missing/corrupt. */
export function loadManifest(cacheFile: string): CacheManifest {
  try {
    const raw = fs.readFileSync(cacheFile, 'utf-8');
    const parsed = JSON.parse(raw) as Partial<CacheManifest>;
    if (parsed && parsed.version === CACHE_VERSION && parsed.pages && typeof parsed.pages === 'object') {
      return { version: CACHE_VERSION, pages: parsed.pages };
    }
  } catch {
    // Missing or corrupt cache -> treat as a clean build.
  }
  return { version: CACHE_VERSION, pages: {} };
}

/** Persists the manifest to disk. */
export function saveManifest(cacheFile: string, manifest: CacheManifest): void {
  fs.mkdirSync(path.dirname(cacheFile), { recursive: true });
  fs.writeFileSync(cacheFile, JSON.stringify(manifest, null, 2));
}
