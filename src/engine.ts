import { promises as fs } from 'node:fs';
import path from 'node:path';
import type { Plugin, PluginContext } from './plugin';
import type { BuildOptions, Page } from './types';

export const pageSources = new WeakMap<Page, string>();

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(fullPath);
    return /\.md$/i.test(entry.name) ? [fullPath] : [];
  }));
  return files.flat().sort();
}

export class SSGEngine {
  readonly options: PluginContext['options'];
  readonly pages: Page[] = [];
  private started = false;
  private ended = false;
  private readonly startedPlugins: Plugin[] = [];
  private readonly context: PluginContext;

  constructor(options: BuildOptions, readonly plugins: Plugin[]) {
    this.options = {
      ...options,
      content: path.resolve(options.content ?? './content'),
      output: path.resolve(options.output ?? './dist'),
      templates: path.resolve(options.templates ?? './templates'),
    };
    if (this.options.content === this.options.output) {
      throw new Error('Content and output directories must be different');
    }
    this.context = { options: this.options, pages: this.pages, build: () => this.build() };
  }

  async start(): Promise<void> {
    if (this.started) return;
    this.started = true;
    for (const plugin of this.plugins) {
      await plugin.onStart?.(this.context);
      this.startedPlugins.push(plugin);
    }
  }

  async build(): Promise<Page[]> {
    if (!this.started) await this.start();
    if (this.ended) throw new Error('Cannot build after the SSG engine has ended');
    const files = await markdownFiles(this.options.content);
    this.pages.splice(0, this.pages.length, ...await Promise.all(files.map(async (file) => {
      const relativePath = path.relative(this.options.content, file);
      const page: Page = {
        title: path.basename(file, path.extname(file)),
        tags: [],
        url: relativePath.replace(/\.md$/i, '.html').split(path.sep).join('/'),
        html: '',
      };
      pageSources.set(page, await fs.readFile(file, 'utf8'));
      return page;
    })));

    await fs.rm(this.options.output, { recursive: true, force: true });
    await fs.mkdir(this.options.output, { recursive: true });
    for (const plugin of this.plugins) await plugin.beforeBuild?.(this.context);
    for (const page of this.pages) {
      for (const plugin of this.plugins) await plugin.onFile?.(page, this.context);
    }
    this.pages.sort((left, right) => {
      if (left.date && right.date && left.date !== right.date) return right.date.localeCompare(left.date);
      if (left.date !== right.date) return left.date ? -1 : 1;
      return left.title.localeCompare(right.title);
    });
    for (const plugin of this.plugins) await plugin.afterBuild?.(this.context);
    return this.pages;
  }

  async end(): Promise<void> {
    if (!this.started || this.ended) return;
    this.ended = true;
    for (const plugin of this.startedPlugins) await plugin.onEnd?.(this.context);
  }
}
