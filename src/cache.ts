import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import { Frontmatter, Page } from './types';
import { pageTemplateSources } from './templates';

export const CACHE_FILENAME = '.ssg-cache.json';

export interface PageCacheEntry {
  slug: string;
  sourceHash: string;
  templateHash: string;
  frontmatter: Frontmatter;
  bodyHtml: string;
}

export interface CacheManifest {
  version: number;
  pages: Record<string, PageCacheEntry>;
}

export function hashString(value: string): string {
  return crypto.createHash('sha256').update(value).digest('hex');
}

export function readFileHash(file: string): string {
  return hashString(fs.readFileSync(file, 'utf-8'));
}

export function computeTemplateHash(templatesDir: string, page: Page): string {
  return hashString(pageTemplateSources(templatesDir, page));
}

export class BuildCache {
  readonly manifestPath: string;
  private manifest: CacheManifest;
  private dirty = false;
  private readonly htmlCache = new Map<string, string>();
  private readonly frontmatterCache = new Map<string, Frontmatter>();

  constructor(manifestPath: string) {
    this.manifestPath = manifestPath;
    this.manifest = this.load();
  }

  private load(): CacheManifest {
    try {
      const parsed = JSON.parse(fs.readFileSync(this.manifestPath, 'utf-8'));
      if (parsed && typeof parsed === 'object' && parsed.pages && typeof parsed.pages === 'object') {
        const manifest = { version: parsed.version ?? 1, pages: parsed.pages as Record<string, PageCacheEntry> };
        for (const entry of Object.values(manifest.pages)) {
          if (entry && entry.frontmatter) {
            this.frontmatterCache.set(entry.slug, entry.frontmatter);
          }
        }
        return manifest;
      }
    } catch {
      // missing or corrupt cache -> start fresh
    }
    return { version: 1, pages: {} };
  }

  getEntry(slug: string): PageCacheEntry | undefined {
    return this.manifest.pages[slug];
  }

  setEntry(entry: PageCacheEntry): void {
    this.manifest.pages[entry.slug] = entry;
    this.frontmatterCache.set(entry.slug, entry.frontmatter);
    this.dirty = true;
  }

  invalidate(slug: string): void {
    delete this.manifest.pages[slug];
    this.htmlCache.delete(slug);
    this.frontmatterCache.delete(slug);
    this.dirty = true;
  }

  getHtml(slug: string): string | undefined {
    return this.htmlCache.get(slug);
  }

  setHtml(slug: string, html: string): void {
    this.htmlCache.set(slug, html);
  }

  getFrontmatter(slug: string): Frontmatter | undefined {
    return this.frontmatterCache.get(slug);
  }

  setFrontmatter(slug: string, frontmatter: Frontmatter): void {
    this.frontmatterCache.set(slug, frontmatter);
  }

  get entries(): Record<string, PageCacheEntry> {
    return this.manifest.pages;
  }

  reset(): void {
    this.manifest = { version: 1, pages: {} };
    this.htmlCache.clear();
    this.frontmatterCache.clear();
    this.dirty = true;
  }

  save(): void {
    if (!this.dirty) return;
    fs.mkdirSync(path.dirname(this.manifestPath), { recursive: true });
    fs.writeFileSync(this.manifestPath, JSON.stringify(this.manifest, null, 2), 'utf-8');
    this.dirty = false;
  }
}
