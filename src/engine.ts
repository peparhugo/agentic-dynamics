import fs from 'fs';
import path from 'path';
import type { PluginContext } from './types';
import type { Page } from './types';
import { PluginPipeline } from './plugin';
import { loadConfig, loadPluginsFromConfig, resolveConfigPath } from './plugin-loader';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import { DevServerPlugin } from './plugins/dev-server';

export interface EngineOptions {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  configPath?: string;
}

function emptyTemplateSet(dir: string): PluginContext['templates'] {
  return { dir, templates: new Map(), layouts: new Map(), partials: new Map() };
}

export class SSGEngine {
  readonly context: PluginContext;
  readonly pipeline: PluginPipeline;

  constructor(options: EngineOptions) {
    const config = loadConfig(options.configPath);
    const configPath = resolveConfigPath(options.configPath);
    const configDir = configPath ? path.dirname(configPath) : process.cwd();

    this.context = {
      config,
      contentDir: options.contentDir,
      outputDir: options.outputDir,
      templatesDir: options.templatesDir,
      pages: [],
      templates: emptyTemplateSet(options.templatesDir),
      output: {},
    };

    this.pipeline = new PluginPipeline();
    this.pipeline.add(new MarkdownPlugin());
    this.pipeline.add(new TemplatePlugin());
    this.pipeline.add(new DevServerPlugin());
    for (const plugin of loadPluginsFromConfig(config, configDir)) {
      this.pipeline.add(plugin);
    }
  }

  build(): Page[] {
    const ctx = this.context;
    fs.mkdirSync(ctx.outputDir, { recursive: true });

    this.pipeline.onStart(ctx);
    this.pipeline.beforeBuild(ctx);

    for (const page of ctx.pages) {
      this.pipeline.onFile(page, ctx);
    }

    this.pipeline.afterBuild(ctx);
    this.pipeline.onEnd(ctx);

    return ctx.pages;
  }

  async buildAsync(): Promise<Page[]> {
    const ctx = this.context;
    fs.mkdirSync(ctx.outputDir, { recursive: true });

    await this.pipeline.runAsync('onStart', ctx);
    await this.pipeline.runAsync('beforeBuild', ctx);

    for (const page of ctx.pages) {
      await this.pipeline.runAsync('onFile', page, ctx);
    }

    await this.pipeline.runAsync('afterBuild', ctx);
    await this.pipeline.runAsync('onEnd', ctx);

    return ctx.pages;
  }
}
