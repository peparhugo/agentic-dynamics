import fs from 'fs';
import path from 'path';
import { Plugin, PluginContext, SSGConfig } from './plugin';
import { BuildOptions, BuildStats, Page } from './types';
import {
  CacheManifest,
  cachePathFor,
  emptyManifest,
  hashDir,
  hashFile,
  isEntryValid,
  loadCache,
  saveCache,
} from './cache';
import { MarkdownPlugin } from '../plugins/markdown';
import { TemplatePlugin } from '../plugins/template';

const DEFAULT_CONTENT_DIR = 'content';
const DEFAULT_OUTPUT_DIR = 'dist';
const DEFAULT_TEMPLATE_DIR = 'templates';

export function collectMarkdownFiles(dir: string): string[] {
  const results: string[] = [];
  if (!fs.existsSync(dir)) {
    return results;
  }
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  entries.sort((a, b) => a.name.localeCompare(b.name));
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...collectMarkdownFiles(fullPath));
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.md')) {
      results.push(fullPath);
    }
  }
  return results;
}

export function toSlug(sourcePath: string, baseDir?: string): string {
  let relative = baseDir ? path.relative(baseDir, sourcePath) : path.basename(sourcePath);
  relative = relative.replace(/\\/g, '/');
  const parsed = path.parse(relative);
  const base = parsed.name === 'index' ? '' : parsed.name;
  const dir = parsed.dir ? `${parsed.dir}/` : '';
  return `${dir}${base}`.replace(/\/+$/, '') || 'index';
}

/**
 * The core SSG engine. It loads plugins (built-in plus any configured through
 * ssg.config.ts) and orchestrates the plugin pipeline.
 */
export class SSGEngine {
  readonly config: SSGConfig;
  private readonly plugins: Plugin[];
  lastStats: BuildStats | undefined;

  constructor(config: SSGConfig = {}) {
    this.config = config;
    this.plugins = buildPluginList(config);
  }

  get pluginList(): Plugin[] {
    return [...this.plugins];
  }

  addPlugin(plugin: Plugin): void {
    if (!this.plugins.some((p) => p.name === plugin.name)) {
      this.plugins.push(plugin);
    }
  }

  private createContext(options: BuildOptions): PluginContext {
    return {
      options,
      contentDir: path.resolve(options.contentDir ?? DEFAULT_CONTENT_DIR),
      outputDir: path.resolve(options.outputDir ?? DEFAULT_OUTPUT_DIR),
      templateDir: path.resolve(options.templateDir ?? DEFAULT_TEMPLATE_DIR),
      pages: [],
      config: this.config,
    };
  }

  private runHook(hook: 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd', ctx: PluginContext): void {
    for (const plugin of this.plugins) {
      const fn = plugin[hook];
      if (fn) {
        fn.call(plugin, ctx);
      }
    }
  }

  private runOnFile(page: Page, ctx: PluginContext): Page {
    let current = page;
    for (const plugin of this.plugins) {
      if (plugin.onFile) {
        const result = plugin.onFile(current, ctx);
        if (result) {
          current = result;
        }
      }
    }
    return current;
  }

  /**
   * Per-build pipeline: beforeBuild -> onFile (per page) -> afterBuild.
   * Used both by build() and by live-reload rebuilds.
   *
   * When `options.incremental` (or `options.clean`) is set, a `.ssg-cache.json`
   * manifest tracks file hashes and cached output. Pages whose source and
   * template hashes are unchanged are skipped (no markdown parse, no render);
   * everything else goes through the normal plugin pipeline.
   */
  buildOnce(options: BuildOptions = {}): Page[] {
    const ctx = this.createContext(options);
    const useCache = !!(options.incremental || options.clean);
    const cachePath = cachePathFor(ctx.outputDir);
    const manifest: CacheManifest | undefined = useCache
      ? options.clean
        ? emptyManifest()
        : loadCache(cachePath) ?? emptyManifest()
      : undefined;
    const templateHash = useCache ? hashDir(ctx.templateDir) : '';
    const stats: BuildStats = {
      total: 0,
      built: 0,
      skipped: 0,
      timeSaved: 0,
      cacheFile: useCache ? cachePath : undefined,
    };

    this.runHook('beforeBuild', ctx);

    const files = collectMarkdownFiles(ctx.contentDir);
    stats.total = files.length;
    const pages: Page[] = [];
    const sourceHashes = new Map<string, string>();
    const onFileMs = new Map<string, number>();
    const skippedSlugs = new Set<string>();

    for (const file of files) {
      const slug = toSlug(file, ctx.contentDir);
      const sourceHash = hashFile(file);
      sourceHashes.set(slug, sourceHash);
      const cached = manifest?.entries?.[slug];

      if (useCache && cached && isEntryValid(cached, sourceHash, templateHash)) {
        pages.push({ ...cached.page, sourcePath: file, rendered: cached.rendered });
        skippedSlugs.add(slug);
        stats.skipped += 1;
        stats.timeSaved += cached.pageMs;
        continue;
      }

      const start = Date.now();
      pages.push(this.runOnFile({ sourcePath: file, slug } as Page, ctx));
      onFileMs.set(slug, Date.now() - start);
      stats.built += 1;
    }

    ctx.pages = pages;

    // Remove output and cache entries for pages that no longer exist.
    if (useCache && manifest) {
      for (const slug of Object.keys(manifest.entries)) {
        if (!sourceHashes.has(slug)) {
          const htmlPath = path.join(ctx.outputDir, `${slug}.html`);
          if (fs.existsSync(htmlPath)) {
            fs.rmSync(htmlPath, { force: true });
          }
          delete manifest.entries[slug];
        }
      }
    }

    this.runHook('afterBuild', ctx);

    // Persist the manifest once rendering finished so cached rendered HTML and
    // parsed frontmatter are available to later incremental builds.
    if (useCache && manifest) {
      for (const page of ctx.pages) {
        const slug = page.slug;
        const sourceHash = sourceHashes.get(slug) ?? hashFile(page.sourcePath);
        const rendered = page.rendered ?? '';
        const pageMs = skippedSlugs.has(slug)
          ? manifest.entries[slug]?.pageMs ?? 0
          : (page.renderMs ?? 0) + (onFileMs.get(slug) ?? 0);
        const pageData = { ...page } as Record<string, unknown>;
        delete pageData.rendered;
        delete pageData.renderMs;
        manifest.entries[slug] = {
          source: page.sourcePath,
          sourceHash,
          templateHash,
          page: pageData as unknown as Page,
          rendered,
          pageMs,
        };
      }
      saveCache(cachePath, manifest);
    }

    this.lastStats = stats;
    return pages;
  }

  /**
   * Full lifecycle run: onStart -> buildOnce -> onEnd.
   */
  build(options: BuildOptions = {}): Page[] {
    const ctx = this.createContext(options);
    this.runHook('onStart', ctx);
    const pages = this.buildOnce(options);
    this.runHook('onEnd', ctx);
    return pages;
  }

  /**
   * Starts the pipeline up to the first build. Lifecycle onEnd is deferred
   * until stop() so that long-running plugins (e.g. the dev server) survive
   * repeated rebuilds.
   */
  start(options: BuildOptions = {}): Page[] {
    const ctx = this.createContext(options);
    this.runHook('onStart', ctx);
    return this.buildOnce(options);
  }

  stop(): void {
    const ctx = this.createContext({});
    this.runHook('onEnd', ctx);
  }
}

function buildPluginList(config: SSGConfig): Plugin[] {
  const list: Plugin[] = [];
  const names = new Set<string>();
  const push = (plugin: Plugin): void => {
    if (!names.has(plugin.name)) {
      names.add(plugin.name);
      list.push(plugin);
    }
  };

  push(new MarkdownPlugin());
  push(new TemplatePlugin());

  for (const plugin of config.plugins ?? []) {
    push(plugin);
  }
  return list;
}
