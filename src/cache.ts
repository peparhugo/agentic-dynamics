import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import { Page } from './types';

export const CACHE_FILE = '.ssg-cache.json';
export const CACHE_VERSION = 1;
const BUILTIN_TEMPLATE_HASH = 'builtin-templates';

export interface CacheEntry {
  sourceHash: string;
  templateHash: string;
  page: Page;
  html: string;
  renderMs: number;
}

export interface CacheManifest {
  version: number;
  entries: Record<string, CacheEntry>;
}

export function hashContent(content: string): string {
  return crypto.createHash('sha256').update(content, 'utf8').digest('hex');
}

export function hashTemplates(templatesDir: string): string {
  if (!templatesDir || !fs.existsSync(templatesDir)) {
    return BUILTIN_TEMPLATE_HASH;
  }
  const files: string[] = [];
  const walk = (dir: string): void => {
    const entries = fs
      .readdirSync(dir, { withFileTypes: true })
      .sort((a, b) => a.name.localeCompare(b.name));
    for (const entry of entries) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.isFile()) {
        files.push(full);
      }
    }
  };
  walk(templatesDir);
  if (files.length === 0) return BUILTIN_TEMPLATE_HASH;
  const hasher = crypto.createHash('sha256');
  for (const file of files) {
    hasher.update(path.relative(templatesDir, file));
    hasher.update(fs.readFileSync(file));
  }
  return hasher.digest('hex');
}

export class CacheManager {
  private entries: Record<string, CacheEntry> = {};
  private templateHash: string;

  constructor(
    private cacheFile: string,
    private templatesDir: string,
    private contentDir: string,
    private outputDir: string
  ) {
    this.templateHash = hashTemplates(templatesDir);
    this.load();
  }

  private load(): void {
    if (!fs.existsSync(this.cacheFile)) return;
    try {
      const data = JSON.parse(fs.readFileSync(this.cacheFile, 'utf8')) as CacheManifest;
      if (
        data &&
        data.version === CACHE_VERSION &&
        data.entries &&
        typeof data.entries === 'object'
      ) {
        this.entries = data.entries;
      }
    } catch {
      this.entries = {};
    }
  }

  getTemplateHash(): string {
    return this.templateHash;
  }

  hashSourceContent(content: string): string {
    return hashContent(content);
  }

  isUnchanged(relPath: string, sourceHash?: string): boolean {
    const entry = this.entries[relPath];
    if (!entry) return false;
    if (entry.templateHash !== this.templateHash) return false;
    const currentSourceHash =
      sourceHash ??
      hashContent(fs.readFileSync(path.join(this.contentDir, relPath), 'utf8'));
    if (entry.sourceHash !== currentSourceHash) return false;
    return true;
  }

  getPage(relPath: string): Page | undefined {
    return this.entries[relPath]?.page;
  }

  getEntry(relPath: string): CacheEntry | undefined {
    return this.entries[relPath];
  }

  record(relPath: string, page: Page, html: string, renderMs: number): void {
    const prev = this.entries[relPath];
    if (prev && prev.page.slug && prev.page.slug !== page.slug) {
      const oldOut = path.join(this.outputDir, `${prev.page.slug}.html`);
      if (fs.existsSync(oldOut)) fs.rmSync(oldOut);
    }
    const sourceHash = hashContent(
      fs.readFileSync(path.join(this.contentDir, relPath), 'utf8')
    );
    this.entries[relPath] = {
      sourceHash,
      templateHash: this.templateHash,
      page,
      html,
      renderMs,
    };
  }

  removeStale(activeFiles: string[], outputDir: string): void {
    for (const rel of Object.keys(this.entries)) {
      if (activeFiles.includes(rel)) continue;
      const entry = this.entries[rel];
      const out = path.join(outputDir, `${entry.page.slug}.html`);
      if (fs.existsSync(out)) fs.rmSync(out);
      delete this.entries[rel];
    }
  }

  save(): void {
    fs.mkdirSync(path.dirname(this.cacheFile), { recursive: true });
    const manifest: CacheManifest = { version: CACHE_VERSION, entries: this.entries };
    fs.writeFileSync(this.cacheFile, JSON.stringify(manifest, null, 2), 'utf8');
  }
}
