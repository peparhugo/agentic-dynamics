import { promises as fs } from 'fs';
import * as path from 'path';

import type { BuildOptions, Page } from './types';
import { PluginPipeline, type Plugin, type PluginContext } from './plugin';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/templates';
import { BuildCache, CACHE_KEY } from './cache';

export interface SSGConfig {
  plugins?: Plugin[];
}

export interface EngineOptions extends BuildOptions {
  configFile?: string;
}

export function defaultPlugins(): Plugin[] {
  return [new MarkdownPlugin(), new TemplatePlugin()];
}

export async function loadConfig(configFile?: string): Promise<SSGConfig | null> {
  const file = configFile ?? 'ssg.config';
  const resolved = path.resolve(process.cwd(), file);
  try {
    const loaded = require(resolved) as { default?: SSGConfig; config?: SSGConfig } | SSGConfig;
    const cfg = ((loaded as { default?: SSGConfig }).default ??
      (loaded as { config?: SSGConfig }).config ??
      loaded) as SSGConfig;
    if (cfg && typeof cfg === 'object' && Array.isArray(cfg.plugins)) {
      return cfg;
    }
    return null;
  } catch {
    return null;
  }
}

export class SSGEngine {
  static async fromOptions(options: EngineOptions, ...extra: Plugin[]): Promise<SSGEngine> {
    let base: Plugin[];
    if (options.plugins && options.plugins.length > 0) {
      base = [...options.plugins];
    } else {
      const config = await loadConfig(options.configFile);
      if (config && Array.isArray(config.plugins) && config.plugins.length > 0) {
        base = [...config.plugins];
      } else {
        base = defaultPlugins();
      }
    }
    const merged: Plugin[] = [];
    for (const plugin of [...base, ...extra]) {
      if (!merged.some((existing) => existing.name === plugin.name)) {
        merged.push(plugin);
      }
    }
    return new SSGEngine(merged);
  }

  readonly pipeline: PluginPipeline;

  constructor(plugins: Plugin[] = []) {
    this.pipeline = new PluginPipeline();
    for (const plugin of plugins) {
      this.pipeline.use(plugin);
    }
  }

  async build(options: BuildOptions): Promise<Page[]> {
    const startedAt = Date.now();
    const cache = await BuildCache.create(options);

    const ctx: PluginContext = {
      options,
      pages: [],
      outputs: new Map(),
      shared: new Map(),
    };
    if (cache) {
      ctx.shared.set(CACHE_KEY, cache);
    }

    await this.pipeline.runStart(ctx);
    await this.pipeline.runBeforeBuild(ctx);
    for (const page of ctx.pages) {
      await this.pipeline.runOnFile(page, ctx);
    }
    await this.pipeline.runAfterBuild(ctx);

    await fs.mkdir(options.outputDir, { recursive: true });
    const writes: Promise<void>[] = [];
    for (const [relative, html] of ctx.outputs) {
      writes.push(fs.writeFile(path.join(options.outputDir, relative), html, 'utf8'));
    }
    await Promise.all(writes);

    if (cache) {
      await cache.removeStaleOutputs();
      await cache.save();
      options.onStats?.(cache.report(Date.now() - startedAt));
    } else {
      options.onStats?.({
        incremental: false,
        clean: !!options.clean,
        total: ctx.outputs.size,
        built: ctx.outputs.size,
        skipped: 0,
        timeSavedMs: 0,
        durationMs: Date.now() - startedAt,
      });
    }

    await this.pipeline.runOnEnd(ctx);
    return ctx.pages;
  }
}
