import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import { PageData, PageFrontmatter } from './types';

export interface CacheEntry {
  slug: string;
  contentHash: string;
  templateHash: string;
  html: string;
  frontmatter: PageFrontmatter;
}

export interface CacheManifest {
  version: number;
  entries: Record<string, CacheEntry>;
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  timeSavedMs: number;
}

const CACHE_FILE = '.ssg-cache.json';

function hashString(input: string): string {
  return crypto.createHash('sha256').update(input).digest('hex');
}

function hashFile(filePath: string): string {
  if (!fs.existsSync(filePath)) return '';
  return hashString(fs.readFileSync(filePath, 'utf-8'));
}

function hashDirectoryTemplates(dir: string): string {
  if (!fs.existsSync(dir)) return hashString('');
  const combined: string[] = [];
  const walkDir = (d: string) => {
    for (const entry of fs.readdirSync(d, { withFileTypes: true })) {
      const full = path.join(d, entry.name);
      if (entry.isDirectory()) {
        walkDir(full);
      } else if (entry.name.endsWith('.hbs')) {
        combined.push(entry.name + ':' + hashFile(full));
      }
    }
  };
  walkDir(dir);
  combined.sort();
  return hashString(combined.join('|'));
}

export class CacheManager {
  private outputDir: string;
  private manifest: CacheManifest;

  constructor(outputDir: string) {
    this.outputDir = outputDir;
    this.manifest = { version: 1, entries: {} };
  }

  load(): boolean {
    const cachePath = path.join(this.outputDir, CACHE_FILE);
    if (!fs.existsSync(cachePath)) return false;
    try {
      const raw = fs.readFileSync(cachePath, 'utf-8');
      const parsed = JSON.parse(raw);
      if (parsed && parsed.version === 1 && parsed.entries) {
        this.manifest = parsed;
        return true;
      }
    } catch {
      // corrupted cache, start fresh
    }
    return false;
  }

  save(): void {
    const cachePath = path.join(this.outputDir, CACHE_FILE);
    const dir = path.dirname(cachePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(cachePath, JSON.stringify(this.manifest, null, 2));
  }

  delete(): void {
    const cachePath = path.join(this.outputDir, CACHE_FILE);
    if (fs.existsSync(cachePath)) {
      fs.unlinkSync(cachePath);
    }
    this.manifest = { version: 1, entries: {} };
  }

  getEntry(slug: string): CacheEntry | undefined {
    return this.manifest.entries[slug];
  }

  setEntry(entry: CacheEntry): void {
    this.manifest.entries[entry.slug] = entry;
  }

  isStale(slug: string, contentHash: string, templateHash: string): boolean {
    const entry = this.manifest.entries[slug];
    if (!entry) return true;
    if (entry.contentHash !== contentHash) return true;
    if (entry.templateHash !== templateHash) return true;
    return false;
  }

  getCachedPage(slug: string): { html: string; frontmatter: PageFrontmatter } | null {
    const entry = this.manifest.entries[slug];
    if (!entry) return null;
    return { html: entry.html, frontmatter: entry.frontmatter };
  }

  static computeContentHash(filePath: string): string {
    return hashFile(filePath);
  }

  static computeTemplateHash(templatesDir: string): string {
    return hashDirectoryTemplates(templatesDir);
  }

  getCachedHtmlMap(): Map<string, string> {
    const map = new Map<string, string>();
    for (const [slug, entry] of Object.entries(this.manifest.entries)) {
      map.set(slug, entry.html);
    }
    return map;
  }
}
