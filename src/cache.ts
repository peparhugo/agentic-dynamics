import fs from 'fs';
import path from 'path';
import crypto from 'crypto';

export interface CacheEntry {
  fileHash: string;
  templateHash: string;
  htmlHash: string;
  frontmatterHash: string;
  timestamp: number;
}

export interface CacheManifest {
  version: string;
  entries: { [filePath: string]: CacheEntry };
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  timeSaved: number;
}

export class BuildCache {
  private cacheFile: string;
  private manifest: CacheManifest;
  private buildStart: number = 0;

  constructor(cacheDir: string = '.') {
    this.cacheFile = path.join(cacheDir, '.ssg-cache.json');
    this.manifest = this.loadManifest();
  }

  private loadManifest(): CacheManifest {
    if (fs.existsSync(this.cacheFile)) {
      try {
        const content = fs.readFileSync(this.cacheFile, 'utf-8');
        return JSON.parse(content);
      } catch {
        return { version: '1.0.0', entries: {} };
      }
    }
    return { version: '1.0.0', entries: {} };
  }

  private hashContent(content: string): string {
    return crypto.createHash('sha256').update(content).digest('hex');
  }

  getFileHash(filePath: string): string | null {
    if (!fs.existsSync(filePath)) {
      return null;
    }
    const content = fs.readFileSync(filePath, 'utf-8');
    return this.hashContent(content);
  }

  isCached(
    filePath: string,
    templatePath: string | null,
    currentFileHash: string,
    currentTemplateHash: string | null
  ): boolean {
    const entry = this.manifest.entries[filePath];
    if (!entry) {
      return false;
    }

    const fileHashMatch = entry.fileHash === currentFileHash;
    const templateHashMatch = currentTemplateHash === null || entry.templateHash === currentTemplateHash;

    return fileHashMatch && templateHashMatch;
  }

  getCacheEntry(filePath: string): CacheEntry | null {
    return this.manifest.entries[filePath] || null;
  }

  setCacheEntry(
    filePath: string,
    fileHash: string,
    templateHash: string,
    html: string,
    frontmatterStr: string
  ): void {
    this.manifest.entries[filePath] = {
      fileHash,
      templateHash,
      htmlHash: this.hashContent(html),
      frontmatterHash: this.hashContent(frontmatterStr),
      timestamp: Date.now(),
    };
  }

  invalidateCacheEntry(filePath: string): void {
    delete this.manifest.entries[filePath];
  }

  save(): void {
    const cacheDir = path.dirname(this.cacheFile);
    if (!fs.existsSync(cacheDir)) {
      fs.mkdirSync(cacheDir, { recursive: true });
    }
    fs.writeFileSync(this.cacheFile, JSON.stringify(this.manifest, null, 2), 'utf-8');
  }

  clear(): void {
    this.manifest.entries = {};
    this.save();
  }

  startBuild(): void {
    this.buildStart = Date.now();
  }

  getStats(pagesBuilt: number, pagesSkipped: number): BuildStats {
    const buildTime = Date.now() - this.buildStart;
    const timeSaved = pagesSkipped * Math.max(0, buildTime / (pagesBuilt + 1));
    return {
      pagesBuilt,
      pagesSkipped,
      timeSaved: Math.round(timeSaved),
    };
  }
}

export function createBuildCache(cacheDir: string = '.'): BuildCache {
  return new BuildCache(cacheDir);
}
