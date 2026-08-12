import { createHash } from 'crypto';
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'fs';
import { dirname, join, posix, sep } from 'path';

export const CACHE_FILE_NAME = '.ssg-cache.json';
export const CACHE_VERSION = 1;

const TEMPLATE_EXTENSIONS = new Set(['.hbs', '.ejs']);

export interface CachedFrontmatter {
  title?: string;
  date?: string;
  tags?: string[];
  template?: string;
  layout?: string;
}

export interface CachedPageData {
  sourceHash: string;
  frontmatter: CachedFrontmatter;
  contentHtml: string;
  html: string;
  buildTimeMs: number;
}

export interface CacheManifest {
  version: number;
  templateHash: string;
  pages: Record<string, CachedPageData>;
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  timeSavedMs: number;
}

export function hashContent(content: string): string {
  return createHash('sha256').update(content, 'utf8').digest('hex');
}

export function hashFile(filePath: string): string {
  return hashContent(readFileSync(filePath, 'utf8'));
}

export function toPosixPath(relPath: string): string {
  return relPath.split(sep).join(posix.sep);
}

function extensionOf(name: string): string {
  const idx = name.lastIndexOf('.');
  return idx === -1 ? '' : name.slice(idx);
}

function collectTemplateFiles(dir: string, out: string[]): void {
  if (!existsSync(dir)) return;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      collectTemplateFiles(fullPath, out);
    } else if (entry.isFile() && TEMPLATE_EXTENSIONS.has(extensionOf(entry.name))) {
      out.push(fullPath);
    }
  }
}

export function computeTemplateHash(templatesDir: string): string {
  const files: string[] = [];
  collectTemplateFiles(templatesDir, files);
  files.sort();
  const hash = createHash('sha256');
  for (const file of files) {
    hash.update(file);
    hash.update('\0');
    hash.update(readFileSync(file, 'utf8'));
  }
  return hash.digest('hex');
}

function emptyManifest(): CacheManifest {
  return { version: CACHE_VERSION, templateHash: '', pages: {} };
}

export class IncrementalCache {
  private readonly manifest: CacheManifest;

  private constructor(private readonly cachePath: string, manifest: CacheManifest) {
    this.manifest = manifest;
  }

  static load(outputDir: string, clean: boolean): IncrementalCache {
    const cachePath = join(outputDir, CACHE_FILE_NAME);
    if (!clean && existsSync(cachePath)) {
      try {
        const parsed = JSON.parse(readFileSync(cachePath, 'utf8')) as CacheManifest;
        if (
          parsed !== null &&
          typeof parsed === 'object' &&
          parsed.version === CACHE_VERSION &&
          parsed.pages !== null &&
          typeof parsed.pages === 'object'
        ) {
          return new IncrementalCache(cachePath, parsed);
        }
      } catch {
        // fall through to an empty manifest
      }
    }
    return new IncrementalCache(cachePath, emptyManifest());
  }

  get templateHash(): string {
    return this.manifest.templateHash;
  }

  setTemplateHash(value: string): void {
    this.manifest.templateHash = value;
  }

  get pages(): Record<string, CachedPageData> {
    return this.manifest.pages;
  }

  get(relPath: string): CachedPageData | undefined {
    return this.manifest.pages[relPath];
  }

  set(relPath: string, data: CachedPageData): void {
    this.manifest.pages[relPath] = data;
  }

  delete(relPath: string): void {
    delete this.manifest.pages[relPath];
  }

  save(): void {
    mkdirSync(dirname(this.cachePath), { recursive: true });
    writeFileSync(this.cachePath, JSON.stringify(this.manifest, null, 2), 'utf8');
  }
}
