import fs from 'fs';
import { Page, BuildResult } from './types';
import {
  Plugin,
  PluginContext,
  runHooks,
  loadConfig,
  pluginsFromConfig,
  discoverPlugins,
} from './plugin';
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
    this.runBuildPhase();
    const result = this.finishBuild();
    runHooks(this.plugins, 'onEnd', ctx);
    return result;
  }

  rebuild(): BuildResult {
    const ctx = this.context;
    ctx.pages = [];
    ctx.files = [];
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
    };
    runHooks(this.plugins, 'afterBuild', ctx, provisional);
    return {
      pages: ctx.pages.length,
      outputDir: ctx.outputDir,
      files: [...ctx.files],
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
