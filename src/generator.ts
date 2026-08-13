import path from 'node:path';
import { loadPlugins } from './config.js';
import { MarkdownPlugin } from './plugins/markdown.js';
import { TemplatePlugin } from './plugins/template.js';
import type { BuildContext, BuildOptions, Plugin } from './plugin.js';

export interface Page {
  slug: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
  template?: string;
  layout?: string;
  data: Record<string, unknown>;
}

export type { BuildOptions, BuildContext, Plugin } from './plugin.js';

export class SsgEngine {
  constructor(private readonly options: BuildOptions = {}, private readonly plugins: Plugin[] = []) {}

  async build(): Promise<Page[]> {
    const context = this.context();
    try {
      await this.run('onStart', context);
      await this.run('beforeBuild', context);
      for (const page of context.pages) await this.run('onFile', context, page);
      await this.run('afterBuild', context);
      return context.pages;
    } finally {
      await this.run('onEnd', context);
    }
  }

  private context(): BuildContext {
    return {
      options: {
        contentDir: path.resolve(this.options.contentDir ?? 'content'),
        outputDir: path.resolve(this.options.outputDir ?? 'dist'),
        templatesDir: path.resolve(this.options.templatesDir ?? 'templates')
      },
      pages: []
    };
  }

  private async run(hook: keyof Plugin, context: BuildContext, page?: Page): Promise<void> {
    for (const plugin of this.plugins) {
      const handler = plugin[hook];
      if (!handler) continue;
      if (hook === 'onFile') await (handler as NonNullable<Plugin['onFile']>)(page!, context);
      else await (handler as (context: BuildContext) => void | Promise<void>)(context);
    }
  }
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const configuredPlugins = await loadPlugins();
  return new SsgEngine(options, [new MarkdownPlugin(), new TemplatePlugin(), ...configuredPlugins]).build();
}

export async function readPages(contentDir: string): Promise<Page[]> {
  const context: BuildContext = { options: { contentDir: path.resolve(contentDir), outputDir: '', templatesDir: '' }, pages: [] };
  await new MarkdownPlugin().beforeBuild(context);
  return context.pages;
}
