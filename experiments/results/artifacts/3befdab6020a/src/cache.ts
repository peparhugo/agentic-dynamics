import fs from 'fs';
import path from 'path';
import crypto from 'crypto';

export interface CacheEntry {
  slug: string;
  sourceHash: string;
  templatesHash: string;
}

export interface CacheManifest {
  version: number;
  pages: Record<string, CacheEntry>;
}

export class CacheManager {
  private cachePath: string;
  private manifest: CacheManifest;

  constructor(outputDir: string) {
    this.cachePath = path.join(outputDir, '.ssg-cache.json');
    this.manifest = { version: 1, pages: {} };
  }

  load(): void {
    try {
      if (fs.existsSync(this.cachePath)) {
        const raw = fs.readFileSync(this.cachePath, 'utf-8');
        this.manifest = JSON.parse(raw);
      }
    } catch {
      this.manifest = { version: 1, pages: {} };
    }
  }

  save(): void {
    const dir = path.dirname(this.cachePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(this.cachePath, JSON.stringify(this.manifest, null, 2), 'utf-8');
  }

  clear(): void {
    this.manifest = { version: 1, pages: {} };
    try {
      if (fs.existsSync(this.cachePath)) {
        fs.unlinkSync(this.cachePath);
      }
    } catch {
      // ignore
    }
  }

  isStale(slug: string, sourceHash: string, templatesHash: string): boolean {
    const entry = this.manifest.pages[slug];
    if (!entry) return true;
    return entry.sourceHash !== sourceHash || entry.templatesHash !== templatesHash;
  }

  update(slug: string, sourceHash: string, templatesHash: string): void {
    this.manifest.pages[slug] = { slug, sourceHash, templatesHash };
  }

  prune(knownSlugs: string[]): number {
    const slugSet = new Set(knownSlugs);
    let removed = 0;
    for (const key of Object.keys(this.manifest.pages)) {
      if (!slugSet.has(key)) {
        delete this.manifest.pages[key];
        removed++;
      }
    }
    return removed;
  }

  static computeHash(content: string): string {
    return crypto.createHash('sha256').update(content).digest('hex');
  }

  static computeTemplateHashes(templatesDir: string): string {
    const resolved = path.resolve(templatesDir);
    if (!fs.existsSync(resolved)) {
      return 'builtin-defaults';
    }

    const hashes: string[] = [];
    const walk = (dir: string): void => {
      const entries = fs.readdirSync(dir, { withFileTypes: true });
      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          walk(fullPath);
        } else if (entry.isFile() && entry.name.endsWith('.hbs')) {
          const content = fs.readFileSync(fullPath, 'utf-8');
          hashes.push(`${fullPath}:${CacheManager.computeHash(content)}`);
        }
      }
    };

    walk(resolved);
    hashes.sort();
    return CacheManager.computeHash(hashes.join('\n'));
  }

  static computeFileHash(filePath: string): string {
    const content = fs.readFileSync(filePath, 'utf-8');
    return CacheManager.computeHash(content);
  }
}
