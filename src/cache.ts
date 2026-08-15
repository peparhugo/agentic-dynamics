import crypto from 'crypto';
import fs from 'fs';
import path from 'path';

export const CACHE_FILENAME = '.ssg-cache.json';
export const CACHE_VERSION = 1;

/**
 * A single cached page: the parsed frontmatter-derived metadata, the raw
 * Markdown body rendered to HTML, and the final rendered page HTML.
 */
export interface CachedPage {
  slug: string;
  sourcePath: string;
  sourceHash: string;
  templateHash: string;
  title: string;
  date?: string;
  tags: string[];
  template?: string;
  layout?: string;
  data: Record<string, unknown>;
  bodyHtml: string;
  html: string;
  durationMs: number;
}

export interface CacheManifest {
  version: number;
  pages: Record<string, CachedPage>;
}

export function hashContent(content: string): string {
  return crypto.createHash('sha256').update(content).digest('hex');
}

export function hashFile(filePath: string): string {
  return hashContent(fs.readFileSync(filePath, 'utf-8'));
}

/**
 * Hash the entire templates directory (templates, layouts, and partials) so a
 * change to any of them invalidates every cached page that depends on the
 * templates. Returns an empty string when no templates directory exists.
 */
export function computeTemplateHash(templatesDir: string): string {
  if (!fs.existsSync(templatesDir)) return '';

  const parts: string[] = [];
  const walk = (dir: string): void => {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    entries.sort((a, b) => a.name.localeCompare(b.name));
    for (const entry of entries) {
      const p = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(p);
      else if (entry.isFile()) parts.push(`${p}:${hashFile(p)}`);
    }
  };
  walk(templatesDir);

  return hashContent(parts.join('\n'));
}

/**
 * A disk-backed manifest of file hashes and cached page output, persisted to
 * `.ssg-cache.json`. It survives between builds so unchanged pages can be
 * skipped on subsequent incremental runs.
 */
export class BuildCache {
  readonly filePath: string;
  private manifest: CacheManifest | undefined;

  constructor(filePath: string) {
    this.filePath = filePath;
  }

  load(): CacheManifest | undefined {
    if (this.manifest) return this.manifest;
    try {
      const raw = fs.readFileSync(this.filePath, 'utf-8');
      const parsed = JSON.parse(raw) as CacheManifest;
      if (
        parsed &&
        parsed.version === CACHE_VERSION &&
        parsed.pages &&
        typeof parsed.pages === 'object'
      ) {
        this.manifest = parsed;
        return parsed;
      }
    } catch {
      // Missing or corrupt cache: treat as an empty cache.
    }
    return undefined;
  }

  exists(): boolean {
    return fs.existsSync(this.filePath);
  }

  delete(): void {
    this.manifest = undefined;
    if (fs.existsSync(this.filePath)) {
      fs.rmSync(this.filePath, { force: true });
    }
  }

  getPage(slug: string): CachedPage | undefined {
    return this.manifest?.pages[slug];
  }

  isFresh(slug: string, sourceHash: string, templateHash: string): boolean {
    const entry = this.getPage(slug);
    return !!entry && entry.sourceHash === sourceHash && entry.templateHash === templateHash;
  }

  setPage(entry: CachedPage): void {
    if (!this.manifest) this.manifest = { version: CACHE_VERSION, pages: {} };
    this.manifest.pages[entry.slug] = entry;
  }

  /** Drop cached entries for pages that no longer exist in the content dir. */
  prune(keepSlugs: string[]): void {
    if (!this.manifest) return;
    const keep = new Set(keepSlugs);
    for (const key of Object.keys(this.manifest.pages)) {
      if (!keep.has(key)) delete this.manifest.pages[key];
    }
  }

  save(): void {
    if (!this.manifest) return;
    fs.mkdirSync(path.dirname(this.filePath), { recursive: true });
    fs.writeFileSync(this.filePath, JSON.stringify(this.manifest, null, 2));
  }
}
