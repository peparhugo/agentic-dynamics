import fs from 'fs';
import path from 'path';
import { Page, BuildResult, BuildStats } from './types';
import {
  Plugin,
  PluginContext,
  runHooks,
  loadConfig,
  pluginsFromConfig,
  discoverPlugins,
} from './plugin';
import { CacheManager, CACHE_FILE } from './cache';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import {
  DevServerPlugin,
  ServeOptions,
  ServeHandle,
} from './plugins/devServer';
import { DEFAULT_TEMPLATES_DIR } from './template';

export interface EngineOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  configFile?: string;
  cwd?: string;
  devServer?: boolean;
  extraPlugins?: Plugin[];
  incremental?: boolean;
  clean?: boolean;
}

export function sortPages(pages: Page[]): Page[] {
  return [...pages].sort((a, b) => {
    const da = a.date ? new Date(a.date).getTime() : 0;
    const db = b.date ? new Date(b.date).getTime() : 0;
    if (da !== db) return db - da;
    return a.title.localeCompare(b.title);
  });
}

export function createBuiltinPlugins(): Plugin[] {
  return [new MarkdownPlugin(), new TemplatePlugin()];
}

export class SiteEngine {
  private plugins: Plugin[];
  private context: PluginContext;
  private devServer?: DevServerPlugin;
  private incremental: boolean;
  private clean: boolean;
  private stats: BuildStats;

  constructor(options: EngineOptions) {
    const cwd = options.cwd ?? process.cwd();
    const config = loadConfig(cwd, options.configFile);

    const plugins: Plugin[] = [];
    const seen = new Set<string>();

    const add = (plugin: Plugin): void => {
      if (seen.has(plugin.name)) return;
      seen.add(plugin.name);
      plugins.push(plugin);
    };

    const builtins = createBuiltinPlugins();
    const markdown = builtins.find((p) => p.name === 'markdown');
    const template = builtins.find((p) => p.name === 'template');

    if (markdown) add(markdown);
    for (const plugin of pluginsFromConfig(config)) add(plugin);
    for (const plugin of discoverPlugins(cwd)) add(plugin);
    if (options.extraPlugins) {
      for (const plugin of options.extraPlugins) add(plugin);
    }
    if (template) add(template);
    if (options.devServer) {
      this.devServer = new DevServerPlugin();
      add(this.devServer);
    }

    this.plugins = plugins;
    this.context = {
      contentDir: options.contentDir,
      outputDir: options.outputDir,
      templatesDir: options.templatesDir ?? DEFAULT_TEMPLATES_DIR,
      config,
      pages: [],
      files: [],
    };
    this.incremental = options.incremental ?? false;
    this.clean = options.clean ?? false;
    this.stats = { pagesBuilt: 0, pagesSkipped: 0, timeSavedMs: 0 };
  }

  getPlugins(): Plugin[] {
    return [...this.plugins];
  }

  getContext(): PluginContext {
    return this.context;
  }

  build(): BuildResult {
    const ctx = this.context;
    ctx.pages = [];
    ctx.files = [];
    runHooks(this.plugins, 'onStart', ctx);

    this.stats = { pagesBuilt: 0, pagesSkipped: 0, timeSavedMs: 0 };

    let cache: CacheManager | undefined;
    if (this.incremental) {
      const cacheFile = path.join(ctx.outputDir, CACHE_FILE);
      if (this.clean && fs.existsSync(cacheFile)) {
        fs.rmSync(cacheFile);
      }
      cache = new CacheManager(cacheFile, ctx.templatesDir, ctx.contentDir, ctx.outputDir);
      ctx.cache = cache;
    } else {
      ctx.cache = undefined;
    }

    fs.mkdirSync(ctx.outputDir, { recursive: true });
    runHooks(this.plugins, 'beforeBuild', ctx);
    const pages = sortPages(ctx.pages);
    ctx.pages = pages;

    for (const page of pages) {
      if (cache && cache.isUnchanged(page.filePath)) {
        const entry = cache.getEntry(page.filePath);
        this.stats.pagesSkipped++;
        if (entry) this.stats.timeSavedMs += entry.renderMs;
        const name = `${page.slug}.html`;
        const outFile = path.join(ctx.outputDir, name);
        if (!fs.existsSync(outFile) && entry) {
          fs.writeFileSync(outFile, entry.html, 'utf8');
        }
        if (!ctx.files.includes(name)) ctx.files.push(name);
        continue;
      }

      this.stats.pagesBuilt++;
      const started = Date.now();
      let current: Page = page;
      for (const plugin of this.plugins) {
        if (typeof plugin.onFile === 'function') {
          const out = plugin.onFile(current, ctx);
          if (out) current = out;
        }
      }
      if (cache) {
        const renderMs = Math.max(1, Date.now() - started);
        const name = `${current.slug}.html`;
        const outFile = path.join(ctx.outputDir, name);
        let html = '';
        try {
          html = fs.readFileSync(outFile, 'utf8');
        } catch {
          html = '';
        }
        cache.record(current.filePath, current, html, renderMs);
      }
    }

    const result = this.finishBuild();

    if (cache) {
      const activeFiles = ctx.pages.map((p) => p.filePath);
      cache.removeStale(activeFiles, ctx.outputDir);
      cache.save();
    }

    runHooks(this.plugins, 'onEnd', ctx);
    return result;
  }

  rebuild(): BuildResult {
    const ctx = this.context;
    ctx.pages = [];
    ctx.files = [];
    this.stats = { pagesBuilt: 0, pagesSkipped: 0, timeSavedMs: 0 };
    ctx.cache = undefined;
    this.runBuildPhase();
    return this.finishBuild();
  }

  private runBuildPhase(): void {
    const ctx = this.context;
    fs.mkdirSync(ctx.outputDir, { recursive: true });
    runHooks(this.plugins, 'beforeBuild', ctx);
    const pages = sortPages(ctx.pages);
    ctx.pages = pages;
    for (const page of pages) {
      this.stats.pagesBuilt++;
      let current: Page = page;
      for (const plugin of this.plugins) {
        if (typeof plugin.onFile === 'function') {
          const out = plugin.onFile(current, ctx);
          if (out) current = out;
        }
      }
    }
  }

  private finishBuild(): BuildResult {
    const ctx = this.context;
    const provisional: BuildResult = {
      pages: ctx.pages.length,
      outputDir: ctx.outputDir,
      files: [...ctx.files],
      pagesBuilt: this.stats.pagesBuilt,
      pagesSkipped: this.stats.pagesSkipped,
      timeSavedMs: this.stats.timeSavedMs,
    };
    runHooks(this.plugins, 'afterBuild', ctx, provisional);
    return {
      pages: ctx.pages.length,
      outputDir: ctx.outputDir,
      files: [...ctx.files],
      pagesBuilt: this.stats.pagesBuilt,
      pagesSkipped: this.stats.pagesSkipped,
      timeSavedMs: this.stats.timeSavedMs,
    };
  }

  serve(options: ServeOptions): ServeHandle {
    const ctx = this.context;
    ctx.rebuild = () => {
      try {
        this.rebuild();
      } catch (err) {
        console.error(
          '[ssg serve] rebuild failed:',
          err instanceof Error ? err.message : err
        );
      }
    };

    if (!this.devServer) {
      this.devServer = new DevServerPlugin();
      this.plugins.push(this.devServer);
    }
    if (typeof options.port === 'number') {
      this.devServer.setPort(options.port);
    }

    this.rebuild();
    runHooks(this.plugins, 'onStart', ctx);
    return this.devServer.getHandle();
  }
}
