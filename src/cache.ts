import fs from 'fs';
import path from 'path';
import crypto from 'crypto';

export interface CacheEntry {
  hash: string;
  templateHash?: string;
  timestamp: number;
}

export interface CacheData {
  version: number;
  entries: Record<string, CacheEntry>;
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  timeSaved: number;
}

export class CacheManager {
  private cachePath: string;
  private cacheData: CacheData;
  private buildStartTime: number = Date.now();

  constructor(outputDir: string) {
    this.cachePath = path.join(outputDir, '.ssg-cache.json');
    this.cacheData = this.loadCache();
  }

  private loadCache(): CacheData {
    if (fs.existsSync(this.cachePath)) {
      try {
        const data = fs.readFileSync(this.cachePath, 'utf-8');
        return JSON.parse(data);
      } catch (error) {
        return { version: 1, entries: {} };
      }
    }
    return { version: 1, entries: {} };
  }

  private computeHash(content: string): string {
    return crypto
      .createHash('sha256')
      .update(content)
      .digest('hex');
  }

  private getFileHash(filePath: string): string {
    if (!fs.existsSync(filePath)) {
      return '';
    }
    const content = fs.readFileSync(filePath, 'utf-8');
    return this.computeHash(content);
  }

  hasChanged(
    fileKey: string,
    content: string,
    templatePath?: string
  ): boolean {
    const currentHash = this.computeHash(content);
    const templateHash = templatePath ? this.getFileHash(templatePath) : undefined;

    const cached = this.cacheData.entries[fileKey];

    if (!cached) {
      return true;
    }

    if (cached.hash !== currentHash) {
      return true;
    }

    if (templateHash && cached.templateHash !== templateHash) {
      return true;
    }

    return false;
  }

  updateEntry(
    fileKey: string,
    content: string,
    templatePath?: string
  ): void {
    const hash = this.computeHash(content);
    const templateHash = templatePath ? this.getFileHash(templatePath) : undefined;

    this.cacheData.entries[fileKey] = {
      hash,
      templateHash,
      timestamp: Date.now()
    };
  }

  save(): void {
    const dir = path.dirname(this.cachePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(
      this.cachePath,
      JSON.stringify(this.cacheData, null, 2),
      'utf-8'
    );
  }

  clear(): void {
    this.cacheData = { version: 1, entries: {} };
  }

  getStats(pagesBuilt: number, pagesSkipped: number): BuildStats {
    const timeSaved = pagesSkipped > 0 ? Date.now() - this.buildStartTime : 0;
    return {
      pagesBuilt,
      pagesSkipped,
      timeSaved
    };
  }
}
