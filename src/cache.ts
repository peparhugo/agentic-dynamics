import { createHash } from 'crypto';
import { promises as fs } from 'fs';
import * as path from 'path';

import type { BuildOptions, BuildStats, Page } from './types';

export const CACHE_VERSION = 1;
export const DEFAULT_CACHE_FILE = '.ssg-cache.json';
export const CACHE_KEY = 'ssg:incrementalCache';

export interface CachedEntry {
  sourceFile: string;
  output: string;
  sourceHash: string;
  templateHash: string;
  page: Page;
  html: string;
  renderMs: number;
}

export interface CacheIndex {
  templateHash: string;
  html: string;
  renderMs: number;
}

export interface CacheManifest {
  version: number;
  entries: Record<string, CachedEntry>;
  index: CacheIndex | null;
}

export function hashContent(content: string): string {
  return createHash('sha256').update(content).digest('hex');
}

export async function hashFile(filePath: string): Promise<string | null> {
  try {
    return hashContent(await fs.readFile(filePath, 'utf8'));
  } catch {
    return null;
  }
}

async function listTemplateFiles(templateDir: string): Promise<string[]> {
  const out: string[] = [];
  let entries;
  try {
    entries = await fs.readdir(templateDir, { withFileTypes: true });
  } catch {
    return out;
  }
  for (const entry of entries) {
    const full = path.join(templateDir, entry.name);
    if (entry.isDirectory()) {
      out.push(...(await listTemplateFiles(full)));
    } else if (entry.isFile() && /\.hbs$/i.test(entry.name)) {
      out.push(full);
    }
  }
  return out.sort();
}

export async function hashTemplateDir(templateDir: string): Promise<string | null> {
  const files = await listTemplateFiles(templateDir);
  if (files.length === 0) {
    return null;
  }
  const hash = createHash('sha256');
  for (const file of files) {
    let content: string;
    try {
      content = await fs.readFile(file, 'utf8');
    } catch {
      continue;
    }
    hash.update(path.relative(templateDir, file).replace(/\\/g, '/'));
    hash.update('\0');
    hash.update(content);
  }
  return hash.digest('hex');
}

export async function loadManifest(cacheFile: string): Promise<CacheManifest | null> {
  try {
    const raw: unknown = JSON.parse(await fs.readFile(cacheFile, 'utf8'));
    if (
      raw &&
      typeof raw === 'object' &&
      (raw as CacheManifest).version === CACHE_VERSION &&
      (raw as CacheManifest).entries &&
      typeof (raw as CacheManifest).entries === 'object'
    ) {
      return raw as CacheManifest;
    }
    return null;
  } catch {
    return null;
  }
}

export async function saveManifest(cacheFile: string, manifest: CacheManifest): Promise<void> {
  await fs.mkdir(path.dirname(cacheFile), { recursive: true });
  await fs.writeFile(cacheFile, JSON.stringify(manifest, null, 2), 'utf8');
}

export interface CacheDecision {
  skipped: boolean;
  page?: Page;
}

export class BuildCache {
  static cacheFileFor(options: BuildOptions): string {
    return options.cacheFile ?? path.join(options.outputDir, DEFAULT_CACHE_FILE);
  }

  static async create(options: BuildOptions): Promise<BuildCache | null> {
    if (!options.incremental) {
      return null;
    }
    const cacheFile = BuildCache.cacheFileFor(options);
    const manifest = options.clean ? null : await loadManifest(cacheFile);
    const templateHash = await hashTemplateDir(options.templateDir ?? 'templates');
    return new BuildCache(
      cacheFile,
      options.outputDir,
      !!options.clean,
      manifest ?? { version: CACHE_VERSION, entries: {}, index: null },
      templateHash
    );
  }

  readonly cacheFile: string;
  readonly skippedOutputs: Set<string> = new Set();

  built = 0;
  skipped = 0;
  timeSavedMs = 0;

  private readonly outputDir: string;
  private readonly clean: boolean;
  private readonly manifest: CacheManifest;
  private readonly previousBySource: Map<string, CachedEntry>;
  private readonly templateHash: string | null;
  private readonly sourceHashes: Map<string, string> = new Map();
  private readonly parsedPages: Map<string, { sourceHash: string; page: Page; startedAt: number }> =
    new Map();
  private readonly nextEntries: Map<string, CachedEntry> = new Map();
  private index: CacheIndex | null = null;

  private constructor(
    cacheFile: string,
    outputDir: string,
    clean: boolean,
    manifest: CacheManifest,
    templateHash: string | null
  ) {
    this.cacheFile = cacheFile;
    this.outputDir = outputDir;
    this.clean = clean;
    this.manifest = manifest;
    this.templateHash = templateHash;
    this.previousBySource = new Map();
    for (const entry of Object.values(manifest.entries)) {
      if (entry && typeof entry.sourceFile === 'string') {
        this.previousBySource.set(entry.sourceFile, entry);
      }
    }
  }

  async decide(sourceFile: string): Promise<CacheDecision> {
    const sourceHash = await hashFile(sourceFile);
    if (!sourceHash) {
      return { skipped: false };
    }
    this.sourceHashes.set(sourceFile, sourceHash);
    const cached = this.previousBySource.get(sourceFile);
    if (
      cached &&
      cached.sourceHash === sourceHash &&
      cached.templateHash === (this.templateHash ?? '') &&
      (await this.outputExists(cached.output))
    ) {
      this.skipped += 1;
      this.timeSavedMs += cached.renderMs;
      this.skippedOutputs.add(cached.output);
      this.nextEntries.set(cached.output, cached);
      return { skipped: true, page: cached.page };
    }
    return { skipped: false };
  }

  isSkipped(output: string): boolean {
    return this.skippedOutputs.has(output);
  }

  cachedHtml(output: string): string {
    const entry = this.nextEntries.get(output);
    return entry ? entry.html : '';
  }

  recordParsed(sourceFile: string, page: Page, startedAt: number): void {
    const sourceHash = this.sourceHashes.get(sourceFile) ?? '';
    this.parsedPages.set(sourceFile, { sourceHash, page, startedAt });
  }

  recordRendered(sourceFile: string, output: string, html: string): void {
    const parsed = this.parsedPages.get(sourceFile);
    if (!parsed) {
      return;
    }
    this.nextEntries.set(output, {
      sourceFile,
      output,
      sourceHash: parsed.sourceHash,
      templateHash: this.templateHash ?? '',
      page: parsed.page,
      html,
      renderMs: Date.now() - parsed.startedAt,
    });
    this.built += 1;
  }

  async shouldSkipIndex(): Promise<boolean> {
    const prevIndex = this.manifest.index;
    if (!prevIndex) {
      return false;
    }
    if (prevIndex.templateHash !== (this.templateHash ?? '')) {
      return false;
    }
    if (this.built > 0 || this.countDeleted() > 0) {
      return false;
    }
    return this.outputExists('index.html');
  }

  skipIndex(): void {
    this.index = this.manifest.index;
  }

  recordIndex(html: string, renderMs: number): void {
    this.index = { templateHash: this.templateHash ?? '', html, renderMs };
  }

  cachedIndexHtml(): string {
    return this.index?.html ?? '';
  }

  async removeStaleOutputs(): Promise<void> {
    for (const entry of this.previousBySource.values()) {
      if (this.nextEntries.has(entry.output)) {
        continue;
      }
      try {
        await fs.unlink(path.join(this.outputDir, entry.output));
      } catch {
        // ignore missing files
      }
    }
  }

  async save(): Promise<void> {
    const entries: Record<string, CachedEntry> = {};
    for (const [output, entry] of this.nextEntries) {
      entries[output] = entry;
    }
    await saveManifest(this.cacheFile, {
      version: CACHE_VERSION,
      entries,
      index: this.index,
    });
  }

  report(durationMs: number): BuildStats {
    return {
      incremental: true,
      clean: this.clean,
      total: this.built + this.skipped,
      built: this.built,
      skipped: this.skipped,
      timeSavedMs: this.timeSavedMs,
      durationMs,
    };
  }

  private countDeleted(): number {
    let count = 0;
    for (const entry of this.previousBySource.values()) {
      if (!this.nextEntries.has(entry.output)) {
        count += 1;
      }
    }
    return count;
  }

  private async outputExists(relative: string): Promise<boolean> {
    try {
      await fs.access(path.join(this.outputDir, relative));
      return true;
    } catch {
      return false;
    }
  }
}
