import fs from 'fs';
import path from 'path';
import { Plugin, PluginContext, SSGConfig } from './plugin';
import { BuildOptions, Page } from './types';
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
   */
  buildOnce(options: BuildOptions = {}): Page[] {
    const ctx = this.createContext(options);
    this.runHook('beforeBuild', ctx);

    const files = collectMarkdownFiles(ctx.contentDir);
    const pages = files.map((file) =>
      this.runOnFile({ sourcePath: file, slug: toSlug(file, ctx.contentDir) } as Page, ctx)
    );
    ctx.pages = pages;

    this.runHook('afterBuild', ctx);
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
