import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import { Page } from './types';

export interface CachedPage {
  page: Page;
  html: string;
}

export interface CacheManifest {
  contentHashes: Record<string, string>;
  templateHash: string;
  pages: Record<string, CachedPage>;
  indexHtml?: string;
  indexSlugs?: string[];
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  timeSavedMs?: number;
}

export class BuildCache {
  private data: CacheManifest | null = null;
  private cachePath: string;

  constructor(cachePath: string) {
    this.cachePath = cachePath;
  }

  static computeHash(content: string): string {
    return crypto.createHash('sha256').update(content).digest('hex');
  }

  static computeFileHash(filePath: string): string {
    const content = fs.readFileSync(filePath, 'utf-8');
    return BuildCache.computeHash(content);
  }

  static computeTemplateHash(templateDir: string): string {
    if (!fs.existsSync(templateDir)) return '';

    const parts: string[] = [];
    const collectFiles = (dir: string, prefix: string) => {
      const entries = fs.readdirSync(dir, { withFileTypes: true });
      entries.sort((a, b) => a.name.localeCompare(b.name));
      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        const relPath = prefix ? `${prefix}/${entry.name}` : entry.name;
        if (entry.isDirectory()) {
          collectFiles(fullPath, relPath);
        } else if (entry.name.endsWith('.hbs')) {
          parts.push(relPath + ':' + BuildCache.computeFileHash(fullPath));
        }
      }
    };
    collectFiles(templateDir, '');

    return BuildCache.computeHash(parts.join('\n'));
  }

  load(): boolean {
    try {
      if (fs.existsSync(this.cachePath)) {
        const raw = fs.readFileSync(this.cachePath, 'utf-8');
        this.data = JSON.parse(raw);
        return true;
      }
    } catch {
      // invalid or corrupted cache, start fresh
    }
    if (!this.data) {
      this.data = {
        contentHashes: {},
        templateHash: '',
        pages: {},
      };
    }
    return false;
  }

  save(): void {
    if (this.data) {
      fs.writeFileSync(this.cachePath, JSON.stringify(this.data, null, 2));
    }
  }

  clear(): void {
    this.data = {
      contentHashes: {},
      templateHash: '',
      pages: {},
    };
    try {
      if (fs.existsSync(this.cachePath)) {
        fs.unlinkSync(this.cachePath);
      }
    } catch {
      // ignore
    }
  }

  isPopulated(): boolean {
    return (
      this.data !== null &&
      (Object.keys(this.data.contentHashes).length > 0 || this.data.templateHash !== '')
    );
  }

  getContentHash(relPath: string): string | undefined {
    return this.data?.contentHashes[relPath];
  }

  setContentHash(relPath: string, hash: string): void {
    if (this.data) {
      this.data.contentHashes[relPath] = hash;
    }
  }

  getTemplateHash(): string {
    return this.data?.templateHash || '';
  }

  setTemplateHash(hash: string): void {
    if (this.data) {
      this.data.templateHash = hash;
    }
  }

  getCachedPage(slug: string): CachedPage | undefined {
    return this.data?.pages[slug];
  }

  setCachedPage(slug: string, cached: CachedPage): void {
    if (this.data) {
      this.data.pages[slug] = cached;
    }
  }

  removeCachedPage(slug: string): void {
    if (this.data) {
      delete this.data.pages[slug];
    }
  }

  getIndexHtml(): string | undefined {
    return this.data?.indexHtml;
  }

  setIndexHtml(html: string): void {
    if (this.data) {
      this.data.indexHtml = html;
    }
  }

  getIndexSlugs(): string[] | undefined {
    return this.data?.indexSlugs;
  }

  setIndexSlugs(slugs: string[]): void {
    if (this.data) {
      this.data.indexSlugs = slugs;
    }
  }

  removeContentHash(relPath: string): void {
    if (this.data) {
      delete this.data.contentHashes[relPath];
    }
  }

  getCachedSlugs(): string[] {
    return this.data ? Object.keys(this.data.pages) : [];
  }

  getAllContentHashes(): Record<string, string> {
    return this.data ? { ...this.data.contentHashes } : {};
  }
}
