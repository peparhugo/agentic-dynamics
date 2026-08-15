import fs from 'node:fs/promises';
import path from 'node:path';
import { BuildOptions, Page, Plugin, PluginContext, resolveBuildOptions } from './plugin';
import MarkdownPlugin from './plugins/markdown';
import TemplatePlugin from './plugins/template';

export type { BuildOptions, Page, Plugin, PluginContext } from './plugin';

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await markdownFiles(file));
    else if (/\.md$/i.test(entry.name)) files.push(file);
  }
  return files.sort();
}

function configuredPlugins(config: unknown): Plugin[] {
  if (!config || typeof config !== 'object') return [];
  const value = Array.isArray(config) ? config : (config as { plugins?: unknown }).plugins;
  if (!Array.isArray(value)) return [];
  return value.flatMap((plugin) => {
    if (typeof plugin === 'function') return [new (plugin as new () => Plugin)()];
    if (plugin && typeof plugin === 'object') return [plugin as Plugin];
    return [];
  });
}

function loadConfig(filename: string): Plugin[] {
  try {
    // require is intentional: it works with ts-jest and with compiled JS configs.
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const loaded = require(filename) as { default?: unknown } & Record<string, unknown>;
    return configuredPlugins(loaded.default ?? loaded);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'MODULE_NOT_FOUND') return [];
    throw error;
  }
}

export class SSG {
  private readonly options: PluginContext['options'];
  private readonly plugins: Plugin[];
  private running = false;

  constructor(options: BuildOptions = {}, additionalPlugins: Plugin[] = []) {
    this.options = resolveBuildOptions(options);
    const configFile = path.resolve(options.configFile ?? './ssg.config.ts');
    const configured = options.plugins ?? loadConfig(configFile);
    // External onFile hooks run between parsing and rendering so they can modify pages.
    this.plugins = [new MarkdownPlugin(), ...configured, ...additionalPlugins, new TemplatePlugin()];
  }

  async build(): Promise<void> {
    if (this.running) return;
    this.running = true;
    const files = await markdownFiles(this.options.contentDir);
    const pages: Page[] = files.map((source) => ({
      source,
      url: path.relative(this.options.contentDir, source).replace(/\.md$/i, '.html').split(path.sep).join('/'),
      data: {}, content: '', html: '', body: '',
    }));
    const context: PluginContext = {
      options: this.options, pages, files, state: new Map(), rebuild: async () => this.build(),
    };
    try {
      await fs.rm(this.options.outputDir, { recursive: true, force: true });
      await fs.mkdir(this.options.outputDir, { recursive: true });
      await this.runHook('onStart', context);
      await this.runHook('beforeBuild', context);
      for (const page of pages) await this.runFileHooks(page, context);
      await this.runHook('afterBuild', context);
      await this.runHook('onEnd', context);
    } finally {
      this.running = false;
    }
  }

  private async runHook(hook: 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd', context: PluginContext): Promise<void> {
    for (const plugin of this.plugins) if (plugin[hook]) await plugin[hook]!(context);
  }

  private async runFileHooks(page: Page, context: PluginContext): Promise<void> {
    for (const plugin of this.plugins) if (plugin.onFile) await plugin.onFile(page, context);
  }
}

export async function buildSite(options: BuildOptions = {}): Promise<void> {
  await new SSG(options).build();
}
