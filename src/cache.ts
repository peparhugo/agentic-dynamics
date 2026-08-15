import { promises as fs } from 'fs';
import path from 'path';
import crypto from 'crypto';

export interface CacheEntry {
  sourceHash: string;
  templateHash?: string;
  layoutHash?: string;
  renderedHtml?: string;
  timestamp: number;
}

export interface CacheManifest {
  version: string;
  entries: { [slug: string]: CacheEntry };
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  timeSaved: number;
  totalPages: number;
}

export class CacheManager {
  private cacheFile: string;
  private manifest: CacheManifest;
  private isDirty: boolean = false;
  private startTime: number = Date.now();
  private pageBuildTimes: Map<string, number> = new Map();

  constructor(outputDir: string) {
    this.cacheFile = path.join(outputDir, '.ssg-cache.json');
    this.manifest = { version: '1', entries: {} };
  }

  async load(): Promise<void> {
    try {
      const content = await fs.readFile(this.cacheFile, 'utf-8');
      this.manifest = JSON.parse(content);
    } catch (error) {
      this.manifest = { version: '1', entries: {} };
    }
  }

  async save(): Promise<void> {
    if (!this.isDirty) return;

    const dir = path.dirname(this.cacheFile);
    await fs.mkdir(dir, { recursive: true });
    await fs.writeFile(this.cacheFile, JSON.stringify(this.manifest, null, 2), 'utf-8');
  }

  private hashContent(content: string): string {
    return crypto.createHash('sha256').update(content).digest('hex');
  }

  async isPageChanged(slug: string, sourceContent: string, templateContent?: string, layoutContent?: string): Promise<boolean> {
    const sourceHash = this.hashContent(sourceContent);
    const templateHash = templateContent ? this.hashContent(templateContent) : undefined;
    const layoutHash = layoutContent ? this.hashContent(layoutContent) : undefined;

    const entry = this.manifest.entries[slug];
    if (!entry) return true;

    if (entry.sourceHash !== sourceHash) return true;
    if (templateHash && entry.templateHash !== templateHash) return true;
    if (layoutHash && entry.layoutHash !== layoutHash) return true;

    return false;
  }

  updateEntry(
    slug: string,
    sourceContent: string,
    renderedHtml: string,
    templateContent?: string,
    layoutContent?: string
  ): void {
    const sourceHash = this.hashContent(sourceContent);
    const templateHash = templateContent ? this.hashContent(templateContent) : undefined;
    const layoutHash = layoutContent ? this.hashContent(layoutContent) : undefined;

    this.manifest.entries[slug] = {
      sourceHash,
      templateHash,
      layoutHash,
      renderedHtml,
      timestamp: Date.now()
    };

    this.isDirty = true;
  }

  getCachedHtml(slug: string): string | undefined {
    return this.manifest.entries[slug]?.renderedHtml;
  }

  recordPageBuildTime(slug: string, buildTimeMs: number): void {
    this.pageBuildTimes.set(slug, buildTimeMs);
  }

  getStats(totalPages: number, skippedSlugs: Set<string>): BuildStats {
    const pagesBuilt = totalPages - skippedSlugs.size;
    const pagesSkipped = skippedSlugs.size;

    let timeSaved = 0;
    for (const slug of skippedSlugs) {
      const buildTime = this.pageBuildTimes.get(slug) || 50;
      timeSaved += buildTime;
    }

    return {
      pagesBuilt,
      pagesSkipped,
      timeSaved,
      totalPages
    };
  }

  clear(): void {
    this.manifest = { version: '1', entries: {} };
    this.isDirty = true;
  }
}
