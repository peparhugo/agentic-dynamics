import { promises as fs } from 'node:fs';
import path from 'node:path';
import { loadPlugins } from './config';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import type { BuildContext, BuildOptions, Page, Plugin } from './types';

async function markdownFiles(directory: string, base = directory): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry): Promise<string[]> => {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(fullPath, base);
    return entry.isFile() && /\.md$/i.test(entry.name) ? [path.relative(base, fullPath)] : [];
  }));
  return files.flat().sort((left, right) => left.localeCompare(right));
}

const isWithin = (relativePath: string): boolean => relativePath === '' || (!relativePath.startsWith('..') && !path.isAbsolute(relativePath));

export class SsgEngine {
  constructor(private readonly options: BuildOptions = {}) {}

  async build(): Promise<Page[]> {
    const context: BuildContext = {
      contentDir: path.resolve(this.options.contentDir ?? './content'),
      outputDir: path.resolve(this.options.outputDir ?? './dist'),
      templateDir: path.resolve(this.options.templateDir ?? './templates'),
      options: this.options,
      pages: [],
    };
    this.validateDirectories(context);

    const stats = await fs.stat(context.contentDir).catch(() => undefined);
    if (!stats?.isDirectory()) throw new Error(`Content directory does not exist: ${context.contentDir}`);

    const markdown = new MarkdownPlugin();
    const configured = this.options.plugins ?? await loadPlugins(path.resolve(this.options.configFile ?? 'ssg.config.ts'));
    const plugins: Plugin[] = [markdown, ...configured, new TemplatePlugin()];
    let started = false;
    try {
      started = true;
      await this.runHook(plugins, 'onStart', context);
      await this.runHook(plugins, 'beforeBuild', context);
      const files = await markdownFiles(context.contentDir);
      context.pages = await Promise.all(files.map(async (relativePath) => {
        const source = await fs.readFile(path.join(context.contentDir, relativePath), 'utf8');
        return markdown.parse(source, relativePath);
      }));
      context.pages.sort((left, right) => {
        if (left.date && right.date && left.date !== right.date) return right.date.localeCompare(left.date);
        if (left.date !== right.date) return left.date ? -1 : 1;
        return left.title.localeCompare(right.title);
      });
      for (let index = 0; index < context.pages.length; index += 1) {
        let page = context.pages[index];
        for (const plugin of plugins) {
          page = await plugin.onFile?.(page, context) ?? page;
          context.pages[index] = page;
        }
      }
      await this.runHook(plugins, 'afterBuild', context);
      return context.pages;
    } finally {
      if (started) await this.runHook(plugins, 'onEnd', context);
    }
  }

  private validateDirectories(context: BuildContext): void {
    if (isWithin(path.relative(context.contentDir, context.outputDir)) || isWithin(path.relative(context.outputDir, context.contentDir))) {
      throw new Error('Content and output directories must not overlap');
    }
  }

  private async runHook(plugins: Plugin[], hook: 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd', context: BuildContext): Promise<void> {
    for (const plugin of plugins) await plugin[hook]?.(context);
  }
}
