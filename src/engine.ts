import fs from 'fs';
import path from 'path';
import type { Page } from './types';
import { resolveTemplateDir } from './plugins/template-plugin';
import type {
  Plugin,
  PluginContext,
  PluginEngine,
  PluginFactory,
  SSGConfig,
} from './plugins/types';
import {
  CACHE_FILE_NAME,
  emptyBuildStats,
  hashFile,
  hashTemplateDir,
  loadBuildCache,
  saveBuildCache,
} from './cache';
import type { BuildCache, BuildStats, CacheEntry } from './cache';

export type EngineCommand = 'build' | 'serve';

export interface EngineOptions {
  contentDir: string;
  outputDir: string;
  templateDir?: string;
  defaultTemplate?: string;
  defaultLayout?: string;
  command?: EngineCommand;
  config?: SSGConfig;
  /**
   * Only rebuild pages whose source or template inputs changed, reusing the
   * cached parsed pages and rendered HTML from `.ssg-cache.json`.
   */
  incremental?: boolean;
  /** Ignore the build cache and rebuild every page (still writes a fresh cache). */
  clean?: boolean;
  /** Location of the build cache manifest (default: `<outputDir>/.ssg-cache.json`). */
  cacheFile?: string;
}

type HookName = 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd';

function isPromise(value: unknown): value is Promise<unknown> {
  return (
    value !== null &&
    typeof value === 'object' &&
    typeof (value as { then?: unknown }).then === 'function'
  );
}

/**
 * The core SSG engine. Owns the shared plugin context and orchestrates the
 * plugin pipeline. Hooks run in plugin registration order:
 *
 *   onStart -> beforeBuild -> onFile (per content file) -> afterBuild -> onEnd
 *
 * The pipeline is available both synchronously (`buildSync`/`runSync`) for
 * the CLI build command and asynchronously (`build`/`run`) so plugins can
 * perform async work in long-running sessions such as the dev server.
 */
export class SsgEngine implements PluginEngine {
  readonly plugins: Plugin[];
  readonly context: PluginContext;
  /** Statistics for the most recent build (only meaningful for incremental builds). */
  readonly stats: BuildStats;

  private readonly contentDir: string;
  private readonly outputDir: string;
  private readonly templateDir?: string;
  private readonly incremental: boolean;
  private readonly clean: boolean;
  private readonly cacheFile: string;
  private cache: BuildCache | null = null;

  constructor(options: EngineOptions, plugins: Array<Plugin | PluginFactory>) {
    this.contentDir = path.resolve(options.contentDir);
    this.outputDir = path.resolve(options.outputDir);
    this.templateDir = options.templateDir;
    this.incremental = options.incremental === true || options.clean === true;
    this.clean = options.clean === true;
    this.cacheFile = options.cacheFile
      ? path.resolve(options.cacheFile)
      : path.join(this.outputDir, CACHE_FILE_NAME);
    this.stats = emptyBuildStats(this.clean);
    const context: PluginContext = {
      command: options.command ?? 'build',
      config: options.config ?? {},
      contentDir: this.contentDir,
      outputDir: this.outputDir,
      templateDir: options.templateDir,
      defaultTemplate: options.defaultTemplate,
      defaultLayout: options.defaultLayout,
      pages: [],
      plugins: [],
      shared: {},
      engine: this,
    };
    const resolved: Plugin[] = [];
    for (const entry of plugins) {
      const plugin = typeof entry === 'function' ? entry(context) : entry;
      resolved.push(plugin);
    }
    context.plugins = resolved;
    this.plugins = resolved;
    this.context = context;
  }

  /** Run the `onStart` hooks. */
  async start(): Promise<void> {
    await this.runHook('onStart');
  }

  /** Run the `onEnd` hooks. */
  async end(): Promise<void> {
    await this.runHook('onEnd');
  }

  /** Run the full build pipeline and return the generated pages. */
  async build(): Promise<Page[]> {
    this.validateContentDir();
    await this.runHook('beforeBuild');
    fs.mkdirSync(this.outputDir, { recursive: true });
    const pages = this.incremental ? await this.collectIncremental() : await this.collectPages();
    this.context.pages = pages;
    await this.runHook('afterBuild');
    if (this.incremental) {
      this.finalizeCache();
    }
    return pages;
  }

  /** Run the entire lifecycle: onStart, build, onEnd. */
  async run(): Promise<Page[]> {
    await this.start();
    const pages = await this.build();
    await this.end();
    return pages;
  }

  /** Synchronous build pipeline (all hooks must return synchronously). */
  buildSync(): Page[] {
    this.validateContentDir();
    this.runHookSync('beforeBuild');
    fs.mkdirSync(this.outputDir, { recursive: true });
    const pages = this.incremental ? this.collectIncrementalSync() : this.collectPagesSync();
    this.context.pages = pages;
    this.runHookSync('afterBuild');
    if (this.incremental) {
      this.finalizeCache();
    }
    return pages;
  }

  /** Synchronous full lifecycle: onStart, build, onEnd. */
  runSync(): Page[] {
    this.runHookSync('onStart');
    const pages = this.buildSync();
    this.runHookSync('onEnd');
    return pages;
  }

  private validateContentDir(): void {
    if (!fs.existsSync(this.contentDir)) {
      throw new Error(`Content directory does not exist: ${this.contentDir}`);
    }
    if (!fs.statSync(this.contentDir).isDirectory()) {
      throw new Error(`Content path is not a directory: ${this.contentDir}`);
    }
  }

  private async runHook(name: HookName): Promise<void> {
    for (const plugin of this.plugins) {
      const hook = plugin[name];
      if (!hook) {
        continue;
      }
      await hook.call(plugin, this.context);
    }
  }

  private runHookSync(name: HookName): void {
    for (const plugin of this.plugins) {
      const hook = plugin[name];
      if (!hook) {
        continue;
      }
      const result = hook.call(plugin, this.context);
      if (isPromise(result)) {
        throw new Error(
          `Plugin "${plugin.name}" returned a Promise from "${name}" during a synchronous build`
        );
      }
    }
  }

  private async collectPages(): Promise<Page[]> {
    const pages: Page[] = [];
    const entries = fs.readdirSync(this.contentDir).sort();
    for (const entry of entries) {
      const page = await this.runOnFile(entry);
      if (page) {
        pages.push(page);
      }
    }
    return pages;
  }

  private collectPagesSync(): Page[] {
    const pages: Page[] = [];
    const entries = fs.readdirSync(this.contentDir).sort();
    for (const entry of entries) {
      const page = this.runOnFileSync(entry);
      if (page) {
        pages.push(page);
      }
    }
    return pages;
  }

  /**
   * Load (or, for a clean build, reset) the cache manifest and record whether
   * a reusable cache was present.
   */
  private prepareCache(): BuildCache {
    if (this.cache) {
      return this.cache;
    }
    if (this.clean && fs.existsSync(this.cacheFile)) {
      fs.rmSync(this.cacheFile);
    }
    const cache = loadBuildCache(this.cacheFile);
    this.stats.cacheLoaded = !this.clean && Object.keys(cache.entries).length > 0;
    this.cache = cache;
    return cache;
  }

  private computeTemplateHash(): string {
    return hashTemplateDir(resolveTemplateDir(this.templateDir), {
      defaultTemplate: this.context.defaultTemplate,
      defaultLayout: this.context.defaultLayout,
    });
  }

  private isUsableCacheEntry(
    cached: CacheEntry,
    sourceHash: string,
    templateHash: string
  ): boolean {
    return cached.sourceHash === sourceHash && cached.templateHash === templateHash;
  }

  /**
   * Incremental page collection: pages whose source and template inputs are
   * unchanged are rebuilt from the cache; everything else flows through the
   * plugin pipeline as usual.
   */
  private async collectIncremental(): Promise<Page[]> {
    const cache = this.prepareCache();
    const templateHash = this.computeTemplateHash();
    const pages: Page[] = [];
    const entries = fs.readdirSync(this.contentDir).sort();
    for (const entry of entries) {
      const filePath = path.join(this.contentDir, entry);
      if (!fs.statSync(filePath).isFile()) {
        continue;
      }
      const sourceHash = hashFile(filePath);
      const cached = cache.entries[entry];
      if (cached && this.isUsableCacheEntry(cached, sourceHash, templateHash)) {
        const page = cached.page;
        page.renderedHtml = cached.renderedHtml;
        pages.push(page);
        this.stats.skipped += 1;
        this.stats.timeSavedMs += cached.buildMs;
        continue;
      }
      const start = Date.now();
      const page = await this.runOnFile(entry);
      if (page) {
        cache.entries[entry] = {
          slug: page.slug,
          sourceHash,
          templateHash,
          page,
          renderedHtml: '',
          buildMs: Math.max(Date.now() - start, 1),
        };
        pages.push(page);
        this.stats.built += 1;
      } else {
        delete cache.entries[entry];
      }
    }
    this.pruneStaleEntries(entries, cache);
    this.stats.total = pages.length;
    return pages;
  }

  /** Synchronous variant of {@link collectIncremental}. */
  private collectIncrementalSync(): Page[] {
    const cache = this.prepareCache();
    const templateHash = this.computeTemplateHash();
    const pages: Page[] = [];
    const entries = fs.readdirSync(this.contentDir).sort();
    for (const entry of entries) {
      const filePath = path.join(this.contentDir, entry);
      if (!fs.statSync(filePath).isFile()) {
        continue;
      }
      const sourceHash = hashFile(filePath);
      const cached = cache.entries[entry];
      if (cached && this.isUsableCacheEntry(cached, sourceHash, templateHash)) {
        const page = cached.page;
        page.renderedHtml = cached.renderedHtml;
        pages.push(page);
        this.stats.skipped += 1;
        this.stats.timeSavedMs += cached.buildMs;
        continue;
      }
      const start = Date.now();
      const page = this.runOnFileSync(entry);
      if (page) {
        cache.entries[entry] = {
          slug: page.slug,
          sourceHash,
          templateHash,
          page,
          renderedHtml: '',
          buildMs: Math.max(Date.now() - start, 1),
        };
        pages.push(page);
        this.stats.built += 1;
      } else {
        delete cache.entries[entry];
      }
    }
    this.pruneStaleEntries(entries, cache);
    this.stats.total = pages.length;
    return pages;
  }

  /**
   * Remove cache entries (and their output HTML) for content files that no
   * longer exist, so a deleted page does not leave stale output behind.
   */
  private pruneStaleEntries(liveEntries: string[], cache: BuildCache): void {
    const live = new Set(liveEntries);
    for (const key of Object.keys(cache.entries)) {
      if (live.has(key)) {
        continue;
      }
      const entry = cache.entries[key];
      const staleHtml = path.join(this.outputDir, `${entry.page.slug}.html`);
      if (fs.existsSync(staleHtml)) {
        fs.rmSync(staleHtml);
      }
      delete cache.entries[key];
    }
  }

  /**
   * Capture the rendered HTML produced during `afterBuild` and persist the
   * updated cache manifest.
   */
  private finalizeCache(): void {
    const cache = this.cache;
    if (!cache) {
      return;
    }
    const bySlug = new Map<string, CacheEntry>();
    for (const entry of Object.values(cache.entries)) {
      bySlug.set(entry.page.slug, entry);
    }
    for (const page of this.context.pages) {
      const entry = bySlug.get(page.slug);
      if (entry && typeof page.renderedHtml === 'string' && page.renderedHtml.length > 0) {
        entry.renderedHtml = page.renderedHtml;
      }
    }
    saveBuildCache(this.cacheFile, cache);
  }

  private async runOnFile(entry: string): Promise<Page | null> {
    let page: Page | null | undefined = { slug: entry, title: entry, contentHtml: '', content: '' };
    for (const plugin of this.plugins) {
      if (!plugin.onFile) {
        continue;
      }
      const result = await plugin.onFile(page, this.context);
      if (result === undefined || result === null) {
        page = null;
        break;
      }
      page = result;
    }
    return page;
  }

  private runOnFileSync(entry: string): Page | null {
    let page: Page | null | undefined = { slug: entry, title: entry, contentHtml: '', content: '' };
    for (const plugin of this.plugins) {
      if (!plugin.onFile) {
        continue;
      }
      const result = plugin.onFile(page, this.context);
      if (isPromise(result)) {
        throw new Error(
          `Plugin "${plugin.name}" returned a Promise from "onFile" during a synchronous build`
        );
      }
      if (result === undefined || result === null) {
        page = null;
        break;
      }
      page = result;
    }
    return page;
  }
}
