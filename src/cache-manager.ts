import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';

export interface CacheEntry {
  filename: string;
  fileHash: string;
  templateHash?: string;
  layoutHash?: string;
  html?: string;
  title?: string;
  date?: string;
  tags?: string[];
  timestamp: number;
}

export interface CacheManifest {
  version: string;
  entries: Record<string, CacheEntry>;
}

export class CacheManager {
  private cacheFile: string;
  private manifest: CacheManifest;

  constructor(outputDir: string) {
    this.cacheFile = path.join(outputDir, '.ssg-cache.json');
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

  saveManifest(): void {
    const outputDir = path.dirname(this.cacheFile);
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }
    fs.writeFileSync(this.cacheFile, JSON.stringify(this.manifest, null, 2));
  }

  getEntry(filename: string): CacheEntry | undefined {
    return this.manifest.entries[filename];
  }

  setEntry(filename: string, entry: CacheEntry): void {
    this.manifest.entries[filename] = entry;
  }

  hasEntry(filename: string): boolean {
    return filename in this.manifest.entries;
  }

  removeEntry(filename: string): void {
    delete this.manifest.entries[filename];
  }

  isFileChanged(filename: string, fileContent: string, templatePath?: string, layoutPath?: string): boolean {
    const entry = this.getEntry(filename);
    if (!entry) {
      return true;
    }

    const fileHash = this.hashContent(fileContent);
    if (fileHash !== entry.fileHash) {
      return true;
    }

    if (templatePath && fs.existsSync(templatePath)) {
      const templateContent = fs.readFileSync(templatePath, 'utf-8');
      const templateHash = this.hashContent(templateContent);
      if (templateHash !== entry.templateHash) {
        return true;
      }
    }

    if (layoutPath && fs.existsSync(layoutPath)) {
      const layoutContent = fs.readFileSync(layoutPath, 'utf-8');
      const layoutHash = this.hashContent(layoutContent);
      if (layoutHash !== entry.layoutHash) {
        return true;
      }
    }

    return false;
  }

  updateEntry(
    filename: string,
    fileContent: string,
    html: string,
    templatePath?: string,
    layoutPath?: string,
    metadata?: { title?: string; date?: string; tags?: string[] }
  ): void {
    const fileHash = this.hashContent(fileContent);
    let templateHash: string | undefined;
    let layoutHash: string | undefined;

    if (templatePath && fs.existsSync(templatePath)) {
      const templateContent = fs.readFileSync(templatePath, 'utf-8');
      templateHash = this.hashContent(templateContent);
    }

    if (layoutPath && fs.existsSync(layoutPath)) {
      const layoutContent = fs.readFileSync(layoutPath, 'utf-8');
      layoutHash = this.hashContent(layoutContent);
    }

    this.setEntry(filename, {
      filename,
      fileHash,
      templateHash,
      layoutHash,
      html,
      title: metadata?.title,
      date: metadata?.date,
      tags: metadata?.tags,
      timestamp: Date.now(),
    });
  }

  clear(): void {
    this.manifest.entries = {};
  }

  getEntries(): CacheEntry[] {
    return Object.values(this.manifest.entries);
  }

  getAllFilenames(): string[] {
    return Object.keys(this.manifest.entries);
  }
}
