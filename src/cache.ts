import { createHash } from 'crypto';
import { promises as fs } from 'fs';
import * as path from 'path';
import { Page } from './types';

/**
 * Incremental build cache.
 *
 * A `.ssg-cache.json` manifest records, for every page slug, the hash of the
 * raw source content, the hash of the templates used to render it, and the
 * previously computed page data / rendered HTML. On an incremental build a
 * page is only re-parsed and re-rendered when its source or its templates
 * changed; otherwise the cached output is reused.
 */

export const CACHE_VERSION = 1;
export const DEFAULT_CACHE_FILE = '.ssg-cache.json';

export interface CacheEntry {
  sourceHash: string;
  templateHash: string;
  /** Parsed page data (frontmatter + rendered markdown body). */
  page: Page | null;
  /** Final rendered HTML output for the page. */
  html: string | null;
  /** Wall-clock ms spent rendering this page on its last build. */
  renderMs: number;
}

export interface CacheManifest {
  version: number;
  files: Record<string, CacheEntry>;
}

export function hashContent(content: string): string {
  return createHash('sha256').update(content, 'utf8').digest('hex');
}

/**
 * The cache lives on disk as a JSON manifest, but a fresh instance with an
 * empty manifest is returned whenever the file is missing, unreadable, or
 * written by an incompatible version so builds never fail on a stale cache.
 */
export class SsgCache {
  private readonly manifest: CacheManifest;
  private readonly cacheFilePath: string;

  constructor(cacheFilePath: string, manifest?: CacheManifest) {
    this.cacheFilePath = cacheFilePath;
    this.manifest = manifest ?? { version: CACHE_VERSION, files: {} };
  }

  static async load(cacheFilePath: string): Promise<SsgCache> {
    try {
      const raw = await fs.readFile(cacheFilePath, 'utf8');
      const parsed = JSON.parse(raw) as CacheManifest;
      if (!parsed || parsed.version !== CACHE_VERSION || !parsed.files) {
        return new SsgCache(cacheFilePath);
      }
      return new SsgCache(cacheFilePath, parsed);
    } catch {
      return new SsgCache(cacheFilePath);
    }
  }

  get(key: string): CacheEntry | undefined {
    return this.manifest.files[key];
  }

  set(key: string, entry: CacheEntry): void {
    this.manifest.files[key] = entry;
  }

  get entries(): Record<string, CacheEntry> {
    return this.manifest.files;
  }

  async save(): Promise<void> {
    await fs.mkdir(path.dirname(this.cacheFilePath), { recursive: true });
    await fs.writeFile(this.cacheFilePath, JSON.stringify(this.manifest, null, 2), 'utf8');
  }
}

/** Deep-copy the page fields the markdown plugin produces. */
export function snapshotPage(page: Page): Page {
  return {
    slug: page.slug,
    title: page.title,
    date: page.date,
    tags: page.tags ? [...page.tags] : [],
    content: page.content,
    html: page.html,
    sourcePath: page.sourcePath,
    template: page.template,
    layout: page.layout,
    data: page.data ? { ...page.data } : undefined,
  };
}

/** Copy parsed page fields from `source` onto `target` in place. */
export function applyParsedPage(source: Page, target: Page): void {
  target.slug = source.slug;
  target.title = source.title;
  target.date = source.date;
  target.tags = source.tags;
  target.content = source.content;
  target.html = source.html;
  target.sourcePath = source.sourcePath;
  target.template = source.template;
  target.layout = source.layout;
  target.data = source.data;
}
