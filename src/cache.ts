import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import { Page, Frontmatter } from './types';

export interface CachePageEntry {
  sourceHash: string;
  templateName: string;
  layoutName: string;
  frontmatter: Frontmatter;
  html: string;
  renderedHTML: string;
}

export interface CacheManifest {
  pages: Record<string, CachePageEntry>;
  templatesHash: string;
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
}

interface InternalPageEntry {
  sourceHash: string;
  templateName: string;
  layoutName: string;
}

export class CacheManager {
  private manifest: CacheManifest | null = null;
  private cachePath: string;
  private htmlCache: Map<string, string> = new Map();
  private pageCache: Map<string, Page> = new Map();
  private frontmatterCache: Map<string, Frontmatter> = new Map();
  private _pageEntries: Map<string, InternalPageEntry> = new Map();
  private _pagesBuilt = 0;
  private _pagesSkipped = 0;
  private _currentTemplatesHash = '';

  constructor(cachePath: string) {
    this.cachePath = cachePath;
  }

  get pagesBuilt(): number {
    return this._pagesBuilt;
  }

  get pagesSkipped(): number {
    return this._pagesSkipped;
  }

  get currentTemplatesHash(): string {
    return this._currentTemplatesHash;
  }

  incrementBuilt(): void {
    this._pagesBuilt++;
  }

  incrementSkipped(): void {
    this._pagesSkipped++;
  }

  getStats(): BuildStats {
    return { pagesBuilt: this._pagesBuilt, pagesSkipped: this._pagesSkipped };
  }

  load(): CacheManifest | null {
    try {
      if (fs.existsSync(this.cachePath)) {
        const raw = fs.readFileSync(this.cachePath, 'utf-8');
        const manifest: CacheManifest = JSON.parse(raw);
        this.manifest = manifest;

        for (const [slug, entry] of Object.entries(manifest.pages)) {
          const page: Page = {
            frontmatter: entry.frontmatter,
            html: entry.html,
            slug,
          };
          this.pageCache.set(slug, page);
          this.frontmatterCache.set(slug, entry.frontmatter);
          this.htmlCache.set(slug, entry.renderedHTML);
          this._pageEntries.set(slug, {
            sourceHash: entry.sourceHash,
            templateName: entry.templateName,
            layoutName: entry.layoutName,
          });
        }

        return manifest;
      }
    } catch {
      // Corrupt cache - ignore
    }
    return null;
  }

  getManifest(): CacheManifest | null {
    return this.manifest;
  }

  save(newManifest?: CacheManifest): void {
    const manifest = newManifest || this.manifest;
    if (manifest) {
      fs.writeFileSync(this.cachePath, JSON.stringify(manifest, null, 2), 'utf-8');
      this.manifest = manifest;
    }
  }

  delete(): void {
    if (fs.existsSync(this.cachePath)) {
      fs.unlinkSync(this.cachePath);
    }
    this.manifest = null;
    this.htmlCache.clear();
    this.pageCache.clear();
    this.frontmatterCache.clear();
    this._pageEntries.clear();
    this._pagesBuilt = 0;
    this._pagesSkipped = 0;
  }

  setPageEntry(slug: string, sourceHash: string, templateName: string, layoutName: string): void {
    this._pageEntries.set(slug, { sourceHash, templateName, layoutName });
  }

  buildManifest(templatesHash: string): CacheManifest {
    const pages: Record<string, CachePageEntry> = {};
    for (const [slug, entry] of this._pageEntries) {
      const frontmatter = this.frontmatterCache.get(slug);
      const page = this.pageCache.get(slug);
      const renderedHTML = this.htmlCache.get(slug);
      if (frontmatter && page && renderedHTML !== undefined) {
        pages[slug] = {
          sourceHash: entry.sourceHash,
          templateName: entry.templateName,
          layoutName: entry.layoutName,
          frontmatter,
          html: page.html,
          renderedHTML,
        };
      }
    }
    return { pages, templatesHash };
  }

  computeFileHash(filePath: string): string {
    if (!fs.existsSync(filePath)) {
      return '';
    }
    const content = fs.readFileSync(filePath);
    return crypto.createHash('md5').update(content).digest('hex');
  }

  computeTemplatesHash(templateDir: string): string {
    if (!templateDir || !fs.existsSync(templateDir)) {
      this._currentTemplatesHash = 'default-templates';
      return this._currentTemplatesHash;
    }
    const hash = crypto.createHash('md5');
    this.hashDirectory(templateDir, hash);
    this._currentTemplatesHash = hash.digest('hex');
    return this._currentTemplatesHash;
  }

  private hashDirectory(dir: string, hash: crypto.Hash): void {
    if (!fs.existsSync(dir)) return;
    const entries = fs.readdirSync(dir, { withFileTypes: true }).sort((a, b) =>
      a.name.localeCompare(b.name)
    );
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        hash.update(entry.name);
        this.hashDirectory(fullPath, hash);
      } else if (entry.name.endsWith('.hbs') || entry.name.endsWith('.handlebars')) {
        hash.update(entry.name);
        hash.update(fs.readFileSync(fullPath));
      }
    }
  }

  isPageDirty(
    slug: string,
    sourceHash: string,
    templateName: string,
    layoutName: string,
    templatesChanged: boolean
  ): boolean {
    if (!this.manifest || !this.manifest.pages[slug]) {
      return true;
    }
    if (templatesChanged) {
      return true;
    }
    const cached = this.manifest.pages[slug];
    if (cached.sourceHash !== sourceHash) {
      return true;
    }
    if (cached.templateName !== templateName) {
      return true;
    }
    if (cached.layoutName !== layoutName) {
      return true;
    }
    return false;
  }

  getCachedPage(slug: string): Page | undefined {
    return this.pageCache.get(slug);
  }

  setCachedPage(slug: string, page: Page): void {
    this.pageCache.set(slug, { ...page });
  }

  getCachedHTML(slug: string): string | undefined {
    return this.htmlCache.get(slug);
  }

  setCachedHTML(slug: string, html: string): void {
    this.htmlCache.set(slug, html);
  }

  getCachedFrontmatter(slug: string): Frontmatter | undefined {
    return this.frontmatterCache.get(slug);
  }

  setCachedFrontmatter(slug: string, fm: Frontmatter): void {
    this.frontmatterCache.set(slug, { ...fm });
  }
}
