import * as fs from 'fs';
import * as path from 'path';
import type { Plugin, PluginContext, PluginConfig } from './plugin';
import type { Page } from './types';
import {
  CACHE_VERSION,
  deleteCacheManifest,
  hashDirectory,
  hashFile,
  loadCacheManifest,
  saveCacheManifest,
  type CacheEntry,
} from './cache';

const DEFAULT_CACHE_FILE_NAME = '.ssg-cache.json';

export interface EngineOptions {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  plugins: Plugin[];
  config?: PluginConfig;
  /** When true, pages whose source file and the templates directory are unchanged since the last cached build reuse their cached result instead of re-running the plugin pipeline. */
  incremental?: boolean;
  /** Forces a full rebuild: any existing cache manifest is discarded before the build runs. */
  clean?: boolean;
  /** Path to the incremental build cache manifest. Defaults to `.ssg-cache.json` inside outputDir. */
  cacheFile?: string;
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  totalPages: number;
  durationMs: number;
  /** Estimated time saved by skipping cached pages, based on how long those pages took to build when they were last built. */
  timeSavedMs: number;
  incremental: boolean;
  clean: boolean;
}

export interface EngineResult {
  pages: Page[];
  outputDir: string;
  stats: BuildStats;
}

/**
 * Core SSG engine: discovers Markdown files under `contentDir` and drives
 * them through the registered plugins' lifecycle hooks. The engine itself
 * knows nothing about Markdown parsing, templating, or serving -- those
 * behaviors come entirely from the plugins passed in.
 */
export class SsgEngine {
  constructor(private readonly options: EngineOptions) {}

  build(): EngineResult {
    const start = Date.now();
    const { contentDir, outputDir, templatesDir, plugins } = this.options;
    const incremental = this.options.incremental ?? false;
    const clean = this.options.clean ?? false;
    const cacheFile = this.options.cacheFile ?? path.join(outputDir, DEFAULT_CACHE_FILE_NAME);

    if (!fs.existsSync(contentDir) || !fs.statSync(contentDir).isDirectory()) {
      throw new Error(`Content directory not found: ${contentDir}`);
    }

    if (clean) {
      deleteCacheManifest(cacheFile);
    }

    const templatesHash = hashDirectory(templatesDir);
    const pluginsSignature = plugins.map((plugin) => plugin.name).join('|');
    const previousManifest = incremental && !clean ? loadCacheManifest(cacheFile) : undefined;
    const cacheIsValid =
      !!previousManifest &&
      previousManifest.templatesHash === templatesHash &&
      previousManifest.pluginsSignature === pluginsSignature;

    const unchangedSourcePaths = new Set<string>();
    const ctx: PluginContext = {
      contentDir,
      outputDir,
      templatesDir,
      config: this.options.config ?? {},
      ...(incremental ? { incremental: { unchangedSourcePaths } } : {}),
    };

    for (const plugin of plugins) plugin.onStart?.(ctx);
    for (const plugin of plugins) plugin.beforeBuild?.(ctx);

    const files = findMarkdownFiles(contentDir);
    const newCacheEntries: Record<string, CacheEntry> = {};
    let pagesBuilt = 0;
    let pagesSkipped = 0;
    let timeSavedMs = 0;

    const pages = files.map((filePath) => {
      const sourcePath = path.relative(contentDir, filePath);
      const sourceHash = hashFile(filePath);
      const cachedEntry = cacheIsValid ? previousManifest!.pages[sourcePath] : undefined;

      if (cachedEntry && cachedEntry.sourceHash === sourceHash) {
        pagesSkipped += 1;
        timeSavedMs += cachedEntry.buildTimeMs;
        unchangedSourcePaths.add(sourcePath);
        newCacheEntries[sourcePath] = cachedEntry;
        return cachedEntry.page;
      }

      const pageStart = Date.now();
      const page = this.buildPage(filePath, contentDir, ctx);
      const buildTimeMs = Date.now() - pageStart;
      pagesBuilt += 1;
      newCacheEntries[sourcePath] = { sourceHash, buildTimeMs, page };
      return page;
    });

    pages.sort(comparePages);

    for (const plugin of plugins) plugin.afterBuild?.(pages, ctx);
    for (const plugin of plugins) plugin.onEnd?.(ctx);

    if (incremental) {
      saveCacheManifest(cacheFile, {
        version: CACHE_VERSION,
        templatesHash,
        pluginsSignature,
        pages: newCacheEntries,
      });
    }

    const stats: BuildStats = {
      pagesBuilt,
      pagesSkipped,
      totalPages: pages.length,
      durationMs: Date.now() - start,
      timeSavedMs,
      incremental,
      clean,
    };

    return { pages, outputDir, stats };
  }

  private buildPage(filePath: string, contentDir: string, ctx: PluginContext): Page {
    let page = createPageSkeleton(filePath, contentDir);
    for (const plugin of this.options.plugins) {
      const result = plugin.onFile?.(page, ctx);
      if (result) page = result;
    }
    return page;
  }
}

function createPageSkeleton(filePath: string, contentDir: string): Page {
  const relativePath = path.relative(contentDir, filePath);
  const slug = slugify(relativePath);

  return {
    slug,
    title: slug,
    tags: [],
    html: '',
    sourcePath: relativePath,
    outputFile: `${slug}.html`,
  };
}

function comparePages(a: Page, b: Page): number {
  if (a.date && b.date) return b.date.localeCompare(a.date);
  if (a.date) return -1;
  if (b.date) return 1;
  return a.title.localeCompare(b.title);
}

function findMarkdownFiles(dir: string): string[] {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const files: string[] = [];

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...findMarkdownFiles(fullPath));
    } else if (entry.isFile() && /\.md$/i.test(entry.name)) {
      files.push(fullPath);
    }
  }

  return files;
}

function slugify(relativePath: string): string {
  const withoutExt = relativePath.replace(/\.md$/i, '');
  const slug = withoutExt
    .split(path.sep)
    .join('-')
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');

  // "index" is reserved for the generated listing page.
  if (!slug || slug === 'index') return slug === 'index' ? 'index-page' : 'page';
  return slug;
}
