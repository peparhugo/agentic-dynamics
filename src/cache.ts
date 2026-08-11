import crypto from 'crypto';
import fs from 'fs';
import path from 'path';
import { Page } from './plugin';

export interface ManifestEntry {
  hash: string;
  slug: string;
  lastBuilt: number;
}

export interface CacheManifest {
  templates?: string;
  pages: Record<string, ManifestEntry>;
}

export interface BuildStats {
  totalPages: number;
  pagesBuilt: number;
  pagesSkipped: number;
  timeSaved: string;
}

function gatherTemplateFiles(dir: string): string[] {
  const files: string[] = [];
  if (!fs.existsSync(dir)) return files;
  const entries = fs.readdirSync(dir);
  for (const entry of entries.sort()) {
    const fullPath = path.join(dir, entry);
    if (fs.statSync(fullPath).isDirectory()) {
      files.push(...gatherTemplateFiles(fullPath));
    } else if (entry.endsWith('.hbs')) {
      files.push(fullPath);
    }
  }
  return files;
}

function hashContent(content: string): string {
  return crypto.createHash('md5').update(content).digest('hex');
}

function hashFile(filePath: string): string {
  try {
    return hashContent(fs.readFileSync(filePath, 'utf-8'));
  } catch {
    return '';
  }
}

function hashTemplatesDir(templatesDir: string): string {
  if (!fs.existsSync(templatesDir)) return '';
  const files = gatherTemplateFiles(templatesDir);
  const combined = files.map((f) => fs.readFileSync(f, 'utf-8')).join('\n');
  return hashContent(combined);
}

function loadManifest(manifestPath: string): CacheManifest | null {
  try {
    if (fs.existsSync(manifestPath)) {
      return JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
    }
  } catch {
    // corrupted manifest
  }
  return null;
}

function saveManifest(manifestPath: string, manifest: CacheManifest): void {
  fs.mkdirSync(path.dirname(manifestPath), { recursive: true });
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
}

const AVG_MS_PER_PAGE = 50;

export class BuildCache {
  private contentDir: string;
  private outputDir: string;
  private templatesDir?: string;
  private manifestPath: string;
  private manifest: CacheManifest | null;
  private inMemoryHtmlCache: Map<string, string>;
  private inMemoryFmCache: Map<string, Page>;
  private _currentTplHash: string | null;
  private _currentTplHashComputed: boolean;
  public stats: BuildStats;

  constructor(contentDir: string, outputDir: string, templatesDir?: string) {
    this.contentDir = contentDir;
    this.outputDir = outputDir;
    this.templatesDir = templatesDir;
    this.manifestPath = path.join(contentDir, '.ssg-cache.json');
    this.manifest = null;
    this.inMemoryHtmlCache = new Map();
    this.inMemoryFmCache = new Map();
    this._currentTplHash = null;
    this._currentTplHashComputed = false;
    this.stats = { totalPages: 0, pagesBuilt: 0, pagesSkipped: 0, timeSaved: '0ms' };
  }

  load(): void {
    this.manifest = loadManifest(this.manifestPath);
  }

  hasValidManifest(): boolean {
    return this.manifest !== null;
  }

  clear(): void {
    try {
      if (fs.existsSync(this.manifestPath)) {
        fs.unlinkSync(this.manifestPath);
      }
    } catch {
      // ignore
    }
    this.manifest = null;
    this.inMemoryHtmlCache.clear();
    this.inMemoryFmCache.clear();
    this._currentTplHash = null;
    this._currentTplHashComputed = false;
  }

  private currentTemplateHash(): string {
    if (!this._currentTplHashComputed) {
      this._currentTplHashComputed = true;
      this._currentTplHash = this.templatesDir && fs.existsSync(this.templatesDir)
        ? hashTemplatesDir(this.templatesDir)
        : '';
    }
    return this._currentTplHash || '';
  }

  shouldSkipFile(sourcePath: string, slug: string): boolean {
    if (!this.manifest) return false;

    const entry = this.manifest.pages[slug];
    if (!entry) return false;

    const currentSourceHash = hashFile(sourcePath);
    if (entry.hash !== currentSourceHash) return false;

    const outputPath = path.join(this.outputDir, `${slug}.html`);
    if (!fs.existsSync(outputPath)) return false;

    if (this.templatesDir) {
      const tplHash = this.currentTemplateHash();
      if (this.manifest.templates !== tplHash) return false;
    }

    return true;
  }

  updateManifest(sourcePath: string, slug: string): void {
    if (!this.manifest) {
      this.manifest = { pages: {} };
    }

    const currentHash = hashFile(sourcePath);
    this.manifest.pages[slug] = { hash: currentHash, slug, lastBuilt: Date.now() };
  }

  finalize(): void {
    if (this.manifest && this.templatesDir) {
      this.manifest.templates = this.currentTemplateHash();
    }
  }

  getCurrentTemplateHash(): string {
    return this.currentTemplateHash();
  }

  removeStaleEntries(knownSlugs: Set<string>): void {
    if (!this.manifest) return;
    for (const key of Object.keys(this.manifest.pages)) {
      if (!knownSlugs.has(key)) {
        delete this.manifest.pages[key];
      }
    }
  }

  persist(): void {
    if (this.manifest) {
      saveManifest(this.manifestPath, this.manifest);
    }
  }

  cacheHtml(slug: string, html: string): void {
    this.inMemoryHtmlCache.set(slug, html);
  }

  getCachedHtml(slug: string): string | undefined {
    return this.inMemoryHtmlCache.get(slug);
  }

  cacheFrontmatter(slug: string, page: Page): void {
    this.inMemoryFmCache.set(slug, page);
  }

  getCachedFrontmatter(slug: string): Page | undefined {
    return this.inMemoryFmCache.get(slug);
  }

  computeSourceHash(sourcePath: string): string {
    return hashFile(sourcePath);
  }

  reportStats(consoleLog: boolean = true): void {
    const { pagesBuilt, pagesSkipped } = this.stats;
    const total = pagesBuilt + pagesSkipped;
    const savedMs = pagesSkipped * AVG_MS_PER_PAGE;
    this.stats.timeSaved = `${savedMs}ms`;

    if (consoleLog) {
      const pct = total > 0 ? Math.round((pagesSkipped / total) * 100) : 0;
      console.log(
        `Build stats: ${pagesBuilt} built, ${pagesSkipped} skipped (${savedMs}ms saved, ~${pct}% cached)`
      );
    }
  }
}

export { hashFile, hashContent, hashTemplatesDir as hashDirectoryTemplates };
