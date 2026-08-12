import fs from 'fs';
import path from 'path';
import type { PluginContext } from './types';
import type { Page } from './types';
import { PluginPipeline } from './plugin';
import { loadConfig, loadPluginsFromConfig, resolveConfigPath } from './plugin-loader';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import { DevServerPlugin } from './plugins/dev-server';
import {
  CACHE_FILE,
  emptyCache,
  emptyStats,
  loadCache,
  pruneCacheEntries,
  saveCache,
} from './cache';
import type { BuildCache, BuildStats } from './cache';

export interface EngineOptions {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  configPath?: string;
  /** Only rebuild pages whose source or template changed. */
  incremental?: boolean;
  /** Ignore any existing cache and rebuild everything. */
  clean?: boolean;
}

function emptyTemplateSet(dir: string): PluginContext['templates'] {
  return { dir, templates: new Map(), layouts: new Map(), partials: new Map() };
}

export class SSGEngine {
  readonly context: PluginContext;
  readonly pipeline: PluginPipeline;
  readonly options: EngineOptions;
  stats: BuildStats = emptyStats();

  constructor(options: EngineOptions) {
    const config = loadConfig(options.configPath);
    const configPath = resolveConfigPath(options.configPath);
    const configDir = configPath ? path.dirname(configPath) : process.cwd();

    this.options = options;
    this.context = {
      config,
      contentDir: options.contentDir,
      outputDir: options.outputDir,
      templatesDir: options.templatesDir,
      pages: [],
      templates: emptyTemplateSet(options.templatesDir),
      output: {},
      incremental: options.incremental ?? false,
    };

    this.pipeline = new PluginPipeline();
    this.pipeline.add(new MarkdownPlugin());
    this.pipeline.add(new TemplatePlugin());
    this.pipeline.add(new DevServerPlugin());
    for (const plugin of loadPluginsFromConfig(config, configDir)) {
      this.pipeline.add(plugin);
    }
  }

  private runPipelineSync(ctx: PluginContext): void {
    this.pipeline.onStart(ctx);
    this.pipeline.beforeBuild(ctx);

    for (const page of ctx.pages) {
      this.pipeline.onFile(page, ctx);
    }

    this.pipeline.afterBuild(ctx);
    this.pipeline.onEnd(ctx);
  }

  private async runPipelineAsync(ctx: PluginContext): Promise<void> {
    await this.pipeline.runAsync('onStart', ctx);
    await this.pipeline.runAsync('beforeBuild', ctx);

    for (const page of ctx.pages) {
      await this.pipeline.runAsync('onFile', page, ctx);
    }

    await this.pipeline.runAsync('afterBuild', ctx);
    await this.pipeline.runAsync('onEnd', ctx);
  }

  private prepareCache(ctx: PluginContext): void {
    const cachePath = path.join(ctx.outputDir, CACHE_FILE);
    const useCache = this.options.incremental === true && this.options.clean !== true;
    const previous = useCache ? loadCache(cachePath) : null;
    ctx.cache = previous ?? emptyCache();
    ctx.stats = emptyStats();
  }

  private persistCache(ctx: PluginContext): void {
    const cachePath = path.join(ctx.outputDir, CACHE_FILE);
    if (ctx.cache) {
      pruneCacheEntries(ctx.cache, ctx.pages.map((page) => page.slug));
      saveCache(cachePath, ctx.cache);
    }
  }

  build(): Page[] {
    const ctx = this.context;
    fs.mkdirSync(ctx.outputDir, { recursive: true });

    this.prepareCache(ctx);
    this.runPipelineSync(ctx);

    this.stats = ctx.stats ?? emptyStats();
    this.stats.pages = ctx.pages.length;
    this.persistCache(ctx);

    return ctx.pages;
  }

  buildWithStats(): { pages: Page[]; stats: BuildStats } {
    const pages = this.build();
    return { pages, stats: this.stats };
  }

  async buildAsync(): Promise<Page[]> {
    const ctx = this.context;
    fs.mkdirSync(ctx.outputDir, { recursive: true });

    this.prepareCache(ctx);
    await this.runPipelineAsync(ctx);

    this.stats = ctx.stats ?? emptyStats();
    this.stats.pages = ctx.pages.length;
    this.persistCache(ctx);

    return ctx.pages;
  }
}
