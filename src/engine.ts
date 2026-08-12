import fs from 'fs/promises';
import path from 'path';
import { Plugin, PluginHook, SsgContext } from './plugin';
import { SsgConfig, loadConfiguredPlugins } from './config';
import { BuildOptions, Page } from './types';
import {
  collectMarkdownFiles,
  renderIndexHtml,
  slugFromSource,
} from './core';
import { defaultPlugins } from './plugins';
import { DEFAULT_TEMPLATE_DIR } from './template';

function dedupePlugins(plugins: Plugin[]): Plugin[] {
  const seen = new Set<string>();
  const result: Plugin[] = [];
  for (const plugin of plugins) {
    if (!plugin || seen.has(plugin.name)) continue;
    seen.add(plugin.name);
    result.push(plugin);
  }
  return result;
}

export class SsgEngine {
  readonly context: SsgContext;
  readonly plugins: Plugin[];

  constructor(
    readonly options: BuildOptions,
    extraPlugins: Plugin[] = [],
    readonly config: SsgConfig = {}
  ) {
    this.plugins = dedupePlugins([...defaultPlugins(), ...extraPlugins]);
    this.context = {
      options,
      config: this.config,
      engine: this,
      pages: [],
      templateDir: path.resolve(options.templateDir ?? DEFAULT_TEMPLATE_DIR),
      startTime: Date.now(),
    };
  }

  async start(): Promise<void> {
    await this.runHook('onStart');
  }

  async build(): Promise<Page[]> {
    await this.runHook('beforeBuild');
    const pages = await this.buildPages();
    this.context.pages = pages;
    await this.writeOutput(pages);
    await this.runHook('afterBuild');
    return pages;
  }

  async close(): Promise<void> {
    await this.runHook('onEnd');
  }

  private async runHook(hook: PluginHook, arg?: unknown): Promise<void> {
    for (const plugin of this.plugins) {
      const fn = (plugin as unknown as Record<string, unknown>)[hook];
      if (typeof fn === 'function') {
        await (fn as (a: unknown) => unknown).call(plugin, arg ?? this.context);
      }
    }
  }

  private async buildPages(): Promise<Page[]> {
    const sources = await collectMarkdownFiles(this.options.contentDir);
    const pages: Page[] = [];
    for (const source of sources) {
      let page: Page = {
        slug: slugFromSource(source),
        source,
        title: '',
        date: undefined,
        tags: [],
        body: '',
        html: '',
      };
      for (const plugin of this.plugins) {
        if (typeof plugin.onFile === 'function') {
          const result = await plugin.onFile(page, this.context);
          if (result) page = result;
        }
      }
      pages.push(page);
    }
    return pages;
  }

  private async writeOutput(pages: Page[]): Promise<void> {
    const outputDir = this.options.outputDir;
    await fs.rm(outputDir, { recursive: true, force: true });
    await fs.mkdir(outputDir, { recursive: true });
    for (const page of pages) {
      const dest = path.join(outputDir, `${page.slug}.html`);
      await fs.mkdir(path.dirname(dest), { recursive: true });
      await fs.writeFile(dest, page.renderedHtml ?? page.html, 'utf-8');
    }
    await fs.writeFile(
      path.join(outputDir, 'index.html'),
      renderIndexHtml(pages),
      'utf-8'
    );
  }
}

export function createEngine(
  options: BuildOptions,
  plugins?: Plugin[],
  config?: SsgConfig
): SsgEngine {
  return new SsgEngine(options, plugins ?? [], config ?? {});
}

export async function buildSite(options: BuildOptions): Promise<Page[]> {
  const { plugins, config } = await loadConfiguredPlugins();
  const engine = createEngine(options, plugins, config);
  await engine.start();
  try {
    return await engine.build();
  } finally {
    await engine.close();
  }
}
