import { promises as fs } from 'node:fs';
import path from 'node:path';
import { loadConfiguredPlugins } from './config';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import type { BuildContext, BuildOptions, GeneratedPage, Plugin } from './types';

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(entryPath);
    return entry.isFile() && /\.md$/i.test(entry.name) ? [entryPath] : [];
  }));
  return files.flat().sort();
}

export class SSGEngine {
  readonly plugins: Plugin[];
  readonly context: BuildContext;

  constructor(options: BuildOptions = {}) {
    const resolved = {
      contentDir: path.resolve(options.contentDir ?? './content'),
      outputDir: path.resolve(options.outputDir ?? './dist'),
      templatesDir: path.resolve(options.templatesDir ?? './templates'),
    };
    this.context = { options: resolved, pages: [] };
    this.plugins = [new MarkdownPlugin(), new TemplatePlugin(), ...loadConfiguredPlugins(options)];
  }

  private async runHook(hook: 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd'): Promise<void> {
    for (const plugin of this.plugins) await plugin[hook]?.(this.context);
  }

  async build(): Promise<GeneratedPage[]> {
    try {
      await this.runHook('onStart');
      const files = await markdownFiles(this.context.options.contentDir);
      this.context.pages.splice(0, this.context.pages.length, ...files.map((sourcePath): GeneratedPage => {
        const relative = path.relative(this.context.options.contentDir, sourcePath).replace(/\.md$/i, '.html');
        return {
          sourcePath,
          outputPath: path.join(this.context.options.outputDir, relative),
          url: relative.split(path.sep).map(encodeURIComponent).join('/'),
          title: path.basename(sourcePath, path.extname(sourcePath)),
          data: {},
          content: '',
          html: '',
        };
      }));

      await this.runHook('beforeBuild');
      for (const page of this.context.pages) {
        for (const plugin of this.plugins) await plugin.onFile?.(page, this.context);
      }
      this.context.pages.sort((a, b) => {
        if (a.data.date && b.data.date) return b.data.date.localeCompare(a.data.date);
        return a.title.localeCompare(b.title);
      });
      await this.runHook('afterBuild');
      return this.context.pages;
    } finally {
      await this.runHook('onEnd');
    }
  }
}

export async function buildSite(options: BuildOptions = {}): Promise<GeneratedPage[]> {
  return new SSGEngine(options).build();
}
